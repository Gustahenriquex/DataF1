"""End-to-end steps behind the CLI: ingest (sources -> raw files -> raw schema) and build (dbt)."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from f1i.config import PROJECT_ROOT, Settings
from f1i.ingest.fastf1_loader import load_race_laps
from f1i.ingest.jolpica import JolpicaClient, driver_standings_frame, results_frame
from f1i.storage import get_engine, replace_partition
from f1i.transform.laps import derive_stints, flag_clean_laps

logger = logging.getLogger(__name__)
DBT_DIR = PROJECT_ROOT / "dbt"

# FastF1 allows 500 calls/h (a full race load uses roughly 20). When the budget runs out we
# wait for the sliding window to free up instead of failing the remaining rounds.
RATE_LIMIT_WAIT_S = 15 * 60
MAX_RATE_LIMIT_WAITS = 8  # up to 2 h per round


def _is_rate_limited(exc: Exception) -> bool:
    message = str(exc)
    return (
        type(exc).__name__ == "RateLimitExceededError"
        or "calls/h" in message
        # FastF1 logs (not raises) a limit hit mid-load, then the laps are missing.
        or "has not been loaded yet" in message
    )


@dataclass
class IngestReport:
    loaded_rounds: list[int] = field(default_factory=list)
    failed_rounds: dict[int, str] = field(default_factory=dict)


def parse_rounds(spec: str | None, available: list[int]) -> list[int]:
    """'1-3,7' -> [1, 2, 3, 7]; None -> every available round."""
    if not spec:
        return sorted(available)
    rounds: set[int] = set()
    for part in spec.split(","):
        start, _, end = part.strip().partition("-")
        rounds.update(range(int(start), int(end or start) + 1))
    return sorted(rounds)


def ingest_season(
    settings: Settings, season: int, rounds_spec: str | None = None, refresh: bool = False
) -> IngestReport:
    engine = get_engine(settings)
    jolpica = JolpicaClient(settings)

    # The season in progress gains results every race weekend: never trust its cache.
    fresh = refresh or season >= date.today().year
    results = results_frame(jolpica.fetch(f"{season}/results", refresh=fresh))
    standings = driver_standings_frame(jolpica.fetch(f"{season}/driverStandings", refresh=fresh))
    replace_partition(engine, results, "jolpica_results", keys=["season"])
    replace_partition(engine, standings, "jolpica_driver_standings", keys=["season"])

    report = IngestReport()
    for round_ in parse_rounds(rounds_spec, results["round"].unique().tolist()):
        try:
            laps = _with_rate_limit_waits(lambda r=round_: _race_laps(settings, season, r, refresh))
            laps = flag_clean_laps(laps)
            replace_partition(engine, laps, "fastf1_laps", keys=["season", "round"])
            replace_partition(
                engine, derive_stints(laps), "fastf1_stints", keys=["season", "round"]
            )
            report.loaded_rounds.append(round_)
        except Exception as exc:  # one bad session must not stop the season
            logger.exception("round failed", extra={"season": season, "round": round_})
            report.failed_rounds[round_] = str(exc).splitlines()[0][:200]
    return report


def _with_rate_limit_waits(
    load: Callable[[], pd.DataFrame],
    sleep: Callable[[float], None] = time.sleep,
    wait_s: float = RATE_LIMIT_WAIT_S,
    max_waits: int = MAX_RATE_LIMIT_WAITS,
) -> pd.DataFrame:
    for attempt in range(max_waits + 1):
        try:
            return load()
        except Exception as exc:
            if attempt == max_waits or not _is_rate_limited(exc):
                raise
            logger.warning(
                "rate limited, waiting", extra={"wait_s": wait_s, "attempt": attempt + 1}
            )
            sleep(wait_s)
    raise AssertionError("unreachable")


def _race_laps(settings: Settings, season: int, round_: int, refresh: bool) -> pd.DataFrame:
    path = settings.raw_dir / "fastf1" / str(season) / f"{round_:02d}_R_laps.parquet"
    if path.exists() and not refresh:
        return pd.read_parquet(path)
    laps = load_race_laps(season, round_, settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    laps.to_parquet(path, index=False)
    return laps


def run_dbt(settings: Settings, args: list[str]) -> bool:
    """Run dbt in-process, passing DB credentials through the environment (profiles.yml)."""
    from dbt.cli.main import dbtRunner

    os.environ.update(
        F1I_DB_HOST=settings.db_host,
        F1I_DB_PORT=str(settings.db_port),
        F1I_DB_NAME=settings.db_name,
        F1I_DB_USER=settings.db_user,
        F1I_DB_PASSWORD=settings.db_password.get_secret_value(),
    )
    result = dbtRunner().invoke(
        [*args, "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)]
    )
    return result.success
