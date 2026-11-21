"""Unit tests for the extractors, retries, bronze writer and incremental loads."""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import polars as pl
import pytest
from tenacity import stop_after_attempt, wait_none

from cmdp.extract.bronze import last_loaded_date, new_load_id, write_bronze
from cmdp.extract.fixtures import fixture_as_of, fixture_transport
from cmdp.extract.http import get_json, make_client
from cmdp.extract.run import incremental_start, next_month, run_extract
from cmdp.extract.statcan import fetch_statcan_vectors
from cmdp.extract.valet import RawObservation, fetch_valet_series

from .conftest import FIXTURES

VALET = "https://www.bankofcanada.ca/valet"
WDS = "https://www150.statcan.gc.ca/t1/wds/rest"


def test_valet_parses_observations_and_missing_values():
    payload = {
        "observations": [
            {"d": "2024-01-02", "FXUSDCAD": {"v": "1.3316"}},
            {"d": "2024-01-03", "FXUSDCAD": {}},
        ]
    }
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
    with make_client(transport=transport) as client:
        rows, url = fetch_valet_series(client, VALET, "FXUSDCAD", date(2024, 1, 1))
    assert rows == [RawObservation("2024-01-02", "1.3316"), RawObservation("2024-01-03", None)]
    assert "start_date=2024-01-01" in url


def test_get_json_retries_transient_errors():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    fast = get_json.retry_with(wait=wait_none(), stop=stop_after_attempt(5))
    with make_client(transport=httpx.MockTransport(handler)) as client:
        assert fast(client, "https://example.test/x") == {"ok": True}
    assert calls["n"] == 3


def test_get_json_does_not_retry_client_errors():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404)

    fast = get_json.retry_with(wait=wait_none())
    with (
        make_client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        fast(client, "https://example.test/x")
    assert calls["n"] == 1


def test_statcan_parses_vectors_from_fixture():
    with make_client(transport=fixture_transport(FIXTURES)) as client:
        data, url = fetch_statcan_vectors(
            client, WDS, ["41690973", "41690974"], date(2024, 1, 1), date(2024, 12, 1)
        )
    assert set(data) == {"41690973", "41690974"}
    assert len(data["41690973"]) == 12
    assert data["41690973"][0].obs_date == "2024-01-01"
    assert "startRefPeriod=2024-01-01" in url


def test_incremental_start_rules():
    assert incremental_start(None, date(2015, 1, 1), "daily") == date(2015, 1, 1)
    assert incremental_start(date(2024, 3, 8), date(2015, 1, 1), "daily") == date(2024, 3, 9)
    assert incremental_start(date(2024, 12, 1), date(2015, 1, 1), "monthly") == date(2025, 1, 1)
    assert next_month(date(2024, 1, 31)) == date(2024, 2, 1)


def test_bronze_write_and_last_loaded_date(tmp_path):
    now = datetime(2024, 5, 1, 12, tzinfo=UTC)
    rows = [RawObservation("2024-04-29", "4.10"), RawObservation("2024-04-30", "4.12")]
    rec = write_bronze(
        tmp_path,
        "boc_valet",
        "GOC_10Y",
        "BD.CDN.10YR.DQ.YLD",
        rows,
        "L1",
        now,
        "u",
        date(2024, 4, 29),
    )
    assert rec.row_count == 2 and rec.max_obs_date == "2024-04-30"
    df = pl.read_parquet(rec.file_path)
    assert df.columns == [
        "series_key",
        "source_id",
        "obs_date",
        "value_raw",
        "load_id",
        "loaded_at",
        "source_url",
    ]
    assert last_loaded_date(tmp_path, "boc_valet", "GOC_10Y") == date(2024, 4, 30)
    empty = write_bronze(tmp_path, "boc_valet", "X", "X", [], "L2", now, "u", date(2024, 5, 1))
    assert empty.row_count == 0 and empty.file_path is None
    assert last_loaded_date(tmp_path, "boc_valet", "X") is None


def test_incremental_load_only_fetches_new_dates(settings, catalog):
    bronze = settings.bronze_dir
    with make_client(transport=fixture_transport(FIXTURES)) as client:
        first = run_extract(client, catalog, bronze, VALET, WDS, new_load_id(), date(2024, 6, 28))
        second = run_extract(client, catalog, bronze, VALET, WDS, new_load_id(), date(2024, 12, 31))
        third = run_extract(client, catalog, bronze, VALET, WDS, new_load_id(), date(2024, 12, 31))

    first_rows = {r.series_key: r for r in first}
    second_rows = {r.series_key: r for r in second}
    assert first_rows["GOC_10Y"].max_obs_date <= "2024-06-28"
    assert second_rows["GOC_10Y"].min_obs_date > first_rows["GOC_10Y"].max_obs_date
    assert second_rows["CPI_ALL"].min_obs_date == "2024-07-01"
    assert sum(r.row_count for r in third) == 0

    stored = pl.read_parquet(str(bronze / "boc_valet" / "GOC_10Y" / "**" / "*.parquet"))
    assert stored["obs_date"].n_unique() == stored.height  # no duplicates across loads
    loads = pl.read_parquet(str(bronze / "_loads" / "**" / "*.parquet"))
    assert loads["load_id"].n_unique() == 3


def test_fixture_as_of_is_latest_fixture_date():
    assert fixture_as_of(FIXTURES) == "2024-12-31"
