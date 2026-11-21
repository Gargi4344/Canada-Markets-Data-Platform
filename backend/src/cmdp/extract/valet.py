"""Bank of Canada Valet API extractor.

Docs: https://www.bankofcanada.ca/valet/docs
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import httpx

from cmdp.extract.http import get_json


@dataclass(frozen=True)
class RawObservation:
    """One observation exactly as the source returned it (value kept as text)."""

    obs_date: str
    value_raw: str | None


def observations_url(base_url: str, series_id: str) -> str:
    """Return the Valet observations URL for one series."""
    return f"{base_url.rstrip('/')}/observations/{series_id}/json"


def fetch_valet_series(
    client: httpx.Client,
    base_url: str,
    series_id: str,
    start_date: date,
    end_date: date | None = None,
) -> tuple[list[RawObservation], str]:
    """Fetch observations for ``series_id`` on or after ``start_date``.

    Returns the raw observations and the exact URL that was requested.
    """
    url = observations_url(base_url, series_id)
    params: dict[str, str] = {"start_date": start_date.isoformat()}
    if end_date is not None:
        params["end_date"] = end_date.isoformat()
    payload = get_json(client, url, params)
    rows: list[RawObservation] = []
    for obs in payload.get("observations", []):
        cell = obs.get(series_id) or {}
        value = cell.get("v")
        rows.append(
            RawObservation(obs_date=obs["d"], value_raw=None if value is None else str(value))
        )
    full_url = str(httpx.URL(url, params=params))
    return rows, full_url
