select
    season, round, race_name, race_date::date as race_date,
    circuit_id, circuit_name, country,
    driver_id, driver_code, driver_name, constructor_id, constructor_name,
    grid, position, position_text, points, laps, status,
    -- grid 0 means pit-lane start
    case when grid > 0 then grid - position end as positions_gained
from {{ source('raw', 'jolpica_results') }}
