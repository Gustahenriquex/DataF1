"""Lap-level transformations: representative ("clean") laps and stint summaries.

A clean lap is one that reflects race pace. Excluded:
  * lap 1 (standing start) and laps without a time;
  * in-laps and out-laps (pit stop time is not pace);
  * any lap not fully under green flag (track status must be exactly "1");
  * laps deleted by race control or flagged inaccurate by FastF1;
  * outliers slower than `slow_factor` x the driver's own median (traffic, damage, errors).
"""

from __future__ import annotations

import pandas as pd

RACE_KEYS = ["season", "round"]
DEFAULT_SLOW_FACTOR = 1.07


def flag_clean_laps(laps: pd.DataFrame, slow_factor: float = DEFAULT_SLOW_FACTOR) -> pd.DataFrame:
    laps = laps.copy()
    candidate = (
        laps["lap_time_s"].notna()
        & (laps["lap_number"] > 1)
        & laps["pit_in_time_s"].isna()
        & laps["pit_out_time_s"].isna()
        & (laps["track_status"] == "1")
        & ~laps["deleted"].astype(bool)
        & laps["is_accurate"].astype(bool)
    ).fillna(False)

    driver_median = (
        laps["lap_time_s"].where(candidate).groupby([laps[k] for k in [*RACE_KEYS, "driver"]])
    ).transform("median")
    laps["is_clean"] = candidate & (laps["lap_time_s"] <= slow_factor * driver_median).fillna(False)
    return laps


def derive_stints(laps: pd.DataFrame) -> pd.DataFrame:
    """One row per driver stint: compound, lap range and tyre age at the start."""
    keys = [*RACE_KEYS, "driver", "stint"]
    stints = (
        laps.dropna(subset=["stint"])
        .sort_values([*keys, "lap_number"])
        .groupby(keys, as_index=False)
        .agg(
            team=("team", "first"),
            compound=("compound", "first"),
            start_lap=("lap_number", "min"),
            end_lap=("lap_number", "max"),
            laps=("lap_number", "count"),
            tyre_life_start=("tyre_life", "min"),
            fresh_tyre=("fresh_tyre", "first"),
            clean_laps=("is_clean", "sum"),
        )
    )
    stints["compound"] = stints["compound"].fillna("UNKNOWN")
    return stints
