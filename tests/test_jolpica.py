from __future__ import annotations

import httpx
import pytest

from f1i.config import Settings
from f1i.ingest.jolpica import (
    JolpicaClient,
    RateLimitBudgetExceeded,
    RateLimiter,
    results_frame,
)


def _race(round_: int, drivers: list[str]) -> dict:
    return {
        "season": "2025",
        "round": str(round_),
        "raceName": f"Race {round_}",
        "date": "2025-03-16",
        "Circuit": {"circuitId": "c", "circuitName": "C", "Location": {"country": "X"}},
        "Results": [
            {
                "Driver": {"driverId": d.lower(), "code": d, "givenName": "G", "familyName": d},
                "Constructor": {"constructorId": "t", "name": "T"},
                "grid": "1",
                "position": str(i + 1),
                "positionText": str(i + 1),
                "points": "25",
                "laps": "57",
                "status": "Finished",
            }
            for i, d in enumerate(drivers)
        ],
    }


class _FakeLimiter(RateLimiter):
    def __init__(self) -> None:
        super().__init__(per_second=1000, per_hour=1000, sleep=lambda _s: None)


def test_fetch_paginates_and_caches_raw_pages(settings: Settings) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        calls.append(offset)
        # 150 results -> two pages; race 2 is split across them.
        race = _race(1, ["AAA"]) if offset == 0 else _race(2, ["BBB"])
        return httpx.Response(
            200, json={"MRData": {"total": "150", "RaceTable": {"Races": [race]}}}
        )

    client = JolpicaClient(
        settings,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        limiter=_FakeLimiter(),
    )

    pages = client.fetch("2025/results")
    assert calls == [0, 100]
    assert client.fetch("2025/results") == pages  # second call served from disk
    assert calls == [0, 100]

    df = results_frame(pages)
    assert df[["round", "driver_code", "points"]].to_dict("records") == [
        {"round": 1, "driver_code": "AAA", "points": 25.0},
        {"round": 2, "driver_code": "BBB", "points": 25.0},
    ]


def test_server_errors_are_retried(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter([httpx.Response(503), httpx.Response(200, json={"MRData": {"total": "0"}})])
    client = JolpicaClient(
        settings,
        client=httpx.Client(transport=httpx.MockTransport(lambda _r: next(responses))),
        limiter=_FakeLimiter(),
    )
    monkeypatch.setattr(client._get_page.retry, "sleep", lambda _s: None)

    assert client.fetch("2025/x", refresh=True)[0]["total"] == "0"


def test_rate_limiter_spaces_calls_and_enforces_hourly_budget() -> None:
    now = [0.0]
    slept: list[float] = []

    def sleep(seconds: float) -> None:
        slept.append(seconds)
        now[0] += seconds

    limiter = RateLimiter(per_second=2, per_hour=3, clock=lambda: now[0], sleep=sleep)
    limiter.wait()
    limiter.wait()
    assert slept == [0.5]

    limiter.wait()
    with pytest.raises(RateLimitBudgetExceeded):
        limiter.wait()

    now[0] += 3600
    limiter.wait()  # window slid: budget available again
