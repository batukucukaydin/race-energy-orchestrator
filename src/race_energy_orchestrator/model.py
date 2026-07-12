from __future__ import annotations

import numpy as np
import pandas as pd

from .config import EnergyConfig
from .strategy import (
    StrategyState,
    driver_command,
    fixed_map_request,
    predict_clipping_risk,
    predictive_mpc_request,
)


def simulate_strategy(frame: pd.DataFrame, config: EnergyConfig, strategy: str) -> pd.DataFrame:
    if strategy not in {"fixed_map", "predictive_mpc"}:
        raise ValueError(f"Unknown strategy {strategy!r}.")

    trace = frame.copy().reset_index(drop=True)
    soc = min(config.initial_soc_mj, config.usable_energy_mj)
    temp_c = config.initial_battery_temp_c

    rows: list[dict[str, float | bool]] = []
    for idx, row in trace.iterrows():
        state = StrategyState(soc_mj=soc, battery_temp_c=temp_c)
        if strategy == "fixed_map":
            requested_deploy_kw, requested_regen_kw = fixed_map_request(row, state, config)
        else:
            requested_deploy_kw, requested_regen_kw = predictive_mpc_request(trace, idx, row, state, config)

        dt = max(float(row["dt_s"]), 0.02)
        deploy_cap_kw, regen_cap_kw = _thermal_caps(temp_c, config)
        deploy_cap_kw = min(deploy_cap_kw, config.mgu_k_deploy_limit_kw)
        regen_cap_kw = min(regen_cap_kw, config.mgu_k_regen_limit_kw)

        requested_deploy_kw = min(float(requested_deploy_kw), config.mgu_k_deploy_limit_kw)
        requested_regen_kw = min(float(requested_regen_kw), config.mgu_k_regen_limit_kw)

        available_energy_kw = max(0.0, (soc - config.minimum_soc_mj) * config.deploy_efficiency / dt * 1000.0)
        actual_deploy_kw = min(requested_deploy_kw, deploy_cap_kw, available_energy_kw)

        capacity_kw = max(0.0, (config.usable_energy_mj - soc) / max(config.regen_efficiency, 1e-6) / dt * 1000.0)
        actual_regen_kw = min(requested_regen_kw, regen_cap_kw, capacity_kw)

        soc = soc - actual_deploy_kw * dt / 1000.0 / config.deploy_efficiency
        soc = soc + actual_regen_kw * dt / 1000.0 * config.regen_efficiency
        soc = float(np.clip(soc, config.minimum_soc_mj, config.usable_energy_mj))

        temp_c = _update_battery_temp(temp_c, actual_deploy_kw, actual_regen_kw, dt, config)
        clipping = requested_deploy_kw - actual_deploy_kw > config.clipping_threshold_kw
        thermal_limited = requested_deploy_kw > deploy_cap_kw + config.clipping_threshold_kw

        rows.append(
            {
                "requested_deploy_kw": requested_deploy_kw,
                "requested_regen_kw": requested_regen_kw,
                "deploy_kw": actual_deploy_kw,
                "regen_kw": actual_regen_kw,
                "soc_mj": soc,
                "battery_temp_c": temp_c,
                "clipping": bool(clipping),
                "thermal_limited": bool(thermal_limited),
            }
        )

    sim = pd.concat([trace, pd.DataFrame(rows)], axis=1)
    sim["strategy"] = strategy
    sim["clipping_risk"] = [
        predict_clipping_risk(sim, idx, float(sim.at[idx, "soc_mj"]), config) for idx in range(len(sim))
    ]
    sim["driver_command"] = sim.apply(driver_command, axis=1)
    sim["speed_loss_kmh"] = np.where(
        sim["clipping"],
        (sim["requested_deploy_kw"] - sim["deploy_kw"]).clip(lower=0.0) / config.mgu_k_deploy_limit_kw * 12.0,
        0.0,
    )
    return sim


def _thermal_caps(temp_c: float, config: EnergyConfig) -> tuple[float, float]:
    if temp_c <= config.battery_soft_limit_c:
        return config.mgu_k_deploy_limit_kw, config.mgu_k_regen_limit_kw
    if temp_c >= config.battery_hard_limit_c:
        return config.mgu_k_deploy_limit_kw * 0.35, config.mgu_k_regen_limit_kw * 0.45

    span = config.battery_hard_limit_c - config.battery_soft_limit_c
    fraction = (temp_c - config.battery_soft_limit_c) / span
    deploy = config.mgu_k_deploy_limit_kw * (1.0 - 0.65 * fraction)
    regen = config.mgu_k_regen_limit_kw * (1.0 - 0.55 * fraction)
    return max(0.0, deploy), max(0.0, regen)


def _update_battery_temp(
    temp_c: float,
    deploy_kw: float,
    regen_kw: float,
    dt_s: float,
    config: EnergyConfig,
) -> float:
    heat = deploy_kw * dt_s * config.deploy_heat_rate + regen_kw * dt_s * config.regen_heat_rate
    cooling = max(0.0, temp_c - config.ambient_temp_c) * config.battery_cooling_rate * dt_s
    return float(temp_c + heat - cooling)
