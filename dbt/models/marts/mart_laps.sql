select l.*, r.driver_name
from {{ ref('stg_laps') }} l
left join {{ ref('stg_results') }} r
  on r.season = l.season and r.round = l.round and r.driver_code = l.driver
