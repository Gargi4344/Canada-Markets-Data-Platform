"""Turn dbt test results into rows of the ``gold.dq_results`` table.

Every data test that dbt runs becomes one row with its control category, the table it
checks, its status (pass / warn / fail / error), the number of failing rows and timing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

# Map dbt test names to the data quality control they implement.
CATEGORY_BY_TEST = {
    "not_null": "integrity",
    "unique": "integrity",
    "unique_combination": "integrity",
    "relationships": "integrity",
    "accepted_values": "integrity",
    "value_between": "range",
    "values_within_catalog_range": "range",
    "freshness_within_threshold": "freshness",
    "no_missing_periods": "completeness",
    "no_anomalies": "anomaly",
    "reconciles": "reconciliation",
}

DQ_RESULTS_DDL = """
create schema if not exists gold;
create table if not exists gold.dq_results (
    run_id varchar,
    run_at timestamptz,
    test_unique_id varchar,
    test_name varchar,
    test_type varchar,
    dq_category varchar,
    table_name varchar,
    column_name varchar,
    severity varchar,
    status varchar,
    failed_rows bigint,
    execution_time_s double,
    message varchar
);
"""


@dataclass
class DqRow:
    """One data quality test outcome."""

    run_id: str
    run_at: datetime
    test_unique_id: str
    test_name: str
    test_type: str
    dq_category: str
    table_name: str | None
    column_name: str | None
    severity: str
    status: str
    failed_rows: int
    execution_time_s: float
    message: str | None


def _table_of(node: dict, manifest: dict) -> str | None:
    """Return the name of the model a test is attached to."""
    attached = node.get("attached_node")
    if attached and attached in manifest["nodes"]:
        return manifest["nodes"][attached]["name"]
    for dep in node.get("depends_on", {}).get("nodes", []):
        if dep.startswith("model."):
            return manifest["nodes"][dep]["name"]
    return None


def collect_dq_rows(run_results: dict, manifest: dict, run_id: str) -> list[DqRow]:
    """Build one ``DqRow`` per test in a dbt ``run_results.json``."""
    run_at = datetime.now(UTC)
    rows: list[DqRow] = []
    for result in run_results.get("results", []):
        uid = result["unique_id"]
        if not uid.startswith("test."):
            continue
        node = manifest["nodes"][uid]
        meta = node.get("test_metadata") or {}
        test_type = meta.get("name", "singular")
        kwargs = meta.get("kwargs") or {}
        rows.append(
            DqRow(
                run_id=run_id,
                run_at=run_at,
                test_unique_id=uid,
                test_name=node["name"],
                test_type=test_type,
                dq_category=CATEGORY_BY_TEST.get(test_type, "integrity"),
                table_name=_table_of(node, manifest),
                column_name=kwargs.get("column_name") or node.get("column_name"),
                severity=str(node.get("config", {}).get("severity", "ERROR")).lower(),
                status=result["status"],
                failed_rows=int(result.get("failures") or 0),
                execution_time_s=float(result.get("execution_time") or 0.0),
                message=result.get("message"),
            )
        )
    return rows


def write_dq_rows(db_path: Path, rows: list[DqRow]) -> int:
    """Append rows to ``gold.dq_results`` in the DuckDB file. Returns the number written."""
    con = duckdb.connect(str(db_path))
    try:
        con.execute(DQ_RESULTS_DDL)
        con.executemany(
            "insert into gold.dq_results values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    r.run_id,
                    r.run_at,
                    r.test_unique_id,
                    r.test_name,
                    r.test_type,
                    r.dq_category,
                    r.table_name,
                    r.column_name,
                    r.severity,
                    r.status,
                    r.failed_rows,
                    r.execution_time_s,
                    r.message,
                )
                for r in rows
            ],
        )
    finally:
        con.close()
    return len(rows)


def summarise(rows: list[DqRow]) -> dict[str, int | float]:
    """Return pass / warn / fail counts and the pass rate (passed / total, percent)."""
    total = len(rows)
    counts = {s: sum(r.status == s for r in rows) for s in ("pass", "warn", "fail", "error")}
    rate = round(100.0 * counts["pass"] / total, 1) if total else 0.0
    return {"total": total, **counts, "pass_rate_pct": rate}
