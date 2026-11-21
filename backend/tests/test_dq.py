"""Tests for the data quality framework: result collection and the controls themselves."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime

import duckdb
import pytest

from cmdp.config import Settings
from cmdp.dq.results import collect_dq_rows, summarise
from cmdp.extract.bronze import write_bronze
from cmdp.extract.valet import RawObservation
from cmdp.pipeline import fixture_settings, run_pipeline

from .conftest import FIXTURES


def test_collect_dq_rows_maps_categories_and_failures():
    manifest = {
        "nodes": {
            "model.cmdp.fct_observation": {"name": "fct_observation"},
            "test.cmdp.range": {
                "name": "dq_range__yield_10y",
                "attached_node": "model.cmdp.fct_observation",
                "test_metadata": {"name": "value_between", "kwargs": {"column_name": "yield_10y"}},
                "config": {"severity": "ERROR"},
            },
            "test.cmdp.fresh": {
                "name": "dq_freshness__fx",
                "attached_node": "model.cmdp.fct_observation",
                "test_metadata": {"name": "freshness_within_threshold", "kwargs": {}},
                "config": {"severity": "warn"},
            },
        }
    }
    run_results = {
        "results": [
            {"unique_id": "model.cmdp.fct_observation", "status": "success"},
            {
                "unique_id": "test.cmdp.range",
                "status": "fail",
                "failures": 3,
                "execution_time": 0.1,
            },
            {
                "unique_id": "test.cmdp.fresh",
                "status": "pass",
                "failures": 0,
                "execution_time": 0.2,
            },
        ]
    }
    rows = collect_dq_rows(run_results, manifest, "R1")
    assert [r.dq_category for r in rows] == ["range", "freshness"]
    assert rows[0].failed_rows == 3 and rows[0].severity == "error"
    assert rows[0].table_name == "fct_observation" and rows[0].column_name == "yield_10y"
    summary = summarise(rows)
    assert summary == {
        "total": 2,
        "pass": 1,
        "warn": 0,
        "fail": 1,
        "error": 0,
        "pass_rate_pct": 50.0,
    }


def test_dq_results_cover_every_control(warehouse):
    con = duckdb.connect(str(warehouse.gold_db), read_only=True)
    try:
        cats = {
            c for (c,) in con.sql("select distinct dq_category from gold.dq_results").fetchall()
        }
        recon = con.sql(
            "select status from gold.dq_results where dq_category = 'reconciliation'"
        ).fetchall()
        fresh = con.sql("select distinct status from gold.dq_freshness").fetchall()
    finally:
        con.close()
    assert {"integrity", "range", "freshness", "completeness", "anomaly", "reconciliation"} <= cats
    assert recon and all(s == "pass" for (s,) in recon)
    assert fresh == [("green",)]  # fixture as-of date is the last fixture day


@pytest.mark.slow
def test_controls_catch_bad_data(tmp_path):
    """Corrupt the fixtures and check that range, removal and reconciliation logic react."""
    fixtures = tmp_path / "fixtures"
    shutil.copytree(FIXTURES, fixtures)
    path = fixtures / "valet" / "BD.CDN.10YR.DQ.YLD.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    obs = payload["observations"]
    obs[100]["BD.CDN.10YR.DQ.YLD"]["v"] = "25.00"  # outside the -1%..20% range
    obs[101]["BD.CDN.10YR.DQ.YLD"] = {"v": ""}  # empty value -> removed as null_value
    path.write_text(json.dumps(payload), encoding="utf-8")

    base = Settings(data_dir=tmp_path / "data", fixtures_dir=fixtures)
    run_pipeline(base, fixtures=True, full_refresh=True)
    settings = fixture_settings(base)

    # Load one day again, as a re-delivered file would: silver must keep one copy.
    dup_date = obs[200]["d"]
    write_bronze(
        settings.bronze_dir,
        "boc_valet",
        "GOC_10Y",
        "BD.CDN.10YR.DQ.YLD",
        [RawObservation(dup_date, obs[200]["BD.CDN.10YR.DQ.YLD"]["v"])],
        "REDELIVERY",
        datetime.now(UTC),
        "test://redelivery",
        date.fromisoformat(dup_date),
    )
    report = run_pipeline(base, fixtures=True, full_refresh=False)

    con = duckdb.connect(str(settings.gold_db), read_only=True)
    try:
        status = dict(
            con.sql(
                "select test_name, status from gold.dq_results where run_id = ?",
                params=[report.run_id],
            ).fetchall()
        )
        recon = con.execute(
            "select bronze_rows, silver_rows, removed_null_value, removed_duplicate,"
            " diff_bronze_vs_silver, diff_load_log_vs_bronze"
            " from gold.dq_reconciliation where series_key = 'GOC_10Y'"
        ).fetchone()
        missing = con.execute(
            "select count(*) from silver.int_missing_periods where series_key = 'GOC_10Y'"
        ).fetchone()[0]
    finally:
        con.close()

    assert status["dq_range__yield_10y"] == "fail"
    assert status["dq_range__catalog_range"] == "fail"
    assert status["dq_completeness__bond_yield"] == "warn"  # the nulled day is now missing
    assert missing == 1
    bronze, silver, nulls, dups, diff_silver, diff_log = recon
    assert (nulls, dups) == (1, 1)
    assert bronze == silver + nulls + dups and diff_silver == 0
    # The hand-written re-delivery file is not in the load log, and the control notices.
    assert diff_log == -1
    assert status["dq_reconciliation__load_log_vs_bronze"] == "fail"
