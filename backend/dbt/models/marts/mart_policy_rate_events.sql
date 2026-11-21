-- Changes in the target for the overnight rate.
-- effective_date is the first business day on which the new target appears in Valet V39079.
with p as (
    select
        obs_date,
        value,
        lag(value) over (order by obs_date) as prev_value
    from {{ ref('fct_observation') }}
    where series_key = 'POLICY_RATE'
)

select
    obs_date as effective_date,
    cast(strftime(obs_date, '%Y%m%d') as integer) as date_key,
    prev_value as old_rate,
    value as new_rate,
    cast(round((value - prev_value) * 100) as integer) as change_bps,
    case when value > prev_value then 'hike' else 'cut' end as direction
from p
where prev_value is not null and value <> prev_value
