"""Shared pytest fixtures: settings that point at a temporary data directory."""

from __future__ import annotations

from pathlib import Path

import pytest

from cmdp.config import BACKEND_DIR, Settings
from cmdp.series import Catalog, load_catalog

FIXTURES = BACKEND_DIR / "tests" / "fixtures"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings whose data directory is an empty temporary folder."""
    return Settings(data_dir=tmp_path / "data")


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    """The real series catalog from ``config/series.yaml``."""
    return load_catalog(BACKEND_DIR / "config" / "series.yaml")
