"""Shared HTTP helpers: one client factory and a JSON fetch with retries."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger(__name__)

USER_AGENT = "canada-markets-data-platform/0.1 (open-source data pipeline)"


def _is_retryable(exc: BaseException) -> bool:
    """Retry on network errors, timeouts, HTTP 429 and HTTP 5xx."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or code >= 500
    return False


def make_client(
    timeout: float = 60.0, transport: httpx.BaseTransport | None = None
) -> httpx.Client:
    """Create an ``httpx.Client`` with a polite user agent.

    Pass ``transport`` to serve responses from local fixtures instead of the internet.
    """
    return httpx.Client(
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        transport=transport,
        follow_redirects=True,
    )


@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=20),
    before_sleep=before_sleep_log(log, logging.WARNING),
    reraise=True,
)
def get_json(client: httpx.Client, url: str, params: dict[str, Any] | None = None) -> Any:
    """GET ``url`` and return the decoded JSON body, retrying transient failures."""
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.json()
