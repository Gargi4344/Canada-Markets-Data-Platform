-- Daily Government of Canada yield curve with the 2s10s spread and an inversion flag.
with pivoted as (
    select
        obs_date,
        date_key,
        max(value) filter (where series_key = 'GOC_2Y') as yield_2y,
        max(value) filter (where series_key = 'GOC_5Y') as yield_5y,
        max(value) filter (where series_key = 'GOC_10Y') as yield_10y,
        max(value) filter (where series_key = 'GOC_LONG') as yield_long
    from {{ ref('fct_observation') }}
    where series_key in ('GOC_2Y', 'GOC_5Y', 'GOC_10Y', 'GOC_LONG')
    group by obs_date, date_key
)

select
    obs_date,
    date_key,
    yield_2y,
    yield_5y,
    yield_10y,
    yield_long,
    round((yield_10y - yield_2y) * 100, 1) as spread_2s10s_bps,
    yield_10y < yield_2y as is_inverted,
    case when yield_10y < yield_2y then 'inverted' else 'normal' end as curve_shape
from pivoted
where yield_2y is not null and yield_10y is not null
