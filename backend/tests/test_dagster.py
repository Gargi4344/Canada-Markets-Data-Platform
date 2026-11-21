"""Tests for the Dagster definitions: asset graph, layers and schedule."""

from __future__ import annotations

from dagster import AssetKey


def test_definitions_load_with_medallion_layers():
    from cmdp.orchestration.definitions import defs

    graph = defs.resolve_asset_graph()
    keys = {k.to_user_string() for k in graph.get_all_asset_keys()}
    assert {"bronze/boc_valet", "bronze/statcan_wds", "bronze/load_log"} <= keys
    assert {"gold/fct_observation", "gold/mart_yield_curve", "gold/dq_freshness"} <= keys
    assert {"data_quality/dq_results", "serving/markets_warehouse"} <= keys

    # bronze -> silver lineage comes from the dbt sources' dagster asset keys
    stg = graph.get(AssetKey(["silver", "stg_valet__observations"]))
    assert AssetKey(["bronze", "boc_valet"]) in stg.parent_keys
    groups = {graph.get(AssetKey(["gold", "mart_yield_curve"])).group_name}
    assert groups == {"gold"}


def test_daily_schedule():
    from cmdp.orchestration.definitions import daily_refresh_schedule

    assert daily_refresh_schedule.cron_schedule == "0 18 * * 1-5"
    assert daily_refresh_schedule.execution_timezone == "America/Toronto"
