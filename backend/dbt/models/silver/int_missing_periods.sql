-- Expected periods that have no observation, between each series' first and last date.
-- Daily series: every Bank of Canada business day. Monthly series: every month.
with bounds as (
    select series_key, frequency, category, min(obs_date) as first_date, max(obs_date) as last_date
    from {{ ref('int_observations_clean') }}
    group by all
),

expected_daily as (
    select b.series_key, b.category, b.frequency, c.cal_date as expected_date
    from bounds as b
    inner join {{ ref('stg_meta__calendar') }} as c
        on c.cal_date between b.first_date and b.last_date and c.is_business_day
    where b.frequency = 'daily'
),

months as (
    select
        series_key,
        category,
        frequency,
        unnest(generate_series(first_date, last_date, interval 1 month)) as month_start
    from bounds
    where frequency = 'monthly'
),

expected_monthly as (
    select series_key, category, frequency, cast(month_start as date) as expected_date
    from months
),

expected as (
    select * from expected_daily
    union all
    select * from expected_monthly
)

select e.series_key, e.category, e.frequency, e.expected_date
from expected as e
left join {{ ref('int_observations_clean') }} as o
    on e.series_key = o.series_key and e.expected_date = o.obs_date
where o.series_key is null
