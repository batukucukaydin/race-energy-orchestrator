from __future__ import annotations

import pandas as pd

from sf26_energyos.cli import main
from sf26_energyos.config import EnergyConfig
from sf26_energyos.data import generate_synthetic_lap
from sf26_energyos.metrics import metrics_frame
from sf26_energyos.model import simulate_strategy
from sf26_energyos.segmentation import add_track_features


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
