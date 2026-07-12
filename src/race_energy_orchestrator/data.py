from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import REQUIRED_INPUT_COLUMNS


@dataclass(frozen=True)
class LapData:
    frame: pd.DataFrame
    source: str
    source_detail: str
    notes: tuple[str, ...] = ()


def load_lap_data(
    year: int,
    event: str,
    session_name: str,
    driver: str,
    cache_dir: str | Path,
    synthetic_only: bool = False,
) -> LapData:
    if synthetic_only:
        return generate_synthetic_lap("Synthetic Monza-like lap requested by CLI.")

    try:
        return _load_fastf1_lap(year, event, session_name, driver, cache_dir)
    except Exception as exc:  # FastF1/network availability is intentionally optional.
        note = f"FastF1 unavailable ({type(exc).__name__}: {exc}). Using deterministic synthetic fallback."
        return generate_synthetic_lap(note)


def _load_fastf1_lap(
    year: int,
    event: str,
    session_name: str,
    driver: str,
    cache_dir: str | Path,
) -> LapData:
    import fastf1

    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_path))

    session = fastf1.get_session(year, event, session_name)
    session.load(laps=True, telemetry=True, weather=False, messages=False)
    laps = session.laps.pick_driver(driver.upper())
    if laps.empty:
        raise ValueError(f"No laps found for driver {driver!r}.")

    lap = laps.pick_fastest()
    telemetry = lap.get_car_data().add_distance()
    frame = _normalise_fastf1_telemetry(telemetry)
    detail = f"FastF1 {year} {event} {session_name}, driver {driver.upper()}, lap {int(lap['LapNumber'])}"
    return LapData(frame=frame, source="FastF1", source_detail=detail)


def _normalise_fastf1_telemetry(telemetry: pd.DataFrame) -> pd.DataFrame:
    frame = pd.DataFrame()
    frame["distance_m"] = telemetry["Distance"].astype(float)

    time_col = telemetry["Time"]
    if np.issubdtype(time_col.dtype, np.timedelta64):
        time_s = time_col.dt.total_seconds()
    else:
        time_s = pd.to_timedelta(time_col).dt.total_seconds()
    frame["time_s"] = time_s - float(time_s.iloc[0])

    frame["speed_kmh"] = telemetry["Speed"].astype(float).clip(lower=1.0)
    frame["throttle"] = _scale_percentage(telemetry["Throttle"])
    frame["brake"] = _normalise_brake(telemetry["Brake"])
    frame["gear"] = telemetry["nGear"].fillna(0).astype(int)
    return _clean_required_frame(frame)


def _scale_percentage(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").fillna(0.0).astype(float)
    if numeric.max() <= 1.5:
        numeric = numeric * 100.0
    return numeric.clip(lower=0.0, upper=100.0)


def _normalise_brake(values: pd.Series) -> pd.Series:
    if values.dtype == bool:
        return values.astype(float) * 100.0
    numeric = pd.to_numeric(values, errors="coerce").fillna(0.0).astype(float)
    if numeric.max() <= 1.5:
        numeric = numeric * 100.0
    return numeric.clip(lower=0.0, upper=100.0)


def _clean_required_frame(frame: pd.DataFrame) -> pd.DataFrame:
    clean = frame[REQUIRED_INPUT_COLUMNS].copy()
    clean = clean.replace([np.inf, -np.inf], np.nan).dropna()
    clean = clean.sort_values("distance_m").drop_duplicates("distance_m")
    clean = clean[clean["time_s"].diff().fillna(0.0) >= 0.0]
    clean = clean.reset_index(drop=True)
    if len(clean) < 20:
        raise ValueError("Telemetry frame is too short after cleaning.")
    return clean


def generate_synthetic_lap(note: str | None = None) -> LapData:
    """Create a deterministic Monza-like lap with long straights and heavy braking."""

    segments: list[dict[str, Any]] = [
        {"name": "Main straight", "type": "straight", "length": 920, "v0": 260, "v1": 335},
        {"name": "T1 braking", "type": "braking", "length": 175, "v0": 335, "v1": 90},
        {"name": "Rettifilo chicane", "type": "slow_corner", "length": 260, "v0": 90, "v1": 135},
        {"name": "Curva Grande run", "type": "straight", "length": 820, "v0": 135, "v1": 320},
        {"name": "Roggia braking", "type": "braking", "length": 145, "v0": 320, "v1": 130},
        {"name": "Roggia", "type": "slow_corner", "length": 265, "v0": 130, "v1": 165},
        {"name": "Lesmo 1", "type": "fast_corner", "length": 330, "v0": 190, "v1": 225},
        {"name": "Lesmo 2", "type": "fast_corner", "length": 310, "v0": 185, "v1": 230},
        {"name": "Serraglio", "type": "straight", "length": 760, "v0": 230, "v1": 325},
        {"name": "Ascari braking", "type": "braking", "length": 165, "v0": 325, "v1": 170},
        {"name": "Ascari", "type": "fast_corner", "length": 470, "v0": 170, "v1": 245},
        {"name": "Back straight", "type": "straight", "length": 1010, "v0": 245, "v1": 338},
        {"name": "Parabolica braking", "type": "braking", "length": 180, "v0": 338, "v1": 165},
        {"name": "Parabolica", "type": "fast_corner", "length": 445, "v0": 165, "v1": 255},
    ]

    rows: list[dict[str, float | int | str]] = []
    distance = 0.0
    time_s = 0.0
    step_m = 5.0
    for segment in segments:
        length = float(segment["length"])
        steps = max(3, int(round(length / step_m)))
        for i in range(steps):
            progress = i / max(1, steps - 1)
            eased = progress * progress * (3.0 - 2.0 * progress)
            speed = float(segment["v0"]) + (float(segment["v1"]) - float(segment["v0"])) * eased
            speed = max(speed, 35.0)
            throttle, brake = _synthetic_controls(str(segment["type"]), progress)
            dt = step_m / (speed / 3.6)
            time_s += dt
            distance += step_m
            rows.append(
                {
                    "distance_m": distance,
                    "time_s": time_s,
                    "speed_kmh": speed,
                    "throttle": throttle,
                    "brake": brake,
                    "gear": _gear_for_speed(speed),
                }
            )

    frame = _clean_required_frame(pd.DataFrame(rows))
    notes = (note,) if note else ()
    return LapData(
        frame=frame,
        source="Synthetic",
        source_detail="Deterministic Monza-like lap with public 2026-style ERS assumptions",
        notes=notes,
    )


def _synthetic_controls(segment_type: str, progress: float) -> tuple[float, float]:
    if segment_type == "braking":
        return 0.0, 100.0 * (1.0 - 0.25 * progress)
    if segment_type == "slow_corner":
        return 28.0 + 52.0 * progress, 0.0
    if segment_type == "fast_corner":
        return 48.0 + 38.0 * progress, 0.0
    return 96.0 + 4.0 * progress, 0.0


def _gear_for_speed(speed_kmh: float) -> int:
    bins = [80, 115, 150, 185, 220, 260, 305]
    return int(np.searchsorted(bins, speed_kmh, side="right") + 1)
