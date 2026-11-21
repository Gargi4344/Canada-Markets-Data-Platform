-- Freshness per series: business days between the latest observation and the as-of date.
-- For monthly series the clock starts at the end of the reference month.
-- status: green (within threshold), amber (within 2x threshold), red (older).
with latest as (
    select
        s.series_key,
        s.category,
        s.frequency,
        s.freshness_max_business_days as threshold_business_days,
        s.last_date as latest_obs_date,
        case
            when s.frequency = 'monthly' then cast(last_day(s.last_date) as date)
            else s.last_date
        end as period_end
    from {{ ref('dim_series') }} as s
),

aged as (
    select
        l.*,
        {{ as_of() }} as as_of_date,
        (
            select count(*)
            from {{ ref('stg_meta__calendar') }} as c
            where c.is_business_day and c.cal_date > l.period_end and c.cal_date <= {{ as_of() }}
        ) as business_days_since
    from latest as l
)

select
    *,
    latest_obs_date is not null and business_days_since <= threshold_business_days as is_fresh,
    case
        when latest_obs_date is null then 'red'
        when business_days_since <= threshold_business_days then 'green'
        when business_days_since <= 2 * threshold_business_days then 'amber'
        else 'red'
    end as status
from aged
