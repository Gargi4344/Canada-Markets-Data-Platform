-- Date dimension: one row per calendar day covered by the warehouse.
select
    cast(strftime(cal_date, '%Y%m%d') as integer) as date_key,
    cal_date as date,
    is_business_day,
    is_weekend,
    holiday_name,
    dayofweek(cal_date) as day_of_week,
    strftime(cal_date, '%A') as day_name,
    month(cal_date) as month,
    strftime(cal_date, '%B') as month_name,
    quarter(cal_date) as quarter,
    year(cal_date) as year,
    cast(date_trunc('month', cal_date) as date) as month_start
from {{ ref('stg_meta__calendar') }}
