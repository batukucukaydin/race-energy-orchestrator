from __future__ import annotations

from functools import lru_cache

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import EnergyConfig
from .data import load_lap_data
from .live import build_live_decision_feed
from .metrics import metrics_frame
from .model import simulate_strategy
from .segmentation import add_track_features


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
    initial_soc_mj: float


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


TRACK_OPTIONS = [
    {"event": "Monza", "label": "Monza"},
    {"event": "Spa-Francorchamps", "label": "Spa-Francorchamps"},
    {"event": "Silverstone", "label": "Silverstone"},
    {"event": "Suzuka", "label": "Suzuka"},
]


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
        session = _session()
        return HealthResponse(status="ok", service="race-energy-orchestrator", data_source=session["lap_data"].source)

    @app.get("/api/session", response_model=SessionResponse)
    def session_summary(
        year: int = Query(default=2024, ge=2020, le=2030),
        event: str = Query(default="Monza", min_length=2, max_length=80),
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
            initial_soc_mj=config.initial_soc_mj,
        )

    @app.get("/api/metrics", response_model=MetricsResponse)
    def metrics(
        year: int = Query(default=2024, ge=2020, le=2030),
        event: str = Query(default="Monza", min_length=2, max_length=80),
        session_name: str = Query(default="Q", min_length=1, max_length=20),
        driver: str = Query(default="LEC", min_length=2, max_length=4),
    ) -> MetricsResponse:
        session = _session(year, event, session_name, driver)
        rows = session["metrics"].to_dict(orient="records")
        return MetricsResponse(rows=[_json_record(row) for row in rows])

    @app.get("/api/options")
    def options() -> dict[str, object]:
        return {"years": [2024, 2025, 2026], "events": TRACK_OPTIONS, "sessions": ["Q", "R", "FP1", "FP2", "FP3"]}

    @app.get("/api/decision", response_model=DecisionResponse)
    def decision(
        index: int = Query(default=0, ge=0),
        year: int = Query(default=2024, ge=2020, le=2030),
        event: str = Query(default="Monza", min_length=2, max_length=80),
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
        year: int = Query(default=2024, ge=2020, le=2030),
        event: str = Query(default="Monza", min_length=2, max_length=80),
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
        year: int = Query(default=2024, ge=2020, le=2030),
        event: str = Query(default="Monza", min_length=2, max_length=80),
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
        year: int = Query(default=2024, ge=2020, le=2030),
        event: str = Query(default="Monza", min_length=2, max_length=80),
        session_name: str = Query(default="Q", min_length=1, max_length=20),
        driver: str = Query(default="LEC", min_length=2, max_length=4),
    ) -> ExplorerResponse:
        session = _session(year, event, session_name, driver)
        rows = []
        for strategy, key in (("fixed_map", "fixed"), ("predictive_mpc", "predictive")):
            rows.extend(_explorer_record(row, strategy) for _, row in session[key].iterrows())
        return ExplorerResponse(rows=rows)

    return app


@lru_cache(maxsize=16)
def _session(year: int = 2024, event: str = "Monza", session_name: str = "Q", driver: str = "LEC") -> dict[str, object]:
    config = EnergyConfig()
    lap_data = load_lap_data(
        year=year,
        event=event,
        session_name=session_name,
        driver=driver,
        cache_dir="work/fastf1-cache",
        synthetic_only=True,
    )
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
        "circuit_label": f"{event}-like synthetic proxy",
    }


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
        "distance_m": float(row["distance_m"]),
        "segment_type": str(row["segment_type"]),
        "speed_kmh": float(row["speed_kmh"]),
        "aero_mode": str(row["aero_mode"]),
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
