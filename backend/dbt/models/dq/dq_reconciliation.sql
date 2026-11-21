-- Row-count reconciliation per series across the layers:
--   load log rows  = bronze rows                       (every logged row reached a file)
--   bronze rows    = silver rows + documented removals (null values and duplicates)
--   silver rows    = fact rows                         (nothing lost joining dim_date)
with bronze as (
    select series_key, count(*) as bronze_rows
    from (
        select series_key from {{ ref('stg_valet__observations') }}
        union all
        select series_key from {{ ref('stg_statcan__observations') }}
    )
    group by series_key
),

load_log as (
    select series_key, sum(row_count) as load_log_rows
    from {{ ref('stg_meta__load_log') }}
    group by series_key
),

silver as (
    select series_key, count(*) as silver_rows
    from {{ ref('int_observations_clean') }}
    group by series_key
),

removed as (
    select
        series_key,
        count(*) filter (where removal_reason = 'null_value') as removed_null_value,
        count(*) filter (where removal_reason = 'duplicate') as removed_duplicate
    from {{ ref('int_observation_removals') }}
    group by series_key
),

facts as (
    select series_key, count(*) as fact_rows
    from {{ ref('fct_observation') }}
    group by series_key
),

joined as (
    select
        s.series_key,
        coalesce(l.load_log_rows, 0) as load_log_rows,
        coalesce(b.bronze_rows, 0) as bronze_rows,
        coalesce(sv.silver_rows, 0) as silver_rows,
        coalesce(r.removed_null_value, 0) as removed_null_value,
        coalesce(r.removed_duplicate, 0) as removed_duplicate,
        coalesce(f.fact_rows, 0) as fact_rows
    from {{ ref('stg_meta__series') }} as s
    left join load_log as l on s.series_key = l.series_key
    left join bronze as b on s.series_key = b.series_key
    left join silver as sv on s.series_key = sv.series_key
    left join removed as r on s.series_key = r.series_key
    left join facts as f on s.series_key = f.series_key
)

select
    *,
    load_log_rows - bronze_rows as diff_load_log_vs_bronze,
    bronze_rows - silver_rows - removed_null_value - removed_duplicate as diff_bronze_vs_silver,
    silver_rows - fact_rows as diff_silver_vs_fact
from joined
