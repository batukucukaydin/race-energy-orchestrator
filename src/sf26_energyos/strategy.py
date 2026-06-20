from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import EnergyConfig


@dataclass
class StrategyState:
    soc_mj: float
    battery_temp_c: float


def fixed_map_request(row: pd.Series, state: StrategyState, config: EnergyConfig) -> tuple[float, float]:
    regen_kw = _regen_request(row, config, aggressive=False)
    deploy_kw = 0.0

    if row["brake"] <= 5.0 and row["throttle"] >= 72.0:
        if row["aero_mode"] == "X_MODE":
            deploy_kw = 350.0 if row["is_long_straight"] else 310.0
        elif row["segment_type"] == "acceleration":
            deploy_kw = 250.0
        elif row["segment_type"] in {"slow_corner", "fast_corner"}:
            deploy_kw = 150.0

    return min(deploy_kw, config.mgu_k_deploy_limit_kw), regen_kw


def predictive_mpc_request(
    frame: pd.DataFrame,
    idx: int,
    row: pd.Series,
    state: StrategyState,
    config: EnergyConfig,
) -> tuple[float, float]:
    regen_kw = _regen_request(row, config, aggressive=True)

    if row["brake"] > 5.0 or row["throttle"] < 20.0:
        return 0.0, regen_kw

    deploy_limit = config.mgu_k_deploy_limit_kw
    if state.soc_mj <= config.minimum_soc_mj + 0.05:
        return 0.0, regen_kw

    reserve_mj = _reserve_requirement(frame, idx, state.soc_mj, config)
    available_for_deploy_mj = max(0.0, state.soc_mj - config.minimum_soc_mj - reserve_mj)

    if row["is_long_straight"]:
        remaining_time = max(float(row["remaining_straight_time_s"]), float(row["dt_s"]), 0.1)
        usable_mj = max(0.0, state.soc_mj - config.minimum_soc_mj - 0.10)
        smooth_kw = usable_mj * config.deploy_efficiency / remaining_time * 1000.0
        return float(np.clip(smooth_kw, 0.0, deploy_limit)), regen_kw

    if row["aero_mode"] == "X_MODE":
        if reserve_mj > 0.0 and available_for_deploy_mj < 0.25:
            deploy_kw = 80.0
        else:
            deploy_kw = 260.0 if row["energy_value"] >= 1.0 else 210.0
        return min(deploy_kw, deploy_limit), regen_kw

    if row["segment_type"] == "acceleration":
        deploy_kw = 165.0 if reserve_mj > 0.0 else 220.0
    elif row["segment_type"] in {"slow_corner", "fast_corner"}:
        deploy_kw = 70.0 if reserve_mj > 0.0 else 120.0
    else:
        deploy_kw = 0.0

    return min(deploy_kw, deploy_limit), regen_kw


def predict_clipping_risk(frame: pd.DataFrame, idx: int, soc_mj: float, config: EnergyConfig) -> float:
    need_mj, regen_mj = _future_long_straight_need(frame, idx, config)
    if need_mj <= 0.0:
        return 0.03
    available_mj = max(0.0, soc_mj - config.minimum_soc_mj) + regen_mj
    shortfall = need_mj - available_mj
    return float(1.0 / (1.0 + math.exp(-shortfall / config.risk_width_mj)))


def driver_command(row: pd.Series) -> str:
    if row["clipping_risk"] >= 0.76 and row["segment_type"] == "braking":
        return "RECHARGE +1"
    if row["clipping_risk"] >= 0.70 and row["aero_mode"] != "X_MODE":
        return "ENERGY HOLD"
    if row["deploy_kw"] >= 310.0 and row["is_high_value_straight"]:
        return "DEPLOY ATTACK"
    if row["deploy_kw"] >= 260.0 and row["aero_mode"] == "X_MODE":
        return "OVERTAKE READY"
    if row["regen_kw"] >= 260.0:
        return "RECHARGE +1"
    if row["deploy_kw"] <= 90.0 and row["clipping_risk"] >= 0.45:
        return "SAVE ENERGY"
    return "ENERGY HOLD"


def _regen_request(row: pd.Series, config: EnergyConfig, aggressive: bool) -> float:
    if row["brake"] > 5.0:
        scale = 0.95 if aggressive else 0.78
        return min(config.mgu_k_regen_limit_kw, config.mgu_k_regen_limit_kw * scale * row["brake"] / 100.0)
    if aggressive and row["throttle"] < 8.0 and row["speed_kmh"] > 190.0:
        return min(55.0, config.mgu_k_regen_limit_kw)
    return 0.0


def _reserve_requirement(frame: pd.DataFrame, idx: int, soc_mj: float, config: EnergyConfig) -> float:
    row = frame.iloc[idx]
    if row["is_long_straight"]:
        return 0.0

    current_time = float(row["time_s"])
    horizon_end = current_time + config.horizon_s
    future = frame.iloc[idx:]
    candidates = future[
        (future["is_long_straight"])
        & (future["straight_group_start_time_s"] >= current_time)
        & (future["straight_group_start_time_s"] <= horizon_end)
    ]
    if candidates.empty:
        finish_fraction = current_time / max(float(frame["time_s"].iloc[-1]), 1.0)
        return max(0.0, config.target_finish_soc_mj * finish_fraction)

    group = candidates.iloc[0]
    duration_s = float(group["straight_group_duration_s"])
    straight_need_mj = duration_s * config.mgu_k_deploy_limit_kw / 1000.0 / config.deploy_efficiency
    reserve = min(config.usable_energy_mj * 0.72, straight_need_mj * 0.74)
    return max(0.0, min(reserve, config.usable_energy_mj - config.minimum_soc_mj, soc_mj))


def _future_long_straight_need(frame: pd.DataFrame, idx: int, config: EnergyConfig) -> tuple[float, float]:
    row = frame.iloc[idx]
    current_time = float(row["time_s"])

    if row["is_long_straight"]:
        duration_s = max(float(row["remaining_straight_time_s"]), float(row["dt_s"]))
        start_time = current_time
    else:
        future = frame.iloc[idx:]
        horizon_end = current_time + config.horizon_s
        candidates = future[
            (future["is_long_straight"])
            & (future["straight_group_start_time_s"] >= current_time)
            & (future["straight_group_start_time_s"] <= horizon_end)
        ]
        if candidates.empty:
            return 0.0, 0.0
        first = candidates.iloc[0]
        duration_s = float(first["straight_group_duration_s"])
        start_time = float(first["straight_group_start_time_s"])

    need_mj = min(
        config.usable_energy_mj,
        duration_s * config.mgu_k_deploy_limit_kw / 1000.0 / config.deploy_efficiency,
    )
    before = frame.iloc[idx:]
    before = before[before["time_s"] < start_time]
    regen_potential_mj = float(
        (
            np.minimum(config.mgu_k_regen_limit_kw, config.mgu_k_regen_limit_kw * before["brake"] / 100.0)
            * before["dt_s"]
            / 1000.0
            * config.regen_efficiency
        ).sum()
    )
    return need_mj, min(regen_potential_mj, config.usable_energy_mj)
