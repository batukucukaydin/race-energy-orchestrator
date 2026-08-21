from __future__ import annotations

from dataclasses import replace

import pandas as pd

from .config import EnergyConfig
from .metrics import compute_metrics
from .model import simulate_strategy
from .segmentation import add_track_features


SCENARIO_OVERRIDES: dict[str, dict[str, float]] = {
    "baseline": {},
    "hot": {
        "ambient_temp_c": 36.0,
        "initial_battery_temp_c": 52.0,
        "horizon_s": 36.0,
    },
    "low_soc": {
        "initial_soc_mj": 2.10,
        "horizon_s": 42.0,
    },
    "thermal_stress": {
        "ambient_temp_c": 34.0,
        "initial_battery_temp_c": 64.0,
        "horizon_s": 24.0,
    },
}


def scenario_configs(base_config: EnergyConfig) -> dict[str, EnergyConfig]:
    return {
        name: replace(base_config, **overrides)
        for name, overrides in SCENARIO_OVERRIDES.items()
    }


def compare_scenarios(base_frame: pd.DataFrame, base_config: EnergyConfig) -> pd.DataFrame:
    rows: list[dict[str, float | str | bool]] = []
    for name, config in scenario_configs(base_config).items():
        featured = add_track_features(base_frame, config)
        fixed = simulate_strategy(featured, config, "fixed_map")
        predictive = simulate_strategy(featured, config, "predictive_mpc")
        fixed_metrics = compute_metrics(fixed, config)
        predictive_metrics = compute_metrics(predictive, config)
        lap_gain = fixed_metrics["lap_time_proxy_s"] - predictive_metrics["lap_time_proxy_s"]
        clipping_reduction = fixed_metrics["clipping_duration_s"] - predictive_metrics["clipping_duration_s"]
        rows.append(
            {
                "scenario": name,
                "ambient_temp_c": config.ambient_temp_c,
                "initial_soc_mj": config.initial_soc_mj,
                "initial_battery_temp_c": config.initial_battery_temp_c,
                "horizon_s": config.horizon_s,
                "lap_gain_s": lap_gain,
                "fixed_clipping_s": fixed_metrics["clipping_duration_s"],
                "orchestrator_clipping_s": predictive_metrics["clipping_duration_s"],
                "clipping_reduction_s": clipping_reduction,
                "orchestrator_thermal_limit_s": predictive_metrics["thermal_limited_duration_s"],
                "orchestrator_end_soc_mj": predictive_metrics["end_soc_mj"],
                "orchestrator_max_battery_temp_c": predictive_metrics["max_battery_temp_c"],
                "orchestrator_control_score": predictive_metrics["clipping_control_score"],
                "effective": bool(lap_gain > 0 and clipping_reduction >= 0),
            }
        )
    return pd.DataFrame(rows)
