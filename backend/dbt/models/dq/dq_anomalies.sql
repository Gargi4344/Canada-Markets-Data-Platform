-- Anomaly flags: a day-over-day move larger than `anomaly_sigma` (5) standard deviations of
-- the previous `anomaly_window` (250) daily moves. Only series with anomaly_check = true.
-- The model contains only the flagged observations.
{% set window = var('anomaly_window') | int %}
{% set sigma = var('anomaly_sigma') | float %}

with daily as (
    select
        o.series_key,
        s.category,
        o.obs_date,
        o.value,
        o.value - lag(o.value) over (partition by o.series_key order by o.obs_date) as change
    from {{ ref('fct_observation') }} as o
    inner join {{ ref('dim_series') }} as s on o.series_key = s.series_key
    where s.anomaly_check and s.frequency = 'daily'
),

stats as (
    select
        *,
        stddev_samp(change) over w as sd_window,
        count(change) over w as n_window
    from daily
    window w as (
        partition by series_key order by obs_date
        rows between {{ window }} preceding and 1 preceding
    )
)

select
    series_key,
    category,
    obs_date,
    value,
    change,
    sd_window,
    round(change / sd_window, 2) as z_score,
    {{ sigma }} as sigma_threshold,
    {{ window }} as window_size
from stats
where n_window = {{ window }}
    and sd_window > 0
    and abs(change) > {{ sigma }} * sd_window
