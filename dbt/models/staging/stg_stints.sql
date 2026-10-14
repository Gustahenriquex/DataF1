select season, round, driver, team, stint, compound,
       start_lap, end_lap, laps, tyre_life_start, fresh_tyre, clean_laps
from {{ source('raw', 'fastf1_stints') }}
