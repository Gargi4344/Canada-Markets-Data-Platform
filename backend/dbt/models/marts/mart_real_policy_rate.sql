-- Monthly real policy rate: average policy rate in the month minus CPI all-items
-- year-over-year inflation for the same month.
with policy as (
    select
        cast(date_trunc('month', obs_date) as date) as month,
        avg(value) as policy_rate_avg,
        arg_max(value, obs_date) as policy_rate_eom
    from {{ ref('fct_observation') }}
    where series_key = 'POLICY_RATE'
    group by 1
),

cpi as (
    select month, yoy_pct as cpi_yoy_pct
    from {{ ref('mart_cpi_monthly') }}
    where series_key = 'CPI_ALL' and yoy_pct is not null
)

select
    p.month,
    round(p.policy_rate_avg, 4) as policy_rate_avg,
    p.policy_rate_eom,
    c.cpi_yoy_pct,
    round(p.policy_rate_avg - c.cpi_yoy_pct, 4) as real_policy_rate
from policy as p
inner join cpi as c on p.month = c.month
