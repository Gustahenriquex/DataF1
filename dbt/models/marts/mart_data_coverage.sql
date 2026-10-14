-- What we actually have per race: makes gaps visible instead of silent.
select
    season, round, max(event_name) as event_name,
    count(distinct driver) as drivers,
    count(*) as laps,
    sum(case when lap_time_s is null then 1 else 0 end) as laps_without_time,
    round(100.0 * avg(case when is_clean then 1 else 0 end), 1) as pct_clean,
    sum(case when compound = 'UNKNOWN' then 1 else 0 end) as laps_unknown_compound,
    sum(case when track_status <> '1' then 1 else 0 end) as laps_not_green
from {{ ref('stg_laps') }}
group by season, round
