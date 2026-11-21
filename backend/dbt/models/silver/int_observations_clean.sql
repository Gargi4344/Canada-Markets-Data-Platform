-- Clean, typed, de-duplicated observations (the silver table).
-- Silver rule 4: standardise units (value * unit_multiplier from the catalog).
-- Silver rule 5: join the business-day calendar and flag observations on non-business days.
select
    f.series_key,
    f.source,
    f.obs_date,
    f.value_num * s.unit_multiplier as value,
    s.unit,
    s.frequency,
    s.category,
    coalesce(c.is_business_day, false) as is_business_day,
    f.load_id,
    f.loaded_at
from {{ ref('int_observations_flagged') }} as f
inner join {{ ref('stg_meta__series') }} as s on f.series_key = s.series_key
left join {{ ref('stg_meta__calendar') }} as c on f.obs_date = c.cal_date
where f.removal_reason is null
