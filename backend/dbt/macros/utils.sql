{#- Use the custom schema name as-is (silver, gold) instead of "<target>_<custom>". -#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}{{ target.schema }}{%- else -%}{{ custom_schema_name | trim }}{%- endif -%}
{%- endmacro %}

{#- The reference date for freshness checks, as a SQL date literal. -#}
{% macro as_of() -%}
    {%- set v = var('as_of', '') -%}
    {%- if v -%}cast('{{ v }}' as date){%- else -%}current_date{%- endif -%}
{%- endmacro %}

{#- Path to a bronze folder or file, taken from the CMDP_BRONZE_PATH environment variable. -#}
{% macro bronze_path(sub) -%}
    {{ env_var('CMDP_BRONZE_PATH', '../../data/bronze') }}/{{ sub }}
{%- endmacro %}
