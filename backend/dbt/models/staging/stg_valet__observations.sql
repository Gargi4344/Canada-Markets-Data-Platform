-- Silver rule 1 (typing): cast the raw text columns of Bank of Canada Valet data.
-- Nothing is removed here, so the row count equals the bronze row count.
select
    series_key,
    source_id,
    'boc_valet' as source,
    cast(obs_date as date) as obs_date,
    value_raw,
    try_cast(nullif(trim(value_raw), '') as double) as value_num,
    load_id,
    loaded_at,
    source_url
from {{ source('bronze', 'boc_valet') }}
