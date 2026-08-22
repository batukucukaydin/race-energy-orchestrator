from __future__ import annotations

from dataclasses import dataclass
from datetime import date


SUPPORTED_YEAR = 2026

# Official 2026 F1 venues. Event names follow FastF1's public event naming
# where possible; synthetic fallback supports the same keys when data is not cached.
F1_2026_EVENTS = (
    ("Melbourne", "Australia · Melbourne"),
    ("Shanghai", "China · Shanghai"),
    ("Suzuka", "Japan · Suzuka"),
    ("Sakhir", "Bahrain · Sakhir"),
    ("Jeddah", "Saudi Arabia · Jeddah"),
    ("Miami", "United States · Miami"),
    ("Montreal", "Canada · Montreal"),
    ("Monaco", "Monaco"),
    ("Barcelona-Catalunya", "Spain · Barcelona-Catalunya"),
    ("Spielberg", "Austria · Spielberg"),
    ("Silverstone", "United Kingdom · Silverstone"),
    ("Spa-Francorchamps", "Belgium · Spa-Francorchamps"),
    ("Budapest", "Hungary · Budapest"),
    ("Zandvoort", "Netherlands · Zandvoort"),
    ("Monza", "Italy · Monza"),
    ("Madrid", "Spain · Madrid"),
    ("Baku", "Azerbaijan · Baku"),
    ("Singapore", "Singapore"),
    ("Austin", "United States · Austin"),
    ("Mexico City", "Mexico · Mexico City"),
    ("São Paulo", "Brazil · São Paulo"),
    ("Las Vegas", "United States · Las Vegas"),
    ("Lusail", "Qatar · Lusail"),
    ("Yas Marina", "United Arab Emirates · Abu Dhabi"),
)

F1_2026_RACE_END_DATES = {
    "Melbourne": date(2026, 3, 8),
    "Shanghai": date(2026, 3, 15),
    "Suzuka": date(2026, 3, 29),
    "Sakhir": date(2026, 4, 12),
    "Jeddah": date(2026, 4, 19),
    "Miami": date(2026, 5, 3),
    "Montreal": date(2026, 5, 24),
    "Monaco": date(2026, 6, 7),
    "Barcelona-Catalunya": date(2026, 6, 14),
    "Spielberg": date(2026, 6, 28),
    "Silverstone": date(2026, 7, 5),
    "Spa-Francorchamps": date(2026, 7, 19),
    "Budapest": date(2026, 7, 26),
    "Zandvoort": date(2026, 8, 23),
    "Monza": date(2026, 9, 6),
    "Madrid": date(2026, 9, 13),
    "Baku": date(2026, 9, 27),
    "Singapore": date(2026, 10, 11),
    "Austin": date(2026, 10, 25),
    "Mexico City": date(2026, 11, 1),
    "São Paulo": date(2026, 11, 8),
    "Las Vegas": date(2026, 11, 21),
    "Lusail": date(2026, 11, 29),
    "Yas Marina": date(2026, 12, 6),
}


def event_data_available(event: str, as_of: date | None = None) -> bool:
    race_end = F1_2026_RACE_END_DATES.get(event)
    return race_end is not None and race_end <= (as_of or date.today())


@dataclass(frozen=True)
class EnergyConfig:
    """All public assumptions for the 2026-style ERS simulation."""

    # FIA 2026 Technical Regulations Section C Issue 18 is used as the basis
    # for the MGU-K deploy cap in this public-data prototype.
    mgu_k_deploy_limit_kw: float = 350.0
    mgu_k_regen_limit_kw: float = 350.0
    operator_deploy_threshold_kw: float = 200.0

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
