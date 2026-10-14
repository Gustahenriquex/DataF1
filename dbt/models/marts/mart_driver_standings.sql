-- Latest standings snapshot available for each season.
select s.*
from {{ source('raw', 'jolpica_driver_standings') }} s
where after_round = (
    select max(after_round) from {{ source('raw', 'jolpica_driver_standings') }} x
    where x.season = s.season
)
