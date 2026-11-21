-- Daily CAD exchange rates with returns and 30-business-day rolling volatility.
-- vol_30d_pct = sample standard deviation of the last 30 daily log returns,
-- annualised with sqrt(252), in percent. Null until 30 returns are available.
with fx as (
    select
        o.series_key,
        replace(o.series_key, 'FX_', '') as pair,
        o.obs_date,
        o.date_key,
        o.value as rate
    from {{ ref('fct_observation') }} as o
    inner join {{ ref('dim_series') }} as s on o.series_key = s.series_key
    where s.category = 'fx'
),

returns as (
    select
        *,
        lag(rate) over (partition by pair order by obs_date) as prev_rate
    from fx
),

with_returns as (
    select
        *,
        (rate / prev_rate - 1) * 100 as daily_return_pct,
        ln(rate / prev_rate) as log_return
    from returns
),

windowed as (
    select
        *,
        stddev_samp(log_return) over w as sd_30,
        count(log_return) over w as n_30
    from with_returns
    window w as (partition by pair order by obs_date rows between 29 preceding and current row)
)

select
    pair,
    series_key,
    obs_date,
    date_key,
    rate,
    daily_return_pct,
    log_return,
    case when n_30 = 30 then sd_30 * sqrt(252) * 100 end as vol_30d_pct
from windowed
