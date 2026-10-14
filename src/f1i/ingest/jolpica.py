"""Jolpica-F1 (Ergast-compatible) client: throttled, retried, paginated, cached to disk."""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from collections.abc import Callable
from typing import Any

import httpx
import pandas as pd
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from f1i import __version__
from f1i.config import Settings

logger = logging.getLogger(__name__)
PAGE_SIZE = 100


class RateLimitBudgetExceeded(RuntimeError):
    """Raised instead of silently sleeping for up to an hour."""


class RateLimiter:
    """Enforces a minimum gap between calls and an hourly budget (sliding window)."""

    def __init__(
        self,
        per_second: float,
        per_hour: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.min_interval = 1.0 / per_second
        self.per_hour = per_hour
        self._calls: deque[float] = deque()
        self._clock = clock
        self._sleep = sleep

    def wait(self) -> None:
        now = self._clock()
        while self._calls and now - self._calls[0] >= 3600:
            self._calls.popleft()
        if len(self._calls) >= self.per_hour:
            raise RateLimitBudgetExceeded(
                f"{self.per_hour} Jolpica calls in the last hour; retry later (pages are cached)"
            )
        if self._calls and (gap := now - self._calls[-1]) < self.min_interval:
            self._sleep(self.min_interval - gap)
            now = self._clock()
        self._calls.append(now)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


class JolpicaClient:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        limiter: RateLimiter | None = None,
    ) -> None:
        self.base_url = settings.jolpica_base_url
        self.raw_dir = settings.raw_dir / "jolpica"
        self._http = client or httpx.Client(
            timeout=settings.http_timeout_seconds,
            headers={"User-Agent": f"f1-intelligence/{__version__} (portfolio project)"},
        )
        self._limiter = limiter or RateLimiter(
            settings.jolpica_max_requests_per_second, settings.jolpica_max_requests_per_hour
        )

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, max=30),
        reraise=True,
    )
    def _get_page(self, path: str, offset: int) -> dict[str, Any]:
        self._limiter.wait()
        response = self._http.get(
            f"{self.base_url}/{path}/", params={"limit": PAGE_SIZE, "offset": offset}
        )
        response.raise_for_status()
        return response.json()["MRData"]

    def fetch(self, path: str, *, refresh: bool = False) -> list[dict[str, Any]]:
        """Every page of `path` (e.g. "2025/results"). Raw pages are kept on disk as-is."""
        cache_file = self.raw_dir / f"{path.replace('/', '_')}.json"
        if cache_file.exists() and not refresh:
            return json.loads(cache_file.read_text(encoding="utf-8"))

        pages: list[dict[str, Any]] = []
        offset, total = 0, None
        while total is None or offset < total:
            page = self._get_page(path, offset)
            pages.append(page)
            total = int(page["total"])
            offset += PAGE_SIZE

        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(pages), encoding="utf-8")
        logger.info("jolpica fetched", extra={"path": path, "pages": len(pages), "total": total})
        return pages


def _driver_fields(driver: dict[str, Any]) -> dict[str, Any]:
    return {
        "driver_id": driver["driverId"],
        "driver_code": driver.get("code"),
        "driver_name": f"{driver['givenName']} {driver['familyName']}",
    }


def results_frame(pages: list[dict[str, Any]]) -> pd.DataFrame:
    """One row per driver per race. Races split across pages are handled naturally."""
    rows = []
    for page in pages:
        for race in page["RaceTable"]["Races"]:
            circuit = race["Circuit"]
            for res in race["Results"]:
                rows.append(
                    {
                        "season": int(race["season"]),
                        "round": int(race["round"]),
                        "race_name": race["raceName"],
                        "race_date": race["date"],
                        "circuit_id": circuit["circuitId"],
                        "circuit_name": circuit["circuitName"],
                        "country": circuit["Location"]["country"],
                        **_driver_fields(res["Driver"]),
                        "constructor_id": res["Constructor"]["constructorId"],
                        "constructor_name": res["Constructor"]["name"],
                        "grid": int(res["grid"]),
                        "position": int(res["position"]),
                        "position_text": res["positionText"],
                        "points": float(res["points"]),
                        "laps": int(res["laps"]),
                        "status": res["status"],
                    }
                )
    return pd.DataFrame(rows)


def driver_standings_frame(pages: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for page in pages:
        for standings in page["StandingsTable"]["StandingsLists"]:
            for item in standings["DriverStandings"]:
                constructors = item.get("Constructors") or [{}]
                rows.append(
                    {
                        "season": int(standings["season"]),
                        "after_round": int(standings["round"]),
                        "position": int(item["position"]) if "position" in item else None,
                        "points": float(item["points"]),
                        "wins": int(item["wins"]),
                        **_driver_fields(item["Driver"]),
                        "constructor_name": constructors[-1].get("name"),
                    }
                )
    return pd.DataFrame(rows)
