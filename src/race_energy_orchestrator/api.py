from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from threading import RLock

import pandas as pd
import plotly
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import EnergyConfig, F1_2026_EVENTS, F1_2026_RACE_END_DATES, SUPPORTED_YEAR, event_data_available
from .data import FastF1DataUnavailable, load_lap_data
from .live import build_live_decision_feed
from .metrics import metrics_frame
from .model import simulate_strategy
from .scenarios import compare_scenarios
from .segmentation import add_track_features
from .stint import build_stint_plan


class HealthResponse(BaseModel):
    status: str
    service: str
    data_source: str


class SessionResponse(BaseModel):
    year: int
    event: str
    session_name: str
    driver: str
    circuit_label: str
    data_source: str
    data_mode: str
    source_detail: str
    sample_count: int
    lap_duration_s: float
    ambient_temp_c: float
    battery_soft_limit_c: float
    horizon_s: float
    initial_soc_mj: float
    minimum_soc_mj: float
    usable_energy_mj: float
    target_finish_soc_mj: float


class DecisionResponse(BaseModel):
    index: int
    total: int
    decision: dict[str, float | str]


class MetricsResponse(BaseModel):
    rows: list[dict[str, float | str]]


class TraceResponse(BaseModel):
    fixed_map: list[dict[str, float | str]]
    predictive_mpc: list[dict[str, float | str]]


class ExplorerResponse(BaseModel):
    rows: list[dict[str, float | str | bool]]


class StintStateResponse(BaseModel):
    name: str
    soc_mj: float
    soc_pct: float
    battery_temp_c: float
    thermal_headroom_c: float
    attack_required_soc_mj: float


class StintSummaryResponse(BaseModel):
    attack_lap: int | None
    projected_finish_soc_mj: float
    projected_finish_soc_pct: float
    cumulative_lap_time_delta_s: float
    confidence_pct: float
    data_basis: str


class StintLapResponse(BaseModel):
    lap: int
    mode: str
    start_soc_mj: float
    target_soc_mj: float
    target_soc_pct: float
    deploy_budget_mj: float
    regen_budget_mj: float
    battery_temp_c: float
    clipping_risk: float
    lap_time_delta_s: float
    estimated_lap_time_s: float
    reason_tr: str
    reason_en: str


class StintPlanResponse(BaseModel):
    current_lap: int
    horizon_laps: int
    state: StintStateResponse
    summary: StintSummaryResponse
    laps: list[StintLapResponse]


TRACK_OPTIONS = [
    {
        "event": event,
        "label": label,
        "race_end_date": F1_2026_RACE_END_DATES[event].isoformat(),
        "data_available": event_data_available(event),
    }
    for event, label in F1_2026_EVENTS
]

_SESSION_LOCK = RLock()
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_WEB_ROOT = _PROJECT_ROOT / "web"
_PLOTLY_BUNDLE = Path(plotly.__file__).resolve().parent / "package_data" / "plotly.min.js"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Race Energy Orchestrator API",
        version="0.1.0",
        description="Decision API for predictive hybrid race energy orchestration.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", service="race-energy-orchestrator", data_source="FastF1")

    @app.get("/assets/plotly.min.js", include_in_schema=False)
    def plotly_bundle() -> FileResponse:
        return FileResponse(_PLOTLY_BUNDLE, media_type="text/javascript", headers={"Cache-Control": "public, max-age=86400"})

    @app.get("/api/session", response_model=SessionResponse)
    def session_summary(
        year: int = Query(default=SUPPORTED_YEAR, ge=SUPPORTED_YEAR, le=SUPPORTED_YEAR),
        event: str = Query(default="Suzuka", min_length=2, max_length=80),
        session_name: str = Query(default="Q", min_length=1, max_length=20),
        driver: str = Query(default="LEC", min_length=2, max_length=4),
    ) -> SessionResponse:
        session = _session(year, event, session_name, driver)
        lap_data = session["lap_data"]
        frame = session["predictive"]
        config = session["config"]
        return SessionResponse(
            year=session["year"],
            event=session["event"],
            session_name=session["session_name"],
            driver=session["driver"],
            circuit_label=session["circuit_label"],
            data_source=lap_data.source,
            source_detail=(
                f"Deterministic {event}-like lap with public 2026-style ERS assumptions"
                if lap_data.source == "Synthetic"
                else lap_data.source_detail
            ),
            data_mode="synthetic" if lap_data.source == "Synthetic" else "fastf1",
            sample_count=len(frame),
            lap_duration_s=float(frame["time_s"].iloc[-1]),
            ambient_temp_c=config.ambient_temp_c,
            battery_soft_limit_c=config.battery_soft_limit_c,
            horizon_s=config.horizon_s,
            initial_soc_mj=config.initial_soc_mj,
            minimum_soc_mj=config.minimum_soc_mj,
            usable_energy_mj=config.usable_energy_mj,
            target_finish_soc_mj=config.target_finish_soc_mj,
        )

    @app.get("/api/metrics", response_model=MetricsResponse)
    def metrics(
        year: int = Query(default=SUPPORTED_YEAR, ge=SUPPORTED_YEAR, le=SUPPORTED_YEAR),
        event: str = Query(default="Suzuka", min_length=2, max_length=80),
        session_name: str = Query(default="Q", min_length=1, max_length=20),
        driver: str = Query(default="LEC", min_length=2, max_length=4),
    ) -> MetricsResponse:
        session = _session(year, event, session_name, driver)
        rows = session["metrics"].to_dict(orient="records")
        return MetricsResponse(rows=[_json_record(row) for row in rows])

    @app.get("/api/options")
    def options() -> dict[str, object]:
        return {"years": [SUPPORTED_YEAR], "events": TRACK_OPTIONS, "sessions": ["Q", "R", "FP1", "FP2", "FP3"]}

    @app.get("/api/decision", response_model=DecisionResponse)
    def decision(
        index: int = Query(default=0, ge=0),
        year: int = Query(default=SUPPORTED_YEAR, ge=SUPPORTED_YEAR, le=SUPPORTED_YEAR),
        event: str = Query(default="Suzuka", min_length=2, max_length=80),
        session_name: str = Query(default="Q", min_length=1, max_length=20),
        driver: str = Query(default="LEC", min_length=2, max_length=4),
    ) -> DecisionResponse:
        feed = _session(year, event, session_name, driver)["feed"]
        bounded_index = min(index, len(feed) - 1)
        return DecisionResponse(index=bounded_index, total=len(feed), decision=_record(feed.iloc[bounded_index]))

    @app.get("/api/decisions", response_model=list[DecisionResponse])
    def decisions(
        start: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
        year: int = Query(default=SUPPORTED_YEAR, ge=SUPPORTED_YEAR, le=SUPPORTED_YEAR),
        event: str = Query(default="Suzuka", min_length=2, max_length=80),
        session_name: str = Query(default="Q", min_length=1, max_length=20),
        driver: str = Query(default="LEC", min_length=2, max_length=4),
    ) -> list[DecisionResponse]:
        feed = _session(year, event, session_name, driver)["feed"]
        end = min(start + limit, len(feed))
        return [
            DecisionResponse(index=index, total=len(feed), decision=_record(feed.iloc[index]))
            for index in range(start, end)
        ]

    @app.get("/api/trace", response_model=TraceResponse)
    def trace(
        year: int = Query(default=SUPPORTED_YEAR, ge=SUPPORTED_YEAR, le=SUPPORTED_YEAR),
        event: str = Query(default="Suzuka", min_length=2, max_length=80),
        session_name: str = Query(default="Q", min_length=1, max_length=20),
        driver: str = Query(default="LEC", min_length=2, max_length=4),
    ) -> TraceResponse:
        session = _session(year, event, session_name, driver)
        return TraceResponse(
            fixed_map=[_trace_record(row) for _, row in session["fixed"].iterrows()],
            predictive_mpc=[_trace_record(row) for _, row in session["predictive"].iterrows()],
        )

    @app.get("/api/explorer", response_model=ExplorerResponse)
    def explorer(
        year: int = Query(default=SUPPORTED_YEAR, ge=SUPPORTED_YEAR, le=SUPPORTED_YEAR),
        event: str = Query(default="Suzuka", min_length=2, max_length=80),
        session_name: str = Query(default="Q", min_length=1, max_length=20),
        driver: str = Query(default="LEC", min_length=2, max_length=4),
    ) -> ExplorerResponse:
        session = _session(year, event, session_name, driver)
        rows = []
        for strategy, key in (("fixed_map", "fixed"), ("predictive_mpc", "predictive")):
            rows.extend(_explorer_record(row, strategy) for _, row in session[key].iterrows())
        return ExplorerResponse(rows=rows)

    @app.get("/api/scenarios")
    def scenarios(
        year: int = Query(default=SUPPORTED_YEAR, ge=SUPPORTED_YEAR, le=SUPPORTED_YEAR),
        event: str = Query(default="Suzuka", min_length=2, max_length=80),
        session_name: str = Query(default="Q", min_length=1, max_length=20),
        driver: str = Query(default="LEC", min_length=2, max_length=4),
    ) -> list[dict[str, object]]:
        session = _session(year, event, session_name, driver)
        comparison = compare_scenarios(session["lap_data"].frame, session["config"])
        return comparison.to_dict(orient="records")

    @app.get("/api/stint-plan", response_model=StintPlanResponse)
    def stint_plan(
        current_lap: int = Query(default=1, ge=1, le=200),
        horizon_laps: int = Query(default=5, ge=3, le=10),
        year: int = Query(default=SUPPORTED_YEAR, ge=SUPPORTED_YEAR, le=SUPPORTED_YEAR),
        event: str = Query(default="Suzuka", min_length=2, max_length=80),
        session_name: str = Query(default="Q", min_length=1, max_length=20),
        driver: str = Query(default="LEC", min_length=2, max_length=4),
    ) -> StintPlanResponse:
        session = _session(year, event, session_name, driver)
        plan = build_stint_plan(
            session["predictive"],
            session["config"],
            current_lap=current_lap,
            horizon_laps=horizon_laps,
            data_source=session["lap_data"].source,
        )
        return StintPlanResponse.model_validate(plan)

    app.mount("/", StaticFiles(directory=_WEB_ROOT, html=True), name="web")
    return app


@lru_cache(maxsize=16)
def _cached_session(year: int = SUPPORTED_YEAR, event: str = "Suzuka", session_name: str = "Q", driver: str = "LEC") -> dict[str, object]:
    if year == SUPPORTED_YEAR and event in F1_2026_RACE_END_DATES and not event_data_available(event):
        race_end = F1_2026_RACE_END_DATES[event].isoformat()
        raise HTTPException(
            status_code=409,
            detail=f"{event} yarışı henüz tamamlanmadı ({race_end}); gerçek telemetry verisi henüz mevcut değil.",
        )
    config = EnergyConfig()
    try:
        lap_data = load_lap_data(
            year=year,
            event=event,
            session_name=session_name,
            driver=driver,
            cache_dir="work/fastf1-cache",
            synthetic_only=False,
            allow_synthetic_fallback=False,
        )
    except FastF1DataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    featured = add_track_features(lap_data.frame, config)
    fixed = simulate_strategy(featured, config, "fixed_map")
    predictive = simulate_strategy(featured, config, "predictive_mpc")
    metrics = metrics_frame([fixed, predictive], config)
    feed = build_live_decision_feed(predictive, config)
    return {
        "config": config,
        "lap_data": lap_data,
        "fixed": fixed,
        "predictive": predictive,
        "metrics": metrics,
        "feed": feed,
        "year": year,
        "event": event,
        "session_name": session_name,
        "driver": driver,
        "circuit_label": (
            f"{event} telemetry"
            if lap_data.source != "Synthetic"
            else f"{event}-like synthetic proxy"
        ),
    }


def _session(year: int = SUPPORTED_YEAR, event: str = "Suzuka", session_name: str = "Q", driver: str = "LEC") -> dict[str, object]:
    with _SESSION_LOCK:
        return _cached_session(year, event, session_name, driver)


def _clear_session_cache() -> None:
    with _SESSION_LOCK:
        _cached_session.cache_clear()


_session.cache_clear = _clear_session_cache  # type: ignore[attr-defined]


def _record(row: pd.Series) -> dict[str, float | str]:
    return {
        "time_s": float(row["time_s"]),
        "distance_m": float(row["distance_m"]),
        "segment_type": str(row["segment_type"]),
        "soc_mj": float(row["soc_mj"]),
        "battery_temp_c": float(row["battery_temp_c"]),
        "clipping_risk": float(row["clipping_risk"]),
        "deploy_kw": float(row["deploy_kw"]),
        "regen_kw": float(row["regen_kw"]),
        "command": str(row["command"]),
        "severity": str(row["severity"]),
        "reason_tr": str(row["reason_tr"]),
        "reason_en": str(row["reason_en"]),
        "confidence_pct": float(row["confidence_pct"]),
        "next_straight_eta_s": float(row["next_straight_eta_s"]),
        "speed_kmh": float(row["speed_kmh"]),
        "aero_mode": str(row["aero_mode"]),
    }


def _trace_record(row: pd.Series) -> dict[str, float | str]:
    return {
        "time_s": float(row["time_s"]),
        "distance_m": float(row["distance_m"]),
        "segment_type": str(row["segment_type"]),
        "speed_kmh": float(row["speed_kmh"]),
        "aero_mode": str(row["aero_mode"]),
        "driver_command": str(row["driver_command"]),
        "deploy_kw": float(row["deploy_kw"]),
        "regen_kw": float(row["regen_kw"]),
        "soc_mj": float(row["soc_mj"]),
        "clipping_risk": float(row["clipping_risk"]),
        "battery_temp_c": float(row["battery_temp_c"]),
    }


def _explorer_record(row: pd.Series, strategy: str) -> dict[str, float | str | bool]:
    return {
        "time_s": float(row["time_s"]),
        "distance_m": float(row["distance_m"]),
        "segment_type": str(row["segment_type"]),
        "strategy": strategy,
        "driver_command": str(row["driver_command"]),
        "deploy_kw": float(row["deploy_kw"]),
        "regen_kw": float(row["regen_kw"]),
        "soc_mj": float(row["soc_mj"]),
        "battery_temp_c": float(row["battery_temp_c"]),
        "clipping_risk": float(row["clipping_risk"]),
        "clipping": bool(row["clipping"]),
        "thermal_limited": bool(row["thermal_limited"]),
    }


def _json_record(row: dict[str, object]) -> dict[str, float | str]:
    return {
        key: float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)
        for key, value in row.items()
    }


app = create_app()
