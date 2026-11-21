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


@pytest.fixture(scope="session")
def warehouse_report(tmp_path_factory: pytest.TempPathFactory):
    """Run the full pipeline once on fixtures (offline) and return its report."""
    from cmdp.pipeline import run_pipeline

    base = Settings(data_dir=tmp_path_factory.mktemp("warehouse") / "data")
    report = run_pipeline(base, fixtures=True, full_refresh=True)
    report.settings = fixture_settings_for(base)
    return report


@pytest.fixture(scope="session")
def warehouse(warehouse_report) -> Settings:
    """Settings that point at the fixture warehouse built by ``warehouse_report``."""
    return warehouse_report.settings


def fixture_settings_for(base: Settings) -> Settings:
    """Return the settings fixture mode uses for a given base."""
    from cmdp.pipeline import fixture_settings

    return fixture_settings(base)
