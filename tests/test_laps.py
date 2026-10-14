from __future__ import annotations

import pandas as pd
import pytest

from f1i.pipeline import parse_rounds
from f1i.transform.laps import derive_stints, flag_clean_laps


def _laps(**overrides: list) -> pd.DataFrame:
    """Six laps of one driver; lap 1 is the start, the rest clean unless overridden."""
    base = {
        "season": [2025] * 6,
        "round": [1] * 6,
        "driver": ["AAA"] * 6,
        "team": ["T"] * 6,
        "lap_number": [1, 2, 3, 4, 5, 6],
        "lap_time_s": [95.0, 90.0, 90.2, 90.4, 90.1, 90.3],
        "pit_in_time_s": [None] * 6,
        "pit_out_time_s": [None] * 6,
        "track_status": ["1"] * 6,
        "deleted": [False] * 6,
        "is_accurate": [True] * 6,
        "stint": [1, 1, 1, 2, 2, 2],
        "compound": ["SOFT"] * 3 + ["HARD"] * 3,
        "tyre_life": [1, 2, 3, 1, 2, 3],
        "fresh_tyre": [True] * 6,
    }
    base.update(overrides)
    return pd.DataFrame(base)


def test_clean_laps_exclude_first_lap_only_by_default() -> None:
    assert flag_clean_laps(_laps())["is_clean"].tolist() == [False, True, True, True, True, True]


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("pit_in_time_s", 3000.0),
        ("pit_out_time_s", 3100.0),
        ("track_status", "4"),  # safety car
        ("track_status", "12"),  # green then yellow within the lap
        ("deleted", True),
        ("is_accurate", False),
        ("lap_time_s", None),
    ],
)
def test_lap_three_is_excluded_when(column: str, value: object) -> None:
    laps = _laps()
    laps[column] = laps[column].astype(object)
    laps.loc[2, column] = value

    assert not flag_clean_laps(laps).loc[2, "is_clean"]


def test_slow_outliers_relative_to_driver_median_are_excluded() -> None:
    laps = _laps(lap_time_s=[95.0, 90.0, 99.0, 90.4, 90.1, 90.3])  # 99 > 1.07 * ~90.3

    assert flag_clean_laps(laps)["is_clean"].tolist() == [False, True, False, True, True, True]


def test_derive_stints() -> None:
    stints = derive_stints(flag_clean_laps(_laps()))

    assert stints[["stint", "compound", "start_lap", "end_lap", "laps", "clean_laps"]].to_dict(
        "records"
    ) == [
        {"stint": 1, "compound": "SOFT", "start_lap": 1, "end_lap": 3, "laps": 3, "clean_laps": 2},
        {"stint": 2, "compound": "HARD", "start_lap": 4, "end_lap": 6, "laps": 3, "clean_laps": 3},
    ]


@pytest.mark.parametrize(
    ("spec", "expected"),
    [(None, [1, 2, 3]), ("2", [2]), ("1-3,7", [1, 2, 3, 7]), (" 5 , 1-2", [1, 2, 5])],
)
def test_parse_rounds(spec: str | None, expected: list[int]) -> None:
    assert parse_rounds(spec, [3, 1, 2]) == expected
