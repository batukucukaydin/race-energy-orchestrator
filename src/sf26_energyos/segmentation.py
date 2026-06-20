from __future__ import annotations

import numpy as np
import pandas as pd

from .config import EnergyConfig


def add_track_features(frame: pd.DataFrame, config: EnergyConfig) -> pd.DataFrame:
    data = frame.copy()
    dt = data["time_s"].diff().fillna(data["time_s"].diff().median()).clip(lower=0.02)
    ds = data["distance_m"].diff().fillna(data["distance_m"].diff().median()).clip(lower=0.0)
    accel_kmh_s = data["speed_kmh"].diff().fillna(0.0) / dt

    braking = (data["brake"] > 8.0) | (accel_kmh_s < -25.0)
    slow_corner = (~braking) & (data["speed_kmh"] < 155.0) & (data["throttle"] < 88.0)
    fast_corner = (~braking) & (data["speed_kmh"] >= 155.0) & (data["throttle"] < 90.0)
    acceleration = (~braking) & (data["throttle"] >= 82.0) & (accel_kmh_s > 3.0) & (data["speed_kmh"] < 255.0)

    segment_type = np.select(
        [braking, slow_corner, fast_corner, acceleration],
        ["braking", "slow_corner", "fast_corner", "acceleration"],
        default="straight",
    )
    data["segment_type"] = segment_type

    x_mode = (
        (data["throttle"] >= 82.0)
        & (data["brake"] < 5.0)
        & (data["speed_kmh"] >= 175.0)
        & data["segment_type"].isin(["straight", "acceleration"])
    )
    data["aero_mode"] = np.where(x_mode, "X_MODE", "Z_MODE")
    data["dt_s"] = dt.astype(float)
    data["ds_m"] = ds.astype(float)
    data["accel_kmh_s"] = accel_kmh_s.astype(float)

    data = _add_straight_groups(data, config)
    data["energy_value"] = data.apply(_energy_value, axis=1)
    return data.reset_index(drop=True)


def _add_straight_groups(data: pd.DataFrame, config: EnergyConfig) -> pd.DataFrame:
    x_mode = data["aero_mode"].eq("X_MODE")
    group_token = x_mode.ne(x_mode.shift(fill_value=False)).cumsum()
    group_id = np.where(x_mode, group_token, -1)
    data["straight_group_id"] = group_id.astype(int)
    data["straight_group_length_m"] = 0.0
    data["straight_group_duration_s"] = 0.0
    data["straight_group_start_time_s"] = np.nan
    data["straight_group_end_time_s"] = np.nan
    data["remaining_straight_time_s"] = 0.0
    data["is_long_straight"] = False
    data["is_high_value_straight"] = False

    for gid, group in data[data["straight_group_id"] >= 0].groupby("straight_group_id"):
        idx = group.index
        length = float(group["distance_m"].max() - group["distance_m"].min() + group["ds_m"].median())
        duration = float(group["time_s"].max() - group["time_s"].min() + group["dt_s"].median())
        start_time = float(group["time_s"].min())
        end_time = float(group["time_s"].max())
        data.loc[idx, "straight_group_length_m"] = length
        data.loc[idx, "straight_group_duration_s"] = duration
        data.loc[idx, "straight_group_start_time_s"] = start_time
        data.loc[idx, "straight_group_end_time_s"] = end_time
        data.loc[idx, "remaining_straight_time_s"] = (end_time - data.loc[idx, "time_s"]).clip(lower=0.0)
        data.loc[idx, "is_long_straight"] = length >= config.long_straight_threshold_m
        data.loc[idx, "is_high_value_straight"] = length >= config.high_value_straight_threshold_m

    return data


def _energy_value(row: pd.Series) -> float:
    if row["is_high_value_straight"]:
        return 1.35
    if row["is_long_straight"]:
        return 1.15
    if row["segment_type"] == "acceleration":
        return 1.05
    if row["segment_type"] in {"slow_corner", "fast_corner"}:
        return 0.55
    if row["segment_type"] == "braking":
        return 0.0
    return 0.90
