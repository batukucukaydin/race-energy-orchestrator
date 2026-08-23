from __future__ import annotations

import pandas as pd

from race_energy_orchestrator.cli import main
from race_energy_orchestrator.config import EnergyConfig
from race_energy_orchestrator.data import generate_synthetic_lap
from race_energy_orchestrator.data import FastF1DataUnavailable
from race_energy_orchestrator.metrics import metrics_frame
from race_energy_orchestrator.live import build_live_decision_feed
from race_energy_orchestrator.model import simulate_strategy
from race_energy_orchestrator.segmentation import add_track_features
from race_energy_orchestrator.scenarios import compare_scenarios
from race_energy_orchestrator.stint import build_stint_plan
from race_energy_orchestrator import api
from race_energy_orchestrator.api import app
from fastapi.testclient import TestClient


def _synthetic_featured(config: EnergyConfig | None = None) -> pd.DataFrame:
    cfg = config or EnergyConfig()
    return add_track_features(generate_synthetic_lap().frame, cfg)


def test_energy_bounds_and_power_limits() -> None:
    config = EnergyConfig()
    trace = simulate_strategy(_synthetic_featured(config), config, "predictive_mpc")

    assert trace["soc_mj"].between(config.minimum_soc_mj, config.usable_energy_mj).all()
    assert (trace["deploy_kw"] <= config.mgu_k_deploy_limit_kw + 1e-9).all()
    assert (trace["regen_kw"] <= config.mgu_k_regen_limit_kw + 1e-9).all()
    assert set(["segment_type", "aero_mode", "driver_command"]).issubset(trace.columns)


def test_predictive_strategy_reduces_clipping_duration() -> None:
    config = EnergyConfig()
    featured = _synthetic_featured(config)
    fixed = simulate_strategy(featured, config, "fixed_map")
    predictive = simulate_strategy(featured, config, "predictive_mpc")

    fixed_clipping = fixed.loc[fixed["clipping"], "dt_s"].sum()
    predictive_clipping = predictive.loc[predictive["clipping"], "dt_s"].sum()

    assert predictive_clipping < fixed_clipping
    assert float(predictive["soc_mj"].iloc[-1]) >= config.target_finish_soc_mj - 1e-6
    assert set(predictive["driver_command"].unique()).issubset(
        {"THERMAL PROTECT", "REGEN PRIORITY", "ENERGY HOLD", "DEPLOY NOW"}
    )


def test_thermal_limit_reduces_requested_deploy() -> None:
    config = EnergyConfig(initial_battery_temp_c=66.0)
    trace = simulate_strategy(_synthetic_featured(config), config, "fixed_map")
    limited = trace[trace["thermal_limited"]]

    assert not limited.empty
    assert (limited["deploy_kw"] < limited["requested_deploy_kw"]).any()


def test_metrics_are_deterministic() -> None:
    config = EnergyConfig()
    featured = _synthetic_featured(config)
    first = metrics_frame(
        [
            simulate_strategy(featured, config, "fixed_map"),
            simulate_strategy(featured, config, "predictive_mpc"),
        ],
        config,
    )
    second = metrics_frame(
        [
            simulate_strategy(featured, config, "fixed_map"),
            simulate_strategy(featured, config, "predictive_mpc"),
        ],
        config,
    )

    pd.testing.assert_frame_equal(first, second)
    assert {
        "thermal_limited_duration_s",
        "deploy_intensity_pct",
        "clipping_loss_proxy_s",
        "clipping_control_score",
    }.issubset(first.columns)
    assert (first["deploy_intensity_pct"] < 100.0).all()


def test_cli_smoke_generates_report_and_csvs(tmp_path) -> None:
    report = tmp_path / "report.html"

    result = main(
        [
            "--synthetic-only",
            "--output",
            str(report),
        ]
    )

    assert result == 0
    assert report.exists() and report.stat().st_size > 1000
    assert "Race Energy Orchestrator" in report.read_text(encoding="utf-8")
    assert 'href="explorer.html' in report.read_text(encoding="utf-8")
    assert "Canlı karar konsolu" in report.read_text(encoding="utf-8")
    assert "5 Turluk Enerji Planı" in report.read_text(encoding="utf-8")
    assert (tmp_path / "explorer.html").exists()
    assert (tmp_path / "guide.html").exists()
    assert not (tmp_path / "metrics.csv").exists()
    assert not (tmp_path / "strategy_trace.csv").exists()


def test_cli_scenario_overrides_are_reflected_in_report(tmp_path) -> None:
    report = tmp_path / "hot_scenario.html"

    result = main(
        [
            "--synthetic-only",
            "--ambient-temp-c",
            "34",
            "--initial-soc-mj",
            "2.6",
            "--initial-battery-temp-c",
            "52",
            "--horizon-s",
            "38",
            "--output",
            str(report),
        ]
    )

    assert result == 0
    html = (tmp_path / "guide.html").read_text(encoding="utf-8")
    assert "ortam 34.0C" in html
    assert "başlangıç SoC 2.60 MJ" in html


def test_scenario_comparison_covers_expected_conditions() -> None:
    config = EnergyConfig()
    comparison = compare_scenarios(generate_synthetic_lap().frame, config)

    assert comparison["scenario"].tolist() == ["baseline", "hot", "low_soc", "thermal_stress"]
    assert comparison["lap_gain_s"].notna().all()
    assert comparison["clipping_reduction_s"].notna().all()
    assert comparison["orchestrator_end_soc_mj"].between(config.minimum_soc_mj, config.usable_energy_mj).all()


def test_live_decision_feed_exposes_actionable_operator_fields() -> None:
    config = EnergyConfig(initial_battery_temp_c=64.0)
    trace = simulate_strategy(_synthetic_featured(config), config, "predictive_mpc")
    feed = build_live_decision_feed(trace, config)

    assert len(feed) == len(trace)
    assert {"command", "severity", "reason_tr", "reason_en", "confidence_pct"}.issubset(feed.columns)
    assert (feed["confidence_pct"] >= 65.0).all()
    assert (feed["command"] == "THERMAL PROTECT").any()
    assert set(feed["command"].unique()).issubset(
        {"THERMAL PROTECT", "REGEN PRIORITY", "ENERGY HOLD", "DEPLOY NOW"}
    )


def test_stint_plan_builds_bounded_five_lap_energy_budget() -> None:
    config = EnergyConfig()
    trace = simulate_strategy(_synthetic_featured(config), config, "predictive_mpc")
    plan = build_stint_plan(trace, config, current_lap=12, horizon_laps=5, data_source="Synthetic")

    assert plan["current_lap"] == 12
    assert [lap["lap"] for lap in plan["laps"]] == [13, 14, 15, 16, 17]
    assert len(plan["laps"]) == 5
    assert {lap["mode"] for lap in plan["laps"]}.issubset({"BUILD", "NORMAL", "ATTACK", "RECOVER", "COOL"})
    assert "BUILD" in {lap["mode"] for lap in plan["laps"]}
    assert "ATTACK" in {lap["mode"] for lap in plan["laps"]}
    assert all(config.minimum_soc_mj <= lap["target_soc_mj"] <= config.usable_energy_mj for lap in plan["laps"])
    assert all(0.0 <= lap["clipping_risk"] <= 1.0 for lap in plan["laps"])
    assert plan["summary"]["data_basis"] == "synthetic_estimate"
    assert 55.0 <= plan["summary"]["confidence_pct"] <= 94.0


def test_fastapi_decision_contract(monkeypatch) -> None:
    def synthetic_test_loader(year, event, session_name, driver, cache_dir, synthetic_only=False, allow_synthetic_fallback=True):
        return generate_synthetic_lap(track=event, year=year, session_name=session_name, driver=driver)

    monkeypatch.setattr(api, "load_lap_data", synthetic_test_loader)
    api._session.cache_clear()
    client = TestClient(app)

    health = client.get("/api/health")
    session = client.get("/api/session")
    metrics = client.get("/api/metrics")
    selected = client.get(
        "/api/session",
        params={"year": 2026, "event": "Suzuka", "session_name": "R", "driver": "VER"},
    )
    options = client.get("/api/options")
    trace = client.get("/api/trace", params={"event": "Suzuka"})
    selected_trace = client.get(
        "/api/trace",
        params={"year": 2026, "event": "Suzuka", "session_name": "R", "driver": "VER"},
    )
    explorer = client.get(
        "/api/explorer",
        params={"year": 2026, "event": "Suzuka", "session_name": "R", "driver": "VER"},
    )
    monaco_session = client.get("/api/session", params={"year": 2026, "event": "Monaco"})
    monaco_trace = client.get("/api/trace", params={"year": 2026, "event": "Monaco"})
    monaco_scenarios = client.get("/api/scenarios", params={"year": 2026, "event": "Monaco"})
    stint_plan = client.get(
        "/api/stint-plan",
        params={"year": 2026, "event": "Suzuka", "session_name": "R", "driver": "VER", "current_lap": 18},
    )
    decision = client.get("/api/decision", params={"index": 4})
    decisions = client.get("/api/decisions", params={"start": 2, "limit": 3})

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert session.json()["data_source"] == "Synthetic"
    assert session.json()["event"] == "Suzuka"
    assert session.json()["circuit_label"] == "Suzuka-like synthetic proxy"
    assert selected.json()["event"] == "Suzuka"
    assert selected.json()["driver"] == "VER"
    assert "Suzuka" in selected.json()["source_detail"]
    assert options.status_code == 200
    assert options.json()["years"] == [2026]
    assert len(options.json()["events"]) == 24
    assert "Suzuka" in {event["event"] for event in options.json()["events"]}
    yas_option = next(event for event in options.json()["events"] if event["event"] == "Yas Marina")
    assert yas_option["data_available"] is False
    assert client.get("/api/session", params={"year": 2026, "event": "Yas Marina"}).status_code == 409
    assert client.get("/api/session", params={"year": 2025}).status_code == 422
    assert trace.status_code == 200
    assert len(trace.json()["predictive_mpc"]) > 100
    assert selected_trace.status_code == 200
    assert selected_trace.json()["predictive_mpc"][0]["distance_m"] == trace.json()["predictive_mpc"][0]["distance_m"]
    assert selected_trace.json()["predictive_mpc"][0]["speed_kmh"] != trace.json()["predictive_mpc"][0]["speed_kmh"]
    assert "segment_type" in selected_trace.json()["predictive_mpc"][0]
    assert explorer.status_code == 200
    assert {row["strategy"] for row in explorer.json()["rows"]} == {"fixed_map", "predictive_mpc"}
    assert monaco_session.status_code == 200
    assert monaco_session.json()["event"] == "Monaco"
    assert monaco_session.json()["lap_duration_s"] != session.json()["lap_duration_s"]
    assert monaco_trace.status_code == 200
    assert monaco_trace.json()["predictive_mpc"][0]["driver_command"]
    assert monaco_scenarios.status_code == 200
    assert len(monaco_scenarios.json()) == 4
    assert stint_plan.status_code == 200
    assert stint_plan.json()["current_lap"] == 18
    assert len(stint_plan.json()["laps"]) == 5
    assert stint_plan.json()["summary"]["attack_lap"] is not None
    assert metrics.status_code == 200
    assert {row["strategy"] for row in metrics.json()["rows"]} == {"fixed_map", "predictive_mpc"}
    assert decision.json()["decision"]["command"]
    assert len(decisions.json()) == 3


def test_fastapi_never_returns_synthetic_fallback(monkeypatch) -> None:
    def unavailable_loader(*args, **kwargs):
        raise FastF1DataUnavailable("test: no FastF1 data")

    monkeypatch.setattr(api, "load_lap_data", unavailable_loader)
    api._session.cache_clear()
    response = TestClient(app).get("/api/session", params={"year": 2026, "event": "Suzuka"})

    assert response.status_code == 503
    assert "no FastF1 data" in response.json()["detail"]
