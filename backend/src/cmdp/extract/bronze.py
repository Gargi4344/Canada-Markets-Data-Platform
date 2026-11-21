"""Write raw observations to the bronze Parquet layer and read incremental state.

Layout::

    data/bronze/<source>/<series_key>/load_date=YYYY-MM-DD/<load_id>.parquet
    data/bronze/_loads/load_date=YYYY-MM-DD/<load_id>.parquet   (one row per series per load)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl

from cmdp.extract.valet import RawObservation

BRONZE_SCHEMA = {
    "series_key": pl.String,
    "source_id": pl.String,
    "obs_date": pl.String,
    "value_raw": pl.String,
    "load_id": pl.String,
    "loaded_at": pl.Datetime("us", "UTC"),
    "source_url": pl.String,
}


@dataclass
class LoadRecord:
    """Metadata about one incremental load of one series."""

    load_id: str
    source: str
    series_key: str
    source_id: str
    requested_start: str
    row_count: int
    min_obs_date: str | None
    max_obs_date: str | None
    source_url: str
    loaded_at: datetime
    file_path: str | None


def series_dir(bronze_dir: Path, source: str, series_key: str) -> Path:
    """Directory that holds every load of one series."""
    return bronze_dir / source / series_key


def last_loaded_date(bronze_dir: Path, source: str, series_key: str) -> date | None:
    """Return the latest observation date already stored for a series, or ``None``."""
    files = sorted(series_dir(bronze_dir, source, series_key).glob("load_date=*/*.parquet"))
    if not files:
        return None
    return (
        pl.scan_parquet([str(f) for f in files])
        .select(pl.col("obs_date").str.to_date().max())
        .collect()
        .item()
    )


def write_bronze(
    bronze_dir: Path,
    source: str,
    series_key: str,
    source_id: str,
    rows: list[RawObservation],
    load_id: str,
    loaded_at: datetime,
    source_url: str,
    requested_start: date,
) -> LoadRecord:
    """Write one series' new rows as a Parquet file and return its load record.

    Nothing is written when ``rows`` is empty, but the load is still recorded.
    """
    file_path: Path | None = None
    if rows:
        n = len(rows)
        df = pl.DataFrame(
            {
                "series_key": [series_key] * n,
                "source_id": [source_id] * n,
                "obs_date": [r.obs_date for r in rows],
                "value_raw": [r.value_raw for r in rows],
                "load_id": [load_id] * n,
                "loaded_at": [loaded_at] * n,
                "source_url": [source_url] * n,
            },
            schema=BRONZE_SCHEMA,
        )
        out_dir = series_dir(bronze_dir, source, series_key) / f"load_date={loaded_at.date()}"
        out_dir.mkdir(parents=True, exist_ok=True)
        file_path = out_dir / f"{load_id}.parquet"
        df.write_parquet(file_path)
    dates = sorted(r.obs_date for r in rows)
    return LoadRecord(
        load_id=load_id,
        source=source,
        series_key=series_key,
        source_id=source_id,
        requested_start=requested_start.isoformat(),
        row_count=len(rows),
        min_obs_date=dates[0] if dates else None,
        max_obs_date=dates[-1] if dates else None,
        source_url=source_url,
        loaded_at=loaded_at,
        file_path=None if file_path is None else file_path.as_posix(),
    )


def write_load_log(bronze_dir: Path, records: list[LoadRecord]) -> Path | None:
    """Write the load records of one run to the bronze load log."""
    if not records:
        return None
    df = pl.DataFrame(
        [asdict(r) for r in records],
        schema={
            "load_id": pl.String,
            "source": pl.String,
            "series_key": pl.String,
            "source_id": pl.String,
            "requested_start": pl.String,
            "row_count": pl.Int64,
            "min_obs_date": pl.String,
            "max_obs_date": pl.String,
            "source_url": pl.String,
            "loaded_at": pl.Datetime("us", "UTC"),
            "file_path": pl.String,
        },
    )
    first = records[0]
    out_dir = bronze_dir / "_loads" / f"load_date={first.loaded_at.date()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{first.load_id}.parquet"
    df.write_parquet(path)
    return path


def new_load_id(now: datetime | None = None) -> str:
    """Return a sortable load id such as ``20250101T120000123456Z``."""
    now = now or datetime.now(UTC)
    return now.strftime("%Y%m%dT%H%M%S%fZ")
