-- One pace row per driver per race.
select season, round, driver, count(*) as n
from {{ ref('mart_race_pace') }}
group by season, round, driver
having count(*) > 1
