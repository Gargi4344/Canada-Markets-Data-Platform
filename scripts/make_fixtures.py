"""Record small, real API samples into ``backend/tests/fixtures`` so CI runs offline.

Usage (from ``backend/``)::

    uv run python ../scripts/make_fixtures.py

The samples are tiny slices of public data: Valet daily series for 2023-2024 and CPI
vectors for 2022-2024. They are committed; the full history is always downloaded at
runtime and never committed.
"""

from __future__ import annotations

import json
from pathlib import Path

from cmdp.config import get_settings
from cmdp.extract.http import get_json, make_client
from cmdp.series import load_catalog

VALET_START, VALET_END = "2023-01-01", "2024-12-31"
CPI_START, CPI_END = "2022-01-01", "2024-12-01"


def main() -> None:
    """Download the fixture slices and write them as JSON."""
    settings = get_settings()
    catalog = load_catalog(settings.series_config)
    out = settings.fixtures_dir
    (out / "valet").mkdir(parents=True, exist_ok=True)
    (out / "statcan").mkdir(parents=True, exist_ok=True)
    with make_client() as client:
        for spec in catalog.by_source("boc_valet"):
            url = f"{settings.valet_base_url}/observations/{spec.source_id}/json"
            payload = get_json(client, url, {"start_date": VALET_START, "end_date": VALET_END})
            slim = {
                "seriesDetail": payload["seriesDetail"],
                "observations": payload["observations"],
            }
            path = out / "valet" / f"{spec.source_id}.json"
            path.write_text(json.dumps(slim, separators=(",", ":")), encoding="utf-8")
            print(f"{spec.source_id}: {len(slim['observations'])} observations")
        vectors = [s.source_id for s in catalog.by_source("statcan_wds")]
        payload = get_json(
            client,
            f"{settings.statcan_base_url}/getDataFromVectorByReferencePeriodRange",
            {
                "vectorIds": ",".join(f'"{v}"' for v in vectors),
                "startRefPeriod": CPI_START,
                "endReferencePeriod": CPI_END,
            },
        )
        keep = ("refPer", "value", "decimals", "releaseTime")
        for item in payload:
            item["object"]["vectorDataPoint"] = [
                {k: p[k] for k in keep} for p in item["object"]["vectorDataPoint"]
            ]
        path = out / "statcan" / "cpi_vectors.json"
        path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        print(f"statcan: {len(payload)} vectors")


if __name__ == "__main__":
    main()
