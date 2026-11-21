-- Every bronze row from both sources with the silver cleaning decision attached.
-- Silver rule 2: rows whose value is empty or not numeric are removed ("null_value").
-- Silver rule 3: when the same (series, date) arrives more than once, keep the most
--                recent load and remove the others ("duplicate").
with unioned as (
    select * from {{ ref('stg_valet__observations') }}
    union all
    select * from {{ ref('stg_statcan__observations') }}
),

ranked as (
    select
        *,
        row_number() over (
            partition by series_key, obs_date, (value_num is null)
            order by loaded_at desc, load_id desc
        ) as version_rank
    from unioned
)

select
    *,
    case
        when value_num is null then 'null_value'
        when version_rank > 1 then 'duplicate'
    end as removal_reason
from ranked
