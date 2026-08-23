from __future__ import annotations

from dataclasses import dataclass
from math import exp

import numpy as np
import pandas as pd

from .config import EnergyConfig


@dataclass(frozen=True)
class StintMode:
    deploy_factor: float
    regen_factor: float
    reason_tr: str
    reason_en: str


MODES = {
    "BUILD": StintMode(
        0.22,
        1.00,
        "Planlanan atak turu için enerji rezervi oluştur.",
        "Build energy reserve for the planned attack lap.",
    ),
    "NORMAL": StintMode(
        0.42,
        0.95,
        "Tur temposunu korurken hedef enerji rezervini tut.",
        "Maintain lap pace while protecting the target energy reserve.",
    ),
    "ATTACK": StintMode(
        0.68,
        0.85,
        "Hazırlanan enerjiyi yüksek değerli hızlanma bölgelerinde kullan.",
        "Use the prepared energy in high-value acceleration zones.",
    ),
    "RECOVER": StintMode(
        0.25,
        1.00,
        "Atak sonrası enerji deposunu ve termal payı geri kazan.",
        "Recover the energy store and thermal headroom after the attack.",
    ),
    "COOL": StintMode(
        0.18,
        0.80,
        "Batarya sıcaklığı için deploy yükünü sınırla.",
        "Limit deployment load to control battery temperature.",
    ),
}


def build_stint_plan(
    trace: pd.DataFrame,
    config: EnergyConfig,
    *,
    current_lap: int = 1,
    horizon_laps: int = 5,
    data_source: str = "Synthetic",
) -> dict[str, object]:
    """Build a deterministic multi-lap energy budget from one representative lap."""

    if trace.empty:
        raise ValueError("A non-empty predictive trace is required.")
    if current_lap < 1:
        raise ValueError("current_lap must be at least 1.")
    if not 3 <= horizon_laps <= 10:
        raise ValueError("horizon_laps must be between 3 and 10.")

    lap_time_s = max(float(trace["time_s"].iloc[-1] - trace["time_s"].iloc[0]), 1.0)
    baseline_deploy_mj = float((trace["deploy_kw"] * trace["dt_s"] / 1000.0).sum())
    baseline_regen_mj = float((trace["regen_kw"] * trace["dt_s"] / 1000.0).sum())
    start_soc_mj = float(np.clip(trace["soc_mj"].iloc[-1], config.minimum_soc_mj, config.usable_energy_mj))
    start_temp_c = float(trace["battery_temp_c"].iloc[-1])
    attack_step = min(3, horizon_laps)
    attack_mode = MODES["ATTACK"]
    attack_regen_gain_mj = baseline_regen_mj * attack_mode.regen_factor * config.regen_efficiency
    attack_draw_mj = baseline_deploy_mj * attack_mode.deploy_factor / max(config.deploy_efficiency, 1e-6)
    attack_required_soc_mj = float(
        np.clip(
            config.target_finish_soc_mj + attack_draw_mj - attack_regen_gain_mj,
            config.target_finish_soc_mj,
            config.usable_energy_mj,
        )
    )

    planned_laps: list[dict[str, float | int | str]] = []
    soc_mj = start_soc_mj
    temp_c = start_temp_c
    attack_lap: int | None = None
    cumulative_delta_s = 0.0
    normal_deploy_mj = baseline_deploy_mj * MODES["NORMAL"].deploy_factor
    normal_regen_mj = baseline_regen_mj * MODES["NORMAL"].regen_factor

    for step in range(1, horizon_laps + 1):
        lap_number = current_lap + step
        thermal_headroom_c = config.battery_soft_limit_c - temp_c
        if thermal_headroom_c < 3.0:
            mode_name = "COOL"
        elif step == attack_step and soc_mj >= attack_required_soc_mj - 0.05:
            mode_name = "ATTACK"
            attack_lap = lap_number
        elif step < attack_step and soc_mj < attack_required_soc_mj:
            mode_name = "BUILD"
        elif attack_lap is not None and step == attack_step + 1:
            mode_name = "RECOVER"
        elif attack_lap is None and step >= attack_step and soc_mj < attack_required_soc_mj:
            mode_name = "BUILD"
        else:
            mode_name = "NORMAL"

        mode = MODES[mode_name]
        requested_deploy_mj = baseline_deploy_mj * mode.deploy_factor
        requested_regen_mj = baseline_regen_mj * mode.regen_factor
        requested_regen_gain_mj = requested_regen_mj * config.regen_efficiency
        available_deploy_mj = max(
            0.0,
            (soc_mj - config.minimum_soc_mj + requested_regen_gain_mj) * config.deploy_efficiency,
        )
        deploy_mj = min(requested_deploy_mj, available_deploy_mj)
        regen_capacity_gain_mj = max(0.0, config.usable_energy_mj - soc_mj + deploy_mj / config.deploy_efficiency)
        if step < attack_step:
            target_soc_cap_mj = min(config.usable_energy_mj, attack_required_soc_mj + 0.35)
        elif mode_name == "ATTACK":
            target_soc_cap_mj = config.usable_energy_mj
        else:
            target_soc_cap_mj = min(
                config.usable_energy_mj,
                max(attack_required_soc_mj, config.target_finish_soc_mj + 0.55),
            )
        regen_target_gain_mj = max(0.0, target_soc_cap_mj - soc_mj + deploy_mj / config.deploy_efficiency)
        regen_gain_mj = min(requested_regen_gain_mj, regen_capacity_gain_mj, regen_target_gain_mj)
        regen_mj = regen_gain_mj / max(config.regen_efficiency, 1e-6)
        end_soc_mj = float(
            np.clip(
                soc_mj - deploy_mj / max(config.deploy_efficiency, 1e-6) + regen_gain_mj,
                config.minimum_soc_mj,
                config.usable_energy_mj,
            )
        )
        clipping_risk = float(
            np.clip(
                (requested_deploy_mj - deploy_mj) / max(requested_deploy_mj, config.risk_width_mj),
                0.0,
                1.0,
            )
        )
        if step < attack_step:
            reserve_shortfall = max(0.0, attack_required_soc_mj - end_soc_mj)
            clipping_risk = max(
                clipping_risk,
                min(1.0, reserve_shortfall / max(attack_required_soc_mj, config.risk_width_mj)),
            )

        cooling = exp(-config.battery_cooling_rate * lap_time_s)
        deploy_heat_c = deploy_mj * 1000.0 * config.deploy_heat_rate
        regen_heat_c = regen_mj * 1000.0 * config.regen_heat_rate
        end_temp_c = float(
            np.clip(
                config.ambient_temp_c + (temp_c - config.ambient_temp_c) * cooling + deploy_heat_c + regen_heat_c,
                config.ambient_temp_c,
                config.battery_hard_limit_c,
            )
        )
        lap_delta_s = (
            (normal_deploy_mj - deploy_mj) * config.deploy_time_gain_s_per_mj_straight
            + (regen_mj - normal_regen_mj) * config.regen_time_loss_s_per_mj
        )
        cumulative_delta_s += lap_delta_s

        planned_laps.append(
            {
                "lap": lap_number,
                "mode": mode_name,
                "start_soc_mj": round(soc_mj, 4),
                "target_soc_mj": round(end_soc_mj, 4),
                "target_soc_pct": round(_soc_pct(end_soc_mj, config), 2),
                "deploy_budget_mj": round(deploy_mj, 4),
                "regen_budget_mj": round(regen_mj, 4),
                "battery_temp_c": round(end_temp_c, 3),
                "clipping_risk": round(clipping_risk, 4),
                "lap_time_delta_s": round(lap_delta_s, 4),
                "estimated_lap_time_s": round(lap_time_s + lap_delta_s, 4),
                "reason_tr": mode.reason_tr,
                "reason_en": mode.reason_en,
            }
        )
        soc_mj = end_soc_mj
        temp_c = end_temp_c

    source_is_synthetic = data_source.strip().lower().startswith("synthetic")
    risk_penalty = max(float(lap["clipping_risk"]) for lap in planned_laps) * 16.0
    confidence_pct = float(np.clip((76.0 if source_is_synthetic else 88.0) - risk_penalty, 55.0, 94.0))
    state_name = _state_name(start_soc_mj, start_temp_c, attack_required_soc_mj, config)
    return {
        "current_lap": current_lap,
        "horizon_laps": horizon_laps,
        "state": {
            "name": state_name,
            "soc_mj": round(start_soc_mj, 4),
            "soc_pct": round(_soc_pct(start_soc_mj, config), 2),
            "battery_temp_c": round(start_temp_c, 3),
            "thermal_headroom_c": round(config.battery_soft_limit_c - start_temp_c, 3),
            "attack_required_soc_mj": round(attack_required_soc_mj, 4),
        },
        "summary": {
            "attack_lap": attack_lap,
            "projected_finish_soc_mj": round(soc_mj, 4),
            "projected_finish_soc_pct": round(_soc_pct(soc_mj, config), 2),
            "cumulative_lap_time_delta_s": round(cumulative_delta_s, 4),
            "confidence_pct": round(confidence_pct, 1),
            "data_basis": "synthetic_estimate" if source_is_synthetic else "fastf1_derived_estimate",
        },
        "laps": planned_laps,
    }


def _soc_pct(soc_mj: float, config: EnergyConfig) -> float:
    span = max(config.usable_energy_mj - config.minimum_soc_mj, 1e-6)
    return float(np.clip((soc_mj - config.minimum_soc_mj) / span * 100.0, 0.0, 100.0))


def _state_name(soc_mj: float, temp_c: float, attack_required_soc_mj: float, config: EnergyConfig) -> str:
    if temp_c >= config.battery_soft_limit_c - 3.0:
        return "THERMAL MANAGEMENT"
    if soc_mj >= attack_required_soc_mj:
        return "ATTACK READY"
    return "ENERGY BUILD"
