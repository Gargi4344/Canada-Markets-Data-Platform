-- One row per series per extract run.
select
    load_id,
    source,
    series_key,
    source_id,
    cast(requested_start as date) as requested_start,
    cast(row_count as bigint) as row_count,
    cast(min_obs_date as date) as min_obs_date,
    cast(max_obs_date as date) as max_obs_date,
    source_url,
    loaded_at
from {{ source('bronze', 'load_log') }}
