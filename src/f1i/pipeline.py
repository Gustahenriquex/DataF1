"""End-to-end steps behind the CLI: ingest (sources -> raw files -> raw schema) and build (dbt)."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

import pandas as pd

from f1i.config import PROJECT_ROOT, Settings
from f1i.ingest.fastf1_loader import load_race_laps
from f1i.ingest.jolpica import JolpicaClient, driver_standings_frame, results_frame
from f1i.storage import get_engine, replace_partition
from f1i.transform.laps import derive_stints, flag_clean_laps

logger = logging.getLogger(__name__)
DBT_DIR = PROJECT_ROOT / "dbt"


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

    results = results_frame(jolpica.fetch(f"{season}/results", refresh=refresh))
    standings = driver_standings_frame(jolpica.fetch(f"{season}/driverStandings", refresh=refresh))
    replace_partition(engine, results, "jolpica_results", keys=["season"])
    replace_partition(engine, standings, "jolpica_driver_standings", keys=["season"])

    report = IngestReport()
    for round_ in parse_rounds(rounds_spec, results["round"].unique().tolist()):
        try:
            laps = _race_laps(settings, season, round_, refresh)
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
