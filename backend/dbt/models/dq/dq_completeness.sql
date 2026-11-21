-- Completeness per series: expected periods between the first and last observation
-- (business days for daily series, months for monthly series) versus periods observed.
with missing as (
    select series_key, count(*) as missing_periods
    from {{ ref('int_missing_periods') }}
    group by series_key
),

expected as (
    select
        s.series_key,
        case
            when s.frequency = 'daily' then (
                select count(*)
                from {{ ref('stg_meta__calendar') }} as c
                where c.is_business_day and c.cal_date between s.first_date and s.last_date
            )
            else datediff('month', s.first_date, s.last_date) + 1
        end as expected_periods
    from {{ ref('dim_series') }} as s
    where s.first_date is not null
)

select
    s.series_key,
    s.category,
    s.frequency,
    s.first_date,
    s.last_date,
    e.expected_periods,
    coalesce(m.missing_periods, 0) as missing_periods,
    round(100.0 * (e.expected_periods - coalesce(m.missing_periods, 0)) / e.expected_periods, 3)
        as completeness_pct
from {{ ref('dim_series') }} as s
inner join expected as e on s.series_key = e.series_key
left join missing as m on s.series_key = m.series_key
