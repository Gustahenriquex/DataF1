-- Race pace per driver from clean laps only (see f1i.transform.laps for the definition).
-- Median and IQR are used because lap times are skewed by traffic and tyre phases.
with clean as (
    select * from {{ ref('stg_laps') }} where is_clean
),
pace as (
    select
        season, round, driver, max(team) as team,
        count(*) as clean_laps,
        percentile_cont(0.5) within group (order by lap_time_s) as median_lap_s,
        avg(lap_time_s) as mean_lap_s,
        stddev_samp(lap_time_s) as std_lap_s,
        percentile_cont(0.75) within group (order by lap_time_s)
          - percentile_cont(0.25) within group (order by lap_time_s) as iqr_lap_s
    from clean
    group by season, round, driver
)
select
    p.*,
    p.median_lap_s - min(p.median_lap_s) over (partition by p.season, p.round) as gap_to_best_s,
    r.driver_name, r.position as finish_position
from pace p
left join {{ ref('stg_results') }} r
  on r.season = p.season and r.round = p.round and r.driver_code = p.driver
