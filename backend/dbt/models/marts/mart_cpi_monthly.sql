-- Monthly CPI index levels with month-over-month and year-over-year inflation.
with cpi as (
    select o.series_key, o.obs_date as month, o.value as index_value
    from {{ ref('fct_observation') }} as o
    inner join {{ ref('dim_series') }} as s on o.series_key = s.series_key
    where s.category = 'cpi'
)

select
    c.series_key,
    c.month,
    c.index_value,
    round((c.index_value / prev_m.index_value - 1) * 100, 3) as mom_pct,
    round((c.index_value / prev_y.index_value - 1) * 100, 3) as yoy_pct
from cpi as c
left join cpi as prev_m
    on c.series_key = prev_m.series_key and prev_m.month = cast(c.month - interval 1 month as date)
left join cpi as prev_y
    on c.series_key = prev_y.series_key and prev_y.month = cast(c.month - interval 12 month as date)
