"""API tests against the warehouse built from fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cmdp.api.main import create_app
from cmdp.config import Settings, get_settings


@pytest.fixture(scope="module")
def client(warehouse) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: warehouse
    return TestClient(app)


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["last_run_status"] == "success"
    assert body["as_of"] == "2024-12-31"
    assert body["total_observations"] > 5000


def test_health_without_warehouse(tmp_path):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    res = TestClient(app).get("/api/health")
    assert res.status_code == 503


def test_series_catalog(client):
    series = client.get("/api/series").json()
    assert len(series) == 15
    ten = next(s for s in series if s["series_key"] == "GOC_10Y")
    assert ten["source_id"] == "BD.CDN.10YR.DQ.YLD"
    assert ten["unit"] == "percent" and ten["freshness_status"] == "green"
    assert ten["source_url"].startswith("https://www.bankofcanada.ca/valet/")


def test_series_observations_filter(client):
    body = client.get("/api/series/goc_10y", params={"start": "2024-03-01", "end": "2024-03-31"})
    assert body.status_code == 200
    data = body.json()
    assert data["count"] == len(data["observations"]) > 15
    assert all("2024-03-01" <= o["date"] <= "2024-03-31" for o in data["observations"])


def test_series_errors(client):
    assert client.get("/api/series/NOPE").status_code == 404
    bad = client.get("/api/series/GOC_10Y", params={"start": "2024-05-01", "end": "2024-01-01"})
    assert bad.status_code == 422


def test_yield_curve_with_year_ago(client):
    body = client.get("/api/yield-curve", params={"date": "2024-12-15"}).json()
    assert body["current"]["date"] == "2024-12-13"  # 15th is a Sunday: previous business day
    assert body["year_ago"]["date"] <= "2023-12-15"
    assert [p["tenor"] for p in body["current"]["points"]] == ["2Y", "5Y", "10Y", "Long"]
    assert len(body["spread_history"]) > 400


def test_fx(client):
    assert "USDCAD" in client.get("/api/fx").json()
    body = client.get("/api/fx/usd-cad").json()
    assert body["pair"] == "USDCAD" and body["unit"] == "CAD per USD"
    assert body["latest"]["date"] == "2024-12-31"
    assert body["latest"]["vol_30d_pct"] > 0
    assert client.get("/api/fx/XXXCAD").status_code == 404


def test_policy_rate(client):
    body = client.get("/api/policy-rate").json()
    assert body["current_rate"] == 3.25
    assert body["events"] and body["monthly"]
    assert body["target_band"] == [1.0, 3.0]


def test_dq_summary(client):
    body = client.get("/api/dq/summary").json()
    assert body["total"] == body["passed"] + body["warned"] + body["failed"] + body["errored"]
    assert body["errored"] == 0 and body["failed"] == 0
    assert set(body["by_category"]) >= {"freshness", "completeness", "anomaly", "reconciliation"}
    assert len(body["freshness"]) == 15
    assert body["anomaly_count"] == len(body["anomalies"])


def test_overview(client):
    body = client.get("/api/overview").json()
    keys = [k["key"] for k in body["kpis"]]
    assert keys == ["policy_rate", "goc_10y", "spread_2s10s", "usdcad", "cpi_yoy"]
    spread = body["kpis"][2]
    assert spread["badge"] in {"inverted", "normal"}
    assert all(k["sparkline"] for k in body["kpis"])
