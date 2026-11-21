-- Series catalog from config/series.yaml.
select
    key as series_key,
    source_id,
    source,
    category,
    name as series_name,
    unit,
    cast(unit_multiplier as double) as unit_multiplier,
    frequency,
    cast(freshness_max_business_days as integer) as freshness_max_business_days,
    cast(anomaly_check as boolean) as anomaly_check,
    cast(range_min as double) as range_min,
    cast(range_max as double) as range_max,
    description
from {{ source('bronze', 'series_catalog') }}
