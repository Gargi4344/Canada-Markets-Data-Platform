-- Silver rule 1 (typing): cast the raw text columns of Statistics Canada CPI data.
-- StatCan reference periods are the first day of the month (YYYY-MM-01).
select
    series_key,
    source_id,
    'statcan_wds' as source,
    cast(obs_date as date) as obs_date,
    value_raw,
    try_cast(nullif(trim(value_raw), '') as double) as value_num,
    load_id,
    loaded_at,
    source_url
from {{ source('bronze', 'statcan_wds') }}
