"""F1 Intelligence dashboard. Run with `uv run f1i app`.

Reads only the `marts` schema built by dbt; no metric is computed here that is not
defined in the pipeline, so the dashboard and future API/agent report the same numbers.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text

from f1i.config import get_settings
from f1i.storage import get_engine

COMPOUND_COLORS = {
    "SOFT": "#da291c",
    "MEDIUM": "#ffd12e",
    "HARD": "#f0f0ec",
    "INTERMEDIATE": "#43b02a",
    "WET": "#0067ad",
    "UNKNOWN": "#7f7f7f",
}
PLOT_TEMPLATE = "plotly_dark"

st.set_page_config(page_title="F1 Intelligence", page_icon="🏁", layout="wide")


@st.cache_resource
def _engine():
    return get_engine(get_settings())


@st.cache_data(ttl=600)
def query(sql: str, **params: object) -> pd.DataFrame:
    with _engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def fmt_lap(seconds: float) -> str:
    minutes, sec = divmod(seconds, 60)
    return f"{int(minutes)}:{sec:06.3f}"


# ------------------------------------------------------------------ sidebar ---
st.sidebar.title("🏁 F1 Intelligence")
try:
    races = query(
        "select distinct season, round, race_name from marts.mart_race_results "
        "order by season, round"
    )
except Exception as exc:  # database down or pipeline never run
    st.error(f"No data available. Run `f1i ingest` and `f1i build` first.\n\n{exc}")
    st.stop()

season = st.sidebar.selectbox("Season", sorted(races["season"].unique(), reverse=True))
season_races = races[races["season"] == season]
laps_rounds = query("select distinct round from marts.mart_laps where season = :s", s=int(season))[
    "round"
]
race_options = season_races[season_races["round"].isin(laps_rounds)]
if race_options.empty:
    st.sidebar.warning("No lap data ingested for this season yet.")
race_label = st.sidebar.selectbox(
    "Race (lap data)",
    race_options.itertuples(index=False),
    format_func=lambda r: f"R{r.round:02d} · {r.race_name}",
)
st.sidebar.caption(
    "Unofficial, non-commercial project. Data: Jolpica-F1 (CC BY-NC-SA 4.0) and FastF1."
)

tab_season, tab_race, tab_compare, tab_quality = st.tabs(
    ["Season overview", "Race analysis", "Driver comparison", "Data coverage"]
)

# ------------------------------------------------------------ season overview ---
with tab_season:
    standings = query(
        "select position, driver_name, constructor_name, points, wins, after_round "
        "from marts.mart_driver_standings where season = :s order by position",
        s=int(season),
    )
    if not standings.empty:
        st.subheader(f"Drivers' standings {season} · after round {standings['after_round'].iat[0]}")
        fig = px.bar(
            standings.head(10).iloc[::-1],
            x="points",
            y="driver_name",
            orientation="h",
            color="constructor_name",
            template=PLOT_TEMPLATE,
            labels={"driver_name": ""},
        )
        st.plotly_chart(fig, width="stretch")
    winners = query(
        "select round, race_name, driver_name as winner, constructor_name, grid "
        "from marts.mart_race_results where season = :s and position = 1 order by round",
        s=int(season),
    )
    st.subheader("Race winners")
    st.dataframe(winners, hide_index=True, width="stretch")

if race_label is None:
    st.stop()
rnd = int(race_label.round)
laps = query("select * from marts.mart_laps where season = :s and round = :r", s=int(season), r=rnd)
drivers = sorted(laps["driver"].dropna().unique())

# -------------------------------------------------------------- race analysis ---
with tab_race:
    st.subheader(f"{race_label.race_name} {season}")
    picked = st.multiselect("Drivers", drivers, default=drivers[:4])
    clean_only = st.toggle("Clean laps only (green flag, no pit laps, no outliers)", value=True)
    view = laps[laps["driver"].isin(picked)]
    if clean_only:
        view = view[view["is_clean"]]
    fig = px.line(
        view.sort_values("lap_number"),
        x="lap_number",
        y="lap_time_s",
        color="driver",
        markers=True,
        template=PLOT_TEMPLATE,
        labels={"lap_number": "Lap", "lap_time_s": "Lap time (s)"},
        hover_data=["compound", "tyre_life"],
    )
    st.plotly_chart(fig, width="stretch")

    st.subheader("Tyre strategy")
    stints = query(
        "select * from marts.mart_stints where season = :s and round = :r", s=int(season), r=rnd
    )
    order = query(
        "select driver_code from marts.mart_race_results "
        "where season = :s and round = :r order by position",
        s=int(season),
        r=rnd,
    )["driver_code"].tolist()
    stints["laps_span"] = stints["end_lap"] - stints["start_lap"] + 1
    fig = px.bar(
        stints,
        x="laps_span",
        y="driver",
        base="start_lap",
        orientation="h",
        color="compound",
        color_discrete_map=COMPOUND_COLORS,
        template=PLOT_TEMPLATE,
        category_orders={"driver": order},
        labels={"laps_span": "Lap", "driver": ""},
        hover_data=["stint", "start_lap", "end_lap", "tyre_life_start"],
    )
    fig.update_layout(height=max(400, 22 * stints["driver"].nunique()))
    st.plotly_chart(fig, width="stretch")
    st.caption("Ordered by finishing position. Bars start at the stint's first lap.")

# ---------------------------------------------------------- driver comparison ---
with tab_compare:
    pace = query(
        "select * from marts.mart_race_pace where season = :s and round = :r order by median_lap_s",
        s=int(season),
        r=rnd,
    )
    c1, c2 = st.columns(2)
    d1 = c1.selectbox("Driver A", pace["driver"], index=0)
    d2 = c2.selectbox("Driver B", pace["driver"], index=min(1, len(pace) - 1))
    a, b = (pace.set_index("driver").loc[d] for d in (d1, d2))
    m1, m2, m3 = st.columns(3)
    m1.metric(f"{d1} median clean lap", fmt_lap(a.median_lap_s), f"n={a.clean_laps}")
    m2.metric(f"{d2} median clean lap", fmt_lap(b.median_lap_s), f"n={b.clean_laps}")
    m3.metric("Median gap (B - A)", f"{b.median_lap_s - a.median_lap_s:+.3f} s")

    duel = laps[laps["driver"].isin([d1, d2]) & laps["is_clean"]]
    fig = px.box(
        duel,
        x="driver",
        y="lap_time_s",
        color="compound",
        points="all",
        color_discrete_map=COMPOUND_COLORS,
        template=PLOT_TEMPLATE,
        labels={"lap_time_s": "Clean lap time (s)", "driver": ""},
    )
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "Pace = median of clean laps; consistency = IQR. Not fuel- or tyre-corrected yet "
        "(Phase 3): drivers on different strategies are not directly comparable."
    )
    st.dataframe(
        pace[
            [
                "driver",
                "team",
                "finish_position",
                "clean_laps",
                "median_lap_s",
                "gap_to_best_s",
                "iqr_lap_s",
            ]
        ].round(3),
        hide_index=True,
        width="stretch",
    )

# -------------------------------------------------------------- data coverage ---
with tab_quality:
    st.subheader("What the data contains")
    st.dataframe(
        query("select * from marts.mart_data_coverage order by season, round"),
        hide_index=True,
        width="stretch",
    )
    st.caption("FastF1 lap timing exists from 2018 onwards; earlier seasons have results only.")
