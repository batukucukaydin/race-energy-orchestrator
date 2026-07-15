from __future__ import annotations

import pandas as pd

from race_energy_orchestrator.cli import main
from race_energy_orchestrator.config import EnergyConfig
from race_energy_orchestrator.data import generate_synthetic_lap
from race_energy_orchestrator.metrics import metrics_frame
from race_energy_orchestrator.model import simulate_strategy
from race_energy_orchestrator.segmentation import add_track_features


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
    assert {"thermal_limited_duration_s", "energy_utilization_pct", "clipping_control_score"}.issubset(first.columns)


def test_cli_smoke_generates_report_and_csvs(tmp_path) -> None:
    report = tmp_path / "report.html"
    metrics = tmp_path / "metrics.csv"
    trace = tmp_path / "strategy_trace.csv"

    result = main(
        [
            "--synthetic-only",
            "--output",
            str(report),
            "--metrics-output",
            str(metrics),
            "--trace-output",
            str(trace),
        ]
    )

    assert result == 0
    assert report.exists() and report.stat().st_size > 1000
    assert metrics.exists()
    assert trace.exists()
    assert "Race Energy Orchestrator" in report.read_text(encoding="utf-8")


def test_cli_scenario_overrides_are_reflected_in_report(tmp_path) -> None:
    report = tmp_path / "hot_scenario.html"
    metrics = tmp_path / "metrics.csv"

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
            "--metrics-output",
            str(metrics),
        ]
    )

    assert result == 0
    html = report.read_text(encoding="utf-8")
    assert "ortam 34.0C" in html
    assert "baslangic SoC 2.60 MJ" in html
