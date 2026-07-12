from __future__ import annotations

import pandas as pd

from .config import EnergyConfig


def compute_metrics(trace: pd.DataFrame, config: EnergyConfig) -> dict[str, float | str]:
    base_lap_time = float(trace["time_s"].iloc[-1] - trace["time_s"].iloc[0])
    deploy_gain_s = float(
        (
            trace["deploy_kw"]
            * trace["dt_s"]
            / 1000.0
            * trace.apply(lambda row: _gain_factor(row, config), axis=1)
        ).sum()
    )
    regen_loss_s = float((trace["regen_kw"] * trace["dt_s"] / 1000.0 * config.regen_time_loss_s_per_mj).sum())
    clipping_duration_s = float(trace.loc[trace["clipping"], "dt_s"].sum())
    clipping_loss_s = clipping_duration_s * 0.024
    thermal_loss_s = float(trace.loc[trace["thermal_limited"], "dt_s"].sum() * config.thermal_time_loss_s_per_s)

    lap_time_proxy_s = base_lap_time - deploy_gain_s + regen_loss_s + clipping_loss_s + thermal_loss_s
    return {
        "strategy": str(trace["strategy"].iloc[0]),
        "base_lap_time_s": base_lap_time,
        "lap_time_proxy_s": lap_time_proxy_s,
        "deploy_gain_s": deploy_gain_s,
        "regen_loss_s": regen_loss_s,
        "clipping_duration_s": clipping_duration_s,
        "max_speed_loss_kmh": float(trace["speed_loss_kmh"].max()),
        "end_soc_mj": float(trace["soc_mj"].iloc[-1]),
        "unused_energy_mj": max(0.0, float(trace["soc_mj"].iloc[-1]) - config.minimum_soc_mj),
        "max_battery_temp_c": float(trace["battery_temp_c"].max()),
        "mean_clipping_risk": float(trace["clipping_risk"].mean()),
        "max_clipping_risk": float(trace["clipping_risk"].max()),
        "total_deploy_mj": float((trace["deploy_kw"] * trace["dt_s"] / 1000.0).sum()),
        "total_regen_mj": float((trace["regen_kw"] * trace["dt_s"] / 1000.0).sum()),
    }


def metrics_frame(traces: list[pd.DataFrame], config: EnergyConfig) -> pd.DataFrame:
    return pd.DataFrame([compute_metrics(trace, config) for trace in traces])


def _gain_factor(row: pd.Series, config: EnergyConfig) -> float:
    if row["aero_mode"] == "X_MODE":
        return config.deploy_time_gain_s_per_mj_straight * float(row["energy_value"])
    if row["segment_type"] == "acceleration":
        return config.deploy_time_gain_s_per_mj_accel
    if row["segment_type"] in {"slow_corner", "fast_corner"}:
        return config.deploy_time_gain_s_per_mj_corner
    return 0.0
