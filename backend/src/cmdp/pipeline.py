"""End-to-end pipeline: extract (bronze) -> dbt run (silver, gold) -> dbt test (DQ) -> publish.

Usage (from ``backend/``)::

    uv run python -m cmdp.pipeline run                  # real data, incremental
    uv run python -m cmdp.pipeline run --full-refresh   # real data, reload everything
    uv run python -m cmdp.pipeline run --fixtures       # offline, committed fixtures
    uv run python -m cmdp.pipeline docs                 # dbt docs generate
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime

import duckdb
import polars as pl

from cmdp.calendar import build_calendar
from cmdp.config import Settings, get_settings
from cmdp.dbt_runner import load_manifest, run_dbt
from cmdp.dq.results import collect_dq_rows, summarise, write_dq_rows
from cmdp.extract.bronze import new_load_id
from cmdp.extract.fixtures import fixture_as_of, fixture_transport
from cmdp.extract.http import make_client
from cmdp.extract.run import run_extract
from cmdp.series import Catalog, load_catalog

log = logging.getLogger("cmdp.pipeline")

PIPELINE_RUNS_DDL = """
create schema if not exists gold;
create table if not exists gold.pipeline_runs (
    run_id varchar, mode varchar, full_refresh boolean, as_of date,
    started_at timestamptz, finished_at timestamptz, duration_s double,
    extract_s double, dbt_run_s double, dbt_test_s double,
    rows_extracted bigint, series_loaded integer,
    dq_total integer, dq_pass integer, dq_warn integer, dq_fail integer, dq_error integer,
    status varchar
);
"""


@dataclass
class RunReport:
    """Everything measured during one pipeline run."""

    run_id: str
    mode: str
    full_refresh: bool
    as_of: str
    started_at: str = ""
    finished_at: str = ""
    duration_s: float = 0.0
    timings_s: dict[str, float] = field(default_factory=dict)
    rows_extracted: int = 0
    series_loaded: int = 0
    dq: dict[str, float] = field(default_factory=dict)
    status: str = "running"


def fixture_settings(base: Settings) -> Settings:
    """Settings for fixture mode: a separate data folder so real data is never touched."""
    return base.model_copy(update={"data_dir": base.data_dir / "fixtures"})


def write_meta(settings: Settings, catalog: Catalog, as_of: date) -> None:
    """Write the series catalog and the business-day calendar to ``bronze/_meta``."""
    meta = settings.bronze_dir / "_meta"
    meta.mkdir(parents=True, exist_ok=True)
    rows = []
    for s in catalog.series:
        d = s.model_dump()
        d["range_min"], d["range_max"] = d.pop("range")
        rows.append(d)
    pl.DataFrame(rows).write_parquet(meta / "series_catalog.parquet")
    start = date(catalog.start_date.year - 1, 1, 1)
    build_calendar(start, as_of).write_parquet(meta / "calendar.parquet")


def publish(settings: Settings, attempts: int = 10) -> None:
    """Copy the build warehouse to ``markets.duckdb`` atomically (the file the API reads)."""
    tmp = settings.gold_db.with_suffix(".duckdb.tmp")
    shutil.copyfile(settings.build_db, tmp)
    for i in range(attempts):
        try:
            os.replace(tmp, settings.gold_db)
            return
        except PermissionError:  # the API may hold the file open for a moment on Windows
            time.sleep(0.5 * (i + 1))
    raise RuntimeError(f"could not publish {settings.gold_db}")


def record_run(settings: Settings, report: RunReport) -> None:
    """Store the run report in ``gold.pipeline_runs`` and as JSON in ``data/runs``."""
    con = duckdb.connect(str(settings.build_db))
    try:
        con.execute(PIPELINE_RUNS_DDL)
        t, dq = report.timings_s, report.dq
        con.execute(
            "insert into gold.pipeline_runs values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                report.run_id,
                report.mode,
                report.full_refresh,
                report.as_of,
                report.started_at,
                report.finished_at,
                report.duration_s,
                t.get("extract", 0.0),
                t.get("dbt_run", 0.0),
                t.get("dbt_test", 0.0),
                report.rows_extracted,
                report.series_loaded,
                dq.get("total", 0),
                dq.get("pass", 0),
                dq.get("warn", 0),
                dq.get("fail", 0),
                dq.get("error", 0),
                report.status,
            ],
        )
    finally:
        con.close()
    settings.runs_dir.mkdir(parents=True, exist_ok=True)
    (settings.runs_dir / f"{report.run_id}.json").write_text(
        json.dumps(asdict(report), indent=2), encoding="utf-8"
    )


def run_pipeline(
    settings: Settings | None = None, fixtures: bool = False, full_refresh: bool = False
) -> RunReport:
    """Run extract -> dbt run -> dbt test -> dq_results -> publish and return the report."""
    settings = settings or get_settings()
    if fixtures:
        settings = fixture_settings(settings)
    catalog = load_catalog(settings.series_config)
    as_of = date.fromisoformat(fixture_as_of(settings.fixtures_dir)) if fixtures else date.today()
    run_id = new_load_id()
    report = RunReport(
        run_id=run_id,
        mode="fixtures" if fixtures else "real",
        full_refresh=full_refresh,
        as_of=as_of.isoformat(),
        started_at=datetime.now(UTC).isoformat(),
    )
    t0 = time.perf_counter()

    if full_refresh:
        shutil.rmtree(settings.bronze_dir, ignore_errors=True)
        settings.build_db.unlink(missing_ok=True)
    settings.bronze_dir.mkdir(parents=True, exist_ok=True)

    t = time.perf_counter()
    write_meta(settings, catalog, as_of)
    transport = fixture_transport(settings.fixtures_dir) if fixtures else None
    with make_client(settings.http_timeout_seconds, transport=transport) as client:
        records = run_extract(
            client,
            catalog,
            settings.bronze_dir,
            settings.valet_base_url,
            settings.statcan_base_url,
            run_id,
            as_of,
        )
    report.timings_s["extract"] = round(time.perf_counter() - t, 3)
    report.rows_extracted = sum(r.row_count for r in records)
    report.series_loaded = len(records)
    log.info("extract: %d new rows in %.1fs", report.rows_extracted, report.timings_s["extract"])

    t = time.perf_counter()
    run = run_dbt(settings, ["run"], as_of.isoformat())
    report.timings_s["dbt_run"] = round(time.perf_counter() - t, 3)
    if not run.success:
        report.status = "failed: dbt run"
        raise RuntimeError("dbt run failed; see backend/dbt/logs/dbt.log")

    t = time.perf_counter()
    test = run_dbt(settings, ["test"], as_of.isoformat())
    report.timings_s["dbt_test"] = round(time.perf_counter() - t, 3)
    dq_rows = collect_dq_rows(test.run_results or {}, load_manifest(settings), run_id)
    write_dq_rows(settings.build_db, dq_rows)
    report.dq = summarise(dq_rows)
    log.info("data quality: %s", report.dq)

    report.status = "success" if test.success else "success_with_dq_failures"
    report.finished_at = datetime.now(UTC).isoformat()
    report.duration_s = round(time.perf_counter() - t0, 3)
    record_run(settings, report)

    t = time.perf_counter()
    publish(settings)
    report.timings_s["publish"] = round(time.perf_counter() - t, 3)
    report.duration_s = round(time.perf_counter() - t0, 3)
    (settings.runs_dir / f"{report.run_id}.json").write_text(
        json.dumps(asdict(report), indent=2), encoding="utf-8"
    )
    log.info("pipeline finished in %.1fs (%s)", report.duration_s, report.status)
    return report


def generate_docs(settings: Settings | None = None) -> bool:
    """Run ``dbt docs generate`` against the current build warehouse."""
    settings = settings or get_settings()
    return run_dbt(settings, ["docs", "generate"]).success


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(prog="cmdp.pipeline", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run", help="run the pipeline")
    run_p.add_argument("--fixtures", action="store_true", help="use committed fixtures (offline)")
    run_p.add_argument("--full-refresh", action="store_true", help="delete bronze and rebuild")
    sub.add_parser("docs", help="generate dbt docs")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.command == "docs":
        return 0 if generate_docs() else 1
    report = run_pipeline(fixtures=args.fixtures, full_refresh=args.full_refresh)
    print(json.dumps(asdict(report), indent=2))
    return 0 if report.dq.get("error", 0) == 0 and report.dq.get("fail", 0) == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
