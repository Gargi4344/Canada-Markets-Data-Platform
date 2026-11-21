"""Statistics Canada Web Data Service (WDS) extractor.

Docs: https://www.statcan.gc.ca/en/developers/wds/user-guide
"""

from __future__ import annotations

from datetime import date

import httpx

from cmdp.extract.http import get_json
from cmdp.extract.valet import RawObservation


def range_url(base_url: str) -> str:
    """Return the WDS endpoint that returns vector data for a reference-period range."""
    return f"{base_url.rstrip('/')}/getDataFromVectorByReferencePeriodRange"


def fetch_statcan_vectors(
    client: httpx.Client,
    base_url: str,
    vector_ids: list[str],
    start_ref: date,
    end_ref: date,
) -> tuple[dict[str, list[RawObservation]], str]:
    """Fetch monthly data points for several vectors between two reference periods.

    Returns a mapping ``vector_id -> observations`` and the URL that was requested.
    """
    url = range_url(base_url)
    params = {
        "vectorIds": ",".join(f'"{v}"' for v in vector_ids),
        "startRefPeriod": start_ref.isoformat(),
        "endReferencePeriod": end_ref.isoformat(),
    }
    payload = get_json(client, url, params)
    out: dict[str, list[RawObservation]] = {v: [] for v in vector_ids}
    for item in payload:
        if item.get("status") != "SUCCESS":
            continue
        obj = item["object"]
        vid = str(obj["vectorId"])
        for point in obj.get("vectorDataPoint", []):
            value = point.get("value")
            out.setdefault(vid, []).append(
                RawObservation(
                    obs_date=point["refPer"], value_raw=None if value is None else str(value)
                )
            )
    return out, str(httpx.URL(url, params=params))
