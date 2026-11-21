"""End-to-end test: run the whole pipeline on fixtures and check the gold tables."""

from __future__ import annotations

import duckdb
import pytest

pytestmark = pytest.mark.slow


def q(warehouse, sql):
    con = duckdb.connect(str(warehouse.gold_db), read_only=True)
    try:
        return con.sql(sql).fetchall()
    finally:
        con.close()


def test_pipeline_report(warehouse_report):
    report = warehouse_report
    assert report.status == "success"
    assert report.rows_extracted > 5000
    assert report.dq["error"] == 0 and report.dq["fail"] == 0
    assert report.dq["total"] >= 60


def test_star_schema_tables_exist(warehouse):
    tables = {t for (t,) in q(warehouse, "select table_name from information_schema.tables")}
    expected = {
        "dim_date",
        "dim_series",
        "fct_observation",
        "mart_yield_curve",
        "mart_fx_daily",
        "mart_policy_rate_events",
        "mart_real_policy_rate",
        "mart_cpi_monthly",
        "dq_results",
        "pipeline_runs",
    }
    assert expected <= tables


def test_bronze_rows_equal_fact_rows(warehouse):
    (bronze,) = q(
        warehouse,
        "select (select count(*) from silver.stg_valet__observations)"
        " + (select count(*) from silver.stg_statcan__observations)",
    )[0]
    (removed,) = q(warehouse, "select count(*) from silver.int_observation_removals")[0]
    (facts,) = q(warehouse, "select count(*) from gold.fct_observation")[0]
    assert bronze == facts + removed


def test_yield_curve_spread_and_inversion(warehouse):
    rows = q(
        warehouse,
        "select yield_2y, yield_10y, spread_2s10s_bps, is_inverted from gold.mart_yield_curve",
    )
    assert rows
    for y2, y10, spread, inverted in rows:
        assert spread == pytest.approx(round((y10 - y2) * 100, 1), abs=0.051)
        assert inverted == (y10 < y2)
    # The Canadian curve was inverted for most of 2023.
    (n_inv,) = q(
        warehouse,
        "select count(*) from gold.mart_yield_curve where is_inverted and year(obs_date) = 2023",
    )[0]
    assert n_inv > 100


def test_policy_rate_events(warehouse):
    events = q(
        warehouse,
        "select effective_date, old_rate, new_rate, change_bps"
        " from gold.mart_policy_rate_events order by 1",
    )
    assert events, "the fixture window (2023-2024) contains rate decisions"
    for _, old, new, bps in events:
        assert bps == round((new - old) * 100) and bps != 0


def test_fx_volatility_needs_30_returns(warehouse):
    (first_vol_rank,) = q(
        warehouse,
        "select min(rn) from (select vol_30d_pct, row_number() over (order by obs_date) rn"
        " from gold.mart_fx_daily where pair = 'USDCAD') where vol_30d_pct is not null",
    )[0]
    assert first_vol_rank == 31  # 30 returns need 31 rates


def test_real_policy_rate_definition(warehouse):
    rows = q(
        warehouse,
        "select policy_rate_avg, cpi_yoy_pct, real_policy_rate from gold.mart_real_policy_rate",
    )
    assert len(rows) >= 12
    for avg, yoy, real in rows:
        assert real == pytest.approx(avg - yoy, abs=1e-3)
