"""Race lap data from FastF1 (timing data exists from 2018 onwards only)."""

from __future__ import annotations

import logging

import pandas as pd

from f1i.config import Settings

logger = logging.getLogger(__name__)

FIRST_SEASON_WITH_TIMING = 2018

# FastF1 column -> our column. Timedeltas become float seconds.
LAP_COLUMNS = {
    "Driver": "driver",
    "DriverNumber": "driver_number",
    "Team": "team",
    "LapNumber": "lap_number",
    "LapTime": "lap_time_s",
    "Sector1Time": "sector1_s",
    "Sector2Time": "sector2_s",
    "Sector3Time": "sector3_s",
    "Stint": "stint",
    "Compound": "compound",
    "TyreLife": "tyre_life",
    "FreshTyre": "fresh_tyre",
    "PitInTime": "pit_in_time_s",
    "PitOutTime": "pit_out_time_s",
    "TrackStatus": "track_status",
    "Position": "position",
    "Deleted": "deleted",
    "IsAccurate": "is_accurate",
}
_INT_COLUMNS = ("lap_number", "stint", "tyre_life", "position")


def load_race_laps(season: int, round_: int, settings: Settings) -> pd.DataFrame:
    if season < FIRST_SEASON_WITH_TIMING:
        raise ValueError(f"FastF1 has no lap timing before {FIRST_SEASON_WITH_TIMING}")
    import fastf1  # heavy import, only when actually loading

    settings.fastf1_cache_path.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(settings.fastf1_cache_path))
    fastf1.set_log_level("WARNING")

    session = fastf1.get_session(season, round_, "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)

    laps = pd.DataFrame(session.laps)[list(LAP_COLUMNS)].rename(columns=LAP_COLUMNS)
    return normalise_laps(laps, season, round_, session.event["EventName"])


def normalise_laps(laps: pd.DataFrame, season: int, round_: int, event_name: str) -> pd.DataFrame:
    laps = laps.copy()
    for col in laps.columns:
        if pd.api.types.is_timedelta64_dtype(laps[col]):
            laps[col] = laps[col].dt.total_seconds()
    for col in _INT_COLUMNS:
        laps[col] = pd.to_numeric(laps[col], errors="coerce").astype("Int64")
    laps["deleted"] = laps["deleted"].astype("boolean").fillna(False)
    laps["is_accurate"] = laps["is_accurate"].astype("boolean").fillna(False)
    laps["track_status"] = laps["track_status"].astype("string")
    laps.insert(0, "event_name", event_name)
    laps.insert(0, "round", round_)
    laps.insert(0, "season", season)
    logger.info("fastf1 laps", extra={"season": season, "round": round_, "rows": len(laps)})
    return laps
