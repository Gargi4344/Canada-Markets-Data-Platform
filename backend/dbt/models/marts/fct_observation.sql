-- Fact table: one row per series per observation date.
select
    o.series_key,
    d.date_key,
    o.obs_date,
    o.value,
    o.load_id
from {{ ref('int_observations_clean') }} as o
inner join {{ ref('dim_date') }} as d on o.obs_date = d.date
