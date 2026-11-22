"""Read-only DuckDB access for the API.

Each request opens its own short-lived read-only connection to the published warehouse.
That keeps the file unlocked between requests so the pipeline can publish a new version.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated, Any

import duckdb
from fastapi import Depends, HTTPException

from cmdp.config import Settings, get_settings


def get_db(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Iterator[duckdb.DuckDBPyConnection]:
    """Yield a read-only connection to ``markets.duckdb`` or fail with HTTP 503."""
    if not settings.gold_db.exists():
        raise HTTPException(
            status_code=503,
            detail="The warehouse has not been built yet. Run `make pipeline` first.",
        )
    try:
        con = duckdb.connect(str(settings.gold_db), read_only=True)
    except duckdb.IOException as exc:  # file being replaced at this exact moment
        raise HTTPException(status_code=503, detail=f"Warehouse unavailable: {exc}") from exc
    try:
        yield con
    finally:
        con.close()


Db = Annotated[duckdb.DuckDBPyConnection, Depends(get_db)]


def rows(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> list[dict]:
    """Run a query and return a list of dicts (column name -> value)."""
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def one(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> dict | None:
    """Run a query and return the first row as a dict, or ``None``."""
    result = rows(con, sql, params)
    return result[0] if result else None
