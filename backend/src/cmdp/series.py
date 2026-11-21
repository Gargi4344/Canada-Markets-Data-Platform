"""Load and validate the series catalog in ``config/series.yaml``."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class SeriesSpec(BaseModel):
    """One time series that the platform ingests."""

    key: str
    source_id: str
    source: Literal["boc_valet", "statcan_wds"]
    category: Literal["policy_rate", "money_market", "bond_yield", "fx", "cpi"]
    name: str
    unit: str
    unit_multiplier: float = 1.0
    frequency: Literal["daily", "monthly"]
    freshness_max_business_days: int = 5
    anomaly_check: bool = True
    range: tuple[float, float]
    description: str


class Catalog(BaseModel):
    """The whole catalog: a start date plus the list of series."""

    start_date: date
    series: list[SeriesSpec] = Field(min_length=1)

    def by_source(self, source: str) -> list[SeriesSpec]:
        """Return the series that come from one source."""
        return [s for s in self.series if s.source == source]

    def get(self, key: str) -> SeriesSpec:
        """Return one series by key or raise ``KeyError``."""
        for s in self.series:
            if s.key == key:
                return s
        raise KeyError(key)


def load_catalog(path: Path) -> Catalog:
    """Parse and validate the YAML catalog."""
    with path.open(encoding="utf-8") as fh:
        return Catalog.model_validate(yaml.safe_load(fh))
