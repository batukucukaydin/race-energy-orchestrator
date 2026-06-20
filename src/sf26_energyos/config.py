from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnergyConfig:
    """All public assumptions for the 2026-style ERS simulation."""

    # FIA 2026 Technical Regulations Section C Issue 18 is used as the basis
    # for the MGU-K deploy cap in this public-data prototype.
    mgu_k_deploy_limit_kw: float = 350.0
    mgu_k_regen_limit_kw: float = 350.0

    usable_energy_mj: float = 4.0
    initial_soc_mj: float = 3.15
    minimum_soc_mj: float = 0.18
    target_finish_soc_mj: float = 0.45

    deploy_efficiency: float = 0.96
    regen_efficiency: float = 0.72

    ambient_temp_c: float = 28.0
    initial_battery_temp_c: float = 43.0
    battery_soft_limit_c: float = 58.0
    battery_hard_limit_c: float = 68.0
    battery_cooling_rate: float = 0.018
    deploy_heat_rate: float = 0.000035
    regen_heat_rate: float = 0.000026

    horizon_s: float = 30.0
    long_straight_threshold_m: float = 520.0
    high_value_straight_threshold_m: float = 850.0

    clipping_threshold_kw: float = 18.0
    risk_width_mj: float = 0.38

    deploy_time_gain_s_per_mj_straight: float = 0.080
    deploy_time_gain_s_per_mj_accel: float = 0.068
    deploy_time_gain_s_per_mj_corner: float = 0.030
    regen_time_loss_s_per_mj: float = 0.018
    thermal_time_loss_s_per_s: float = 0.002

    reference_links: tuple[str, str] = (
        "https://www.fia.com/regulation/category/110",
        "https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_c_technical_-_iss_18_-_2026-05-07.pdf",
    )


REQUIRED_INPUT_COLUMNS = [
    "distance_m",
    "time_s",
    "speed_kmh",
    "throttle",
    "brake",
    "gear",
]

MODEL_COLUMNS = [
    "segment_type",
    "aero_mode",
    "deploy_kw",
    "regen_kw",
    "soc_mj",
    "battery_temp_c",
    "clipping_risk",
    "driver_command",
]
