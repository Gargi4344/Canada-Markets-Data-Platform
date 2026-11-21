{#- ===================== Custom data quality tests ===================== -#}
{#- Each test returns the failing rows; dbt counts them as `failures`.      -#}

{#- Range: values of `column_name` must lie in [min_value, max_value] (nulls are ignored). -#}
{% test value_between(model, column_name, min_value=none, max_value=none, exclusive_min=false) %}
select *
from {{ model }}
where {{ column_name }} is not null
  and (
    false
    {% if min_value is not none %}
      or {{ column_name }} {{ '<=' if exclusive_min else '<' }} {{ min_value }}
    {% endif %}
    {% if max_value is not none %}
      or {{ column_name }} > {{ max_value }}
    {% endif %}
  )
{% endtest %}

{#- Range: every observation lies inside the plausible range of its series in the catalog. -#}
{% test values_within_catalog_range(model) %}
select o.series_key, o.obs_date, o.value, s.range_min, s.range_max
from {{ model }} as o
inner join {{ ref('dim_series') }} as s on o.series_key = s.series_key
where o.value < s.range_min or o.value > s.range_max
{% endtest %}

{#- Freshness: series whose latest observation is older than its threshold. -#}
{% test freshness_within_threshold(model) %}
select *
from {{ model }}
where not is_fresh
{% endtest %}

{#- Completeness: the model lists missing business days / months; it must be empty. -#}
{% test no_missing_periods(model) %}
select *
from {{ model }}
{% endtest %}

{#- Anomaly: the model lists flagged moves; any row is reported. -#}
{% test no_anomalies(model) %}
select *
from {{ model }}
{% endtest %}

{#- Reconciliation: the difference column must be zero for every series. -#}
{% test reconciles(model, column_name) %}
select *
from {{ model }}
where {{ column_name }} <> 0
{% endtest %}
