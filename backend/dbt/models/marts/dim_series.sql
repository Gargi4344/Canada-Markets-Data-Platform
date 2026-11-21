-- Series dimension: catalog metadata plus coverage statistics from the silver layer.
with coverage as (
    select
        series_key,
        min(obs_date) as first_date,
        max(obs_date) as last_date,
        count(*) as observation_count
    from {{ ref('int_observations_clean') }}
    group by series_key
)

select
    s.series_key,
    s.source_id,
    s.source,
    s.category,
    s.series_name,
    s.unit,
    s.frequency,
    s.description,
    s.range_min,
    s.range_max,
    s.freshness_max_business_days,
    s.anomaly_check,
    c.first_date,
    c.last_date,
    coalesce(c.observation_count, 0) as observation_count
from {{ ref('stg_meta__series') }} as s
left join coverage as c on s.series_key = c.series_key
