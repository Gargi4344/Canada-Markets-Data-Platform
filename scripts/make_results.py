"""Measure the platform and regenerate RESULTS.md and the README results and highlights.

Usage (from ``backend/``)::

    uv run python ../scripts/make_results.py            # full refresh + incremental + tests
    uv run python ../scripts/make_results.py --skip-full   # reuse the current warehouse

Every number written here comes from code that ran in this invocation (or, with
--skip-full, from the last runs recorded in gold.pipeline_runs). Nothing is hard-coded.
"""

from __future__ import annotations

import argparse
import platform
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from cmdp.config import get_settings
from cmdp.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
README = ROOT / "README.md"
RESULTS = ROOT / "RESULTS.md"
HIGHLIGHTS_TEMPLATE = ROOT / "scripts" / "templates" / "highlights.md"


def run_tests() -> dict[str, float]:
    """Run pytest with a JUnit report and return counts and duration."""
    report = BACKEND / ".pytest_tmp_results.xml"
    t = time.perf_counter()
    subprocess.run(
        [sys.executable, "-m", "pytest", "-q", f"--junitxml={report}"],
        cwd=BACKEND,
        check=False,
    )
    elapsed = time.perf_counter() - t
    suite = ET.parse(report).getroot()
    suite = suite if suite.tag == "testsuite" else suite.find("testsuite")
    report.unlink(missing_ok=True)
    total = int(suite.get("tests", 0))
    failed = int(suite.get("failures", 0)) + int(suite.get("errors", 0))
    skipped = int(suite.get("skipped", 0))
    return {
        "total": total,
        "passed": total - failed - skipped,
        "failed": failed,
        "seconds": elapsed,
    }


def warehouse_metrics(db: Path) -> dict:
    """Query the published warehouse for the numbers reported in RESULTS.md."""
    con = duckdb.connect(str(db), read_only=True)

    def one(sql: str):
        return con.execute(sql).fetchone()

    try:
        m: dict = {}
        m["series_count"] = one("select count(*) from gold.dim_series")[0]
        m["series_by_source"] = dict(
            con.execute("select source, count(*) from gold.dim_series group by 1").fetchall()
        )
        m["row_count"], m["first_date"], m["last_date"] = one(
            "select count(*), min(obs_date), max(obs_date) from gold.fct_observation"
        )
        m["bronze_rows"] = one(
            "select (select count(*) from silver.stg_valet__observations)"
            " + (select count(*) from silver.stg_statcan__observations)"
        )[0]
        m["removed_rows"] = one("select count(*) from silver.int_observation_removals")[0]
        run_id = one("select run_id from gold.dq_results order by run_at desc limit 1")[0]
        m["dq_run_id"] = run_id
        rows = con.execute(
            "select dq_category, status, count(*) from gold.dq_results where run_id = ?"
            " group by 1, 2",
            [run_id],
        ).fetchall()
        m["dq_by_category"] = {}
        for cat, status, n in rows:
            m["dq_by_category"].setdefault(cat, {})[status] = n
        statuses = {
            s: sum(n for _, st, n in rows if st == s) for s in ("pass", "warn", "fail", "error")
        }
        m["dq_test_count"] = sum(statuses.values())
        m["dq_status"] = statuses
        m["dq_pass_rate"] = round(100 * statuses["pass"] / m["dq_test_count"], 1)
        m["anomalies"] = one("select count(*) from gold.dq_anomalies")[0]
        m["anomalies_by_series"] = dict(
            con.execute(
                "select series_key, count(*) from gold.dq_anomalies group by 1 order by 2 desc"
            ).fetchall()
        )
        m["missing_periods"] = one(
            "select coalesce(sum(missing_periods), 0) from gold.dq_completeness"
        )[0]
        m["stale_series"] = one("select count(*) from gold.dq_freshness where not is_fresh")[0]
        m["rate_decisions"] = one("select count(*) from gold.mart_policy_rate_events")[0]
        m["inverted_days"] = one("select count(*) from gold.mart_yield_curve where is_inverted")[0]
        m["curve_days"] = one("select count(*) from gold.mart_yield_curve")[0]
        runs = con.execute(
            "select run_id, mode, full_refresh, duration_s, extract_s, dbt_run_s, dbt_test_s,"
            " rows_extracted, finished_at from gold.pipeline_runs where mode = 'real'"
            " order by finished_at desc"
        ).fetchall()
        cols = [
            "run_id",
            "mode",
            "full_refresh",
            "duration_s",
            "extract_s",
            "dbt_run_s",
            "dbt_test_s",
            "rows_extracted",
            "finished_at",
        ]
        m["runs"] = [dict(zip(cols, r, strict=True)) for r in runs]
    finally:
        con.close()
    return m


def fmt_int(n: int) -> str:
    """Thousands separators."""
    return f"{n:,}"


def results_table(m: dict, full: dict | None, inc: dict | None, tests: dict) -> str:
    """Markdown table of the headline metrics."""
    rows = [
        (
            "Series loaded",
            f"{m['series_count']} ({m['series_by_source'].get('boc_valet', 0)} Bank of Canada, {m['series_by_source'].get('statcan_wds', 0)} Statistics Canada)",
        ),
        ("Rows in fct_observation", fmt_int(m["row_count"])),
        (
            "Rows in bronze / removed in silver",
            f"{fmt_int(m['bronze_rows'])} / {fmt_int(m['removed_rows'])}",
        ),
        ("Date range", f"{m['first_date']} to {m['last_date']}"),
        ("Data quality tests", str(m["dq_test_count"])),
        ("Pass rate (passed / total)", f"{m['dq_pass_rate']}%"),
        ("Tests by status", ", ".join(f"{k} {v}" for k, v in m["dq_status"].items())),
        ("Anomalies flagged (5σ, 250-day window)", str(m["anomalies"])),
        ("Missing business days / months", str(m["missing_periods"])),
        ("Stale series at as-of date", str(m["stale_series"])),
        ("Policy rate changes since 2015", str(m["rate_decisions"])),
        (
            "Inverted-curve days (2s10s < 0)",
            f"{fmt_int(m['inverted_days'])} of {fmt_int(m['curve_days'])}",
        ),
    ]
    if full:
        rows.append(
            (
                "Full pipeline runtime (full refresh)",
                f"{full['duration_s']:.1f} s (extract {full['extract_s']:.1f} s, dbt run {full['dbt_run_s']:.1f} s, dbt test {full['dbt_test_s']:.1f} s)",
            )
        )
    if inc:
        rows.append(
            (
                "Incremental runtime",
                f"{inc['duration_s']:.1f} s ({fmt_int(inc['rows_extracted'])} new rows)",
            )
        )
    rows.append(
        ("pytest", f"{tests['passed']} passed, {tests['failed']} failed ({tests['seconds']:.0f} s)")
    )
    lines = ["| Metric | Value |", "| --- | --- |"] + [f"| {a} | {b} |" for a, b in rows]
    return "\n".join(lines)


def replace_block(text: str, name: str, body: str) -> str:
    """Replace the content between <!-- NAME:START --> and <!-- NAME:END -->."""
    pattern = re.compile(rf"(<!-- {name}:START -->)(.*?)(<!-- {name}:END -->)", re.S)
    if not pattern.search(text):
        raise SystemExit(f"README is missing the {name} markers")
    return pattern.sub(lambda mo: f"{mo.group(1)}\n{body}\n{mo.group(3)}", text)


def main() -> None:
    """Measure, then write RESULTS.md and update README.md."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-full", action="store_true", help="do not re-run the pipelines")
    args = parser.parse_args()
    settings = get_settings()

    full = inc = None
    if not args.skip_full:
        print("== full refresh run (real data from 2015) ==", flush=True)
        r = run_pipeline(settings, full_refresh=True)
        full = {"duration_s": r.duration_s, **{f"{k}_s": v for k, v in r.timings_s.items()}}
        print("== incremental run ==", flush=True)
        r = run_pipeline(settings)
        inc = {"duration_s": r.duration_s, "rows_extracted": r.rows_extracted}

    m = warehouse_metrics(settings.gold_db)
    if args.skip_full:
        full_runs = [r for r in m["runs"] if r["full_refresh"]]
        inc_runs = [r for r in m["runs"] if not r["full_refresh"]]
        full = full_runs[0] if full_runs else None
        inc = inc_runs[0] if inc_runs else None

    print("== pytest ==", flush=True)
    tests = run_tests()
    table = results_table(m, full, inc, tests)
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    by_cat = "\n".join(
        f"| {cat} | "
        + " | ".join(str(counts.get(s, 0)) for s in ("pass", "warn", "fail", "error"))
        + " |"
        for cat, counts in sorted(m["dq_by_category"].items())
    )
    anomalies = (
        "\n".join(f"| {k} | {v} |" for k, v in m["anomalies_by_series"].items()) or "| – | 0 |"
    )
    RESULTS.write_text(
        f"""# Results

Generated by `make results` on {now} ({platform.system()} {platform.release()}, Python {platform.python_version()}).
Every number below was measured by `scripts/make_results.py` in that run; none is typed by hand.

## Headline metrics

{table}

## Data quality by control (run `{m["dq_run_id"]}`)

| Control | pass | warn | fail | error |
| --- | --- | --- | --- | --- |
{by_cat}

Monitoring controls (freshness, completeness, anomaly) use `warn` severity: they report source
issues without stopping the pipeline. Structural controls (integrity, range, reconciliation)
use `error` severity. Pass rate = tests with status `pass` / all tests.

## Anomalies flagged by series

| Series | Flags |
| --- | --- |
{anomalies}
""",
        encoding="utf-8",
        newline="\n",
    )

    values = {
        "series_count": str(m["series_count"]),
        "row_count": fmt_int(m["row_count"]),
        "dq_test_count": str(m["dq_test_count"]),
        "dq_pass_rate": str(m["dq_pass_rate"]),
    }
    highlights = HIGHLIGHTS_TEMPLATE.read_text(encoding="utf-8").strip()
    for key, val in values.items():
        highlights = highlights.replace("{" + key + "}", val)
    if "{" in highlights:
        raise SystemExit(f"unfilled placeholder in highlights: {highlights}")
    readme = README.read_text(encoding="utf-8")
    readme = replace_block(readme, "HIGHLIGHTS", highlights)
    readme = replace_block(
        readme,
        "RESULTS",
        f"{table}\n\n_Measured on {now} by `make results`. Details in [RESULTS.md](RESULTS.md)._",
    )
    README.write_text(readme, encoding="utf-8", newline="\n")
    print(table)


if __name__ == "__main__":
    main()
