select
    season, round, event_name, driver, team, lap_number,
    lap_time_s, sector1_s, sector2_s, sector3_s,
    stint, coalesce(compound, 'UNKNOWN') as compound, tyre_life, fresh_tyre,
    pit_in_time_s is not null as is_in_lap,
    pit_out_time_s is not null as is_out_lap,
    track_status, position, deleted, is_accurate, is_clean
from {{ source('raw', 'fastf1_laps') }}
