"""Serve recorded API responses from ``tests/fixtures`` so the pipeline runs offline.

The transport honours ``start_date`` and ``startRefPeriod`` so incremental loads behave
exactly as they do against the real APIs.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx


def fixture_transport(fixtures_dir: Path) -> httpx.MockTransport:
    """Return an ``httpx.MockTransport`` backed by JSON files in ``fixtures_dir``."""
    valet_dir = fixtures_dir / "valet"
    statcan_file = fixtures_dir / "statcan" / "cpi_vectors.json"

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/valet/observations/" in path:
            series_id = path.split("/observations/")[1].split("/")[0]
            file = valet_dir / f"{series_id}.json"
            if not file.exists():
                return httpx.Response(404, json={"message": f"Series {series_id} not found."})
            payload = json.loads(file.read_text(encoding="utf-8"))
            start = request.url.params.get("start_date")
            end = request.url.params.get("end_date")
            payload["observations"] = [
                o
                for o in payload["observations"]
                if (start is None or o["d"] >= start) and (end is None or o["d"] <= end)
            ]
            return httpx.Response(200, json=payload)
        if path.endswith("/getDataFromVectorByReferencePeriodRange"):
            wanted = {v.strip('"') for v in request.url.params["vectorIds"].split(",")}
            start = request.url.params["startRefPeriod"]
            end = request.url.params["endReferencePeriod"]
            payload = json.loads(statcan_file.read_text(encoding="utf-8"))
            out = []
            for item in payload:
                obj = dict(item["object"])
                if str(obj["vectorId"]) not in wanted:
                    continue
                obj["vectorDataPoint"] = [
                    p for p in obj["vectorDataPoint"] if start <= p["refPer"] <= end
                ]
                out.append({"status": "SUCCESS", "object": obj})
            return httpx.Response(200, json=out)
        return httpx.Response(404, json={"message": "unknown fixture route"})

    return httpx.MockTransport(handler)


def fixture_as_of(fixtures_dir: Path) -> str:
    """Return the latest observation date in the Valet fixtures (the fixture "today")."""
    latest = ""
    for file in (fixtures_dir / "valet").glob("*.json"):
        obs = json.loads(file.read_text(encoding="utf-8"))["observations"]
        if obs:
            latest = max(latest, obs[-1]["d"])
    return latest
