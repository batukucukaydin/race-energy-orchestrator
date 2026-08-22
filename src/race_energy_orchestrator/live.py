from __future__ import annotations

import pandas as pd

from .config import EnergyConfig


def build_live_decision_feed(trace: pd.DataFrame, config: EnergyConfig) -> pd.DataFrame:
    """Convert predictive trace samples into operator-facing decisions."""

    rows: list[dict[str, float | str]] = []
    for idx, row in trace.iterrows():
        command, severity, reason_tr, reason_en = _decision_for_row(row, config)
        rows.append(
            {
                "time_s": float(row["time_s"]),
                "distance_m": float(row["distance_m"]),
                "speed_kmh": float(row["speed_kmh"]),
                "segment_type": str(row["segment_type"]),
                "aero_mode": str(row["aero_mode"]),
                "soc_mj": float(row["soc_mj"]),
                "battery_temp_c": float(row["battery_temp_c"]),
                "clipping_risk": float(row["clipping_risk"]),
                "deploy_kw": float(row["deploy_kw"]),
                "regen_kw": float(row["regen_kw"]),
                "command": command,
                "severity": severity,
                "reason_tr": reason_tr,
                "reason_en": reason_en,
                "confidence_pct": _confidence(row, config),
                "next_straight_eta_s": _next_straight_eta(trace, idx),
            }
        )
    return pd.DataFrame(rows)


def _decision_for_row(row: pd.Series, config: EnergyConfig) -> tuple[str, str, str, str]:
    if bool(row["thermal_limited"]) or row["battery_temp_c"] >= config.battery_soft_limit_c:
        return (
            "THERMAL PROTECT",
            "critical",
            "Batarya termal limiti güç kullanımını kısıtlıyor. Deploy azalt ve soğutma payını koru.",
            "Battery thermal limits are constraining power. Reduce deploy and preserve cooling margin.",
        )
    if bool(row["clipping"]):
        return (
            "ENERGY HOLD",
            "warning",
            "Gerçekleşen clipping tespit edildi. Deploy'u koru ve bir sonraki enerji fırsatını bekle.",
            "Actual clipping was detected. Hold deploy and wait for the next energy opportunity.",
        )
    if row["clipping_risk"] >= 0.82:
        return (
            "ENERGY HOLD",
            "advisory",
            "İlerideki enerji ihtiyacı için rezerv korunuyor. Bu, gerçekleşmiş clipping değil, öngörü sinyalidir.",
            "Reserve is being protected for future energy demand. This is a forecast signal, not realized clipping.",
        )
    if row["regen_kw"] >= 220.0:
        return (
            "REGEN PRIORITY",
            "normal",
            "Frenleme enerjisi kullanılabilir. Bir sonraki deploy fırsatı için geri kazanım yap.",
            "Braking energy is available. Recover energy for the next deploy opportunity.",
        )
    if row["deploy_kw"] >= config.operator_deploy_threshold_kw:
        return (
            "DEPLOY NOW",
            "normal",
            "Enerji değeri yüksek bir hızlanma bölgesindesin. Güç dağıtımı tur zamanını destekliyor.",
            "You are in a high-value acceleration zone. Energy deployment supports lap time.",
        )
    return (
        "ENERGY HOLD",
        "normal",
        "Mevcut enerji dengesi hedef finish rezervini koruyor. Yeni bilgi gelene kadar haritayı sabit tut.",
        "The current energy balance preserves the target finish reserve. Hold the map until conditions change.",
    )


def _confidence(row: pd.Series, config: EnergyConfig) -> float:
    thermal_margin = max(0.0, config.battery_soft_limit_c - float(row["battery_temp_c"]))
    temperature_confidence = min(1.0, thermal_margin / 8.0)
    risk_confidence = 1.0 - min(1.0, abs(float(row["clipping_risk"]) - 0.5) * 0.8)
    return round(65.0 + 20.0 * temperature_confidence + 15.0 * risk_confidence, 1)


def _next_straight_eta(trace: pd.DataFrame, idx: int) -> float:
    current_time = float(trace.at[idx, "time_s"])
    future = trace.iloc[idx:]
    candidates = future[future["is_high_value_straight"]]
    if candidates.empty:
        return 0.0
    return max(0.0, float(candidates.iloc[0]["time_s"]) - current_time)
