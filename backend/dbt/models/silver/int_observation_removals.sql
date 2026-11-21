-- Rows removed between bronze and silver, with the documented reason.
select
    series_key,
    source,
    obs_date,
    value_raw,
    load_id,
    loaded_at,
    removal_reason
from {{ ref('int_observations_flagged') }}
where removal_reason is not null
