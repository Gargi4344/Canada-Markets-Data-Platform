"""Run the incremental extract for every series in the catalog."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

from cmdp.extract.bronze import LoadRecord, last_loaded_date, write_bronze, write_load_log
from cmdp.extract.statcan import fetch_statcan_vectors
from cmdp.extract.valet import RawObservation, fetch_valet_series
from cmdp.series import Catalog, SeriesSpec

log = logging.getLogger(__name__)


def next_month(d: date) -> date:
    """Return the first day of the month after ``d``."""
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def incremental_start(last: date | None, default: date, frequency: str) -> date:
    """Return the first date to request: the day (or month) after the last loaded one."""
    if last is None:
        return default
    return next_month(last) if frequency == "monthly" else last + timedelta(days=1)


def extract_valet(
    client: httpx.Client,
    base_url: str,
    catalog: Catalog,
    bronze_dir: Path,
    load_id: str,
    loaded_at: datetime,
    today: date,
) -> list[LoadRecord]:
    """Incrementally load every Bank of Canada Valet series."""
    records = []
    for spec in catalog.by_source("boc_valet"):
        last = last_loaded_date(bronze_dir, spec.source, spec.key)
        start = incremental_start(last, catalog.start_date, spec.frequency)
        rows: list[RawObservation] = []
        url = f"{base_url}/observations/{spec.source_id}/json (skipped: already up to date)"
        if start <= today:
            rows, url = fetch_valet_series(client, base_url, spec.source_id, start, today)
            rows = [r for r in rows if r.obs_date >= start.isoformat()]
        rec = write_bronze(
            bronze_dir, spec.source, spec.key, spec.source_id, rows, load_id, loaded_at, url, start
        )
        log.info("valet   %-12s start=%s new_rows=%d", spec.key, start, rec.row_count)
        records.append(rec)
    return records


def extract_statcan(
    client: httpx.Client,
    base_url: str,
    catalog: Catalog,
    bronze_dir: Path,
    load_id: str,
    loaded_at: datetime,
    today: date,
) -> list[LoadRecord]:
    """Incrementally load every Statistics Canada vector (one request per start month)."""
    # CPI year-over-year needs the 12 months before the catalog start date.
    default = date(catalog.start_date.year - 1, catalog.start_date.month, 1)
    by_start: dict[date, list[SeriesSpec]] = {}
    for spec in catalog.by_source("statcan_wds"):
        last = last_loaded_date(bronze_dir, spec.source, spec.key)
        by_start.setdefault(incremental_start(last, default, spec.frequency), []).append(spec)
    records = []
    for start, group in sorted(by_start.items()):
        data: dict[str, list[RawObservation]] = {s.source_id: [] for s in group}
        url = "statcan getDataFromVectorByReferencePeriodRange (skipped: already up to date)"
        if start <= today:
            data, url = fetch_statcan_vectors(
                client, base_url, [s.source_id for s in group], start, today
            )
        for spec in group:
            rows = [r for r in data.get(spec.source_id, []) if r.obs_date >= start.isoformat()]
            rec = write_bronze(
                bronze_dir,
                spec.source,
                spec.key,
                spec.source_id,
                rows,
                load_id,
                loaded_at,
                url,
                start,
            )
            log.info("statcan %-12s start=%s new_rows=%d", spec.key, start, rec.row_count)
            records.append(rec)
    return records


def run_extract(
    client: httpx.Client,
    catalog: Catalog,
    bronze_dir: Path,
    valet_base_url: str,
    statcan_base_url: str,
    load_id: str,
    today: date | None = None,
) -> list[LoadRecord]:
    """Extract every source incrementally and write the load log. Returns the load records."""
    loaded_at = datetime.now(UTC)
    today = today or loaded_at.date()
    records = extract_valet(client, valet_base_url, catalog, bronze_dir, load_id, loaded_at, today)
    records += extract_statcan(
        client, statcan_base_url, catalog, bronze_dir, load_id, loaded_at, today
    )
    write_load_log(bronze_dir, records)
    return records
