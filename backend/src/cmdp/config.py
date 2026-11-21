"""Runtime settings and well-known paths.

All paths can be overridden with environment variables prefixed ``CMDP_`` (see ``.env.example``).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Settings for the pipeline and the API."""

    model_config = SettingsConfigDict(
        env_prefix="CMDP_", env_file=REPO_DIR / ".env", extra="ignore"
    )

    data_dir: Path = REPO_DIR / "data"
    series_config: Path = BACKEND_DIR / "config" / "series.yaml"
    dbt_project_dir: Path = BACKEND_DIR / "dbt"
    fixtures_dir: Path = BACKEND_DIR / "tests" / "fixtures"
    valet_base_url: str = "https://www.bankofcanada.ca/valet"
    statcan_base_url: str = "https://www150.statcan.gc.ca/t1/wds/rest"
    http_timeout_seconds: float = 60.0
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def bronze_dir(self) -> Path:
        """Root of the raw (bronze) Parquet layer."""
        return self.data_dir / "bronze"

    @property
    def warehouse_dir(self) -> Path:
        """Directory that holds the DuckDB files."""
        return self.data_dir / "warehouse"

    @property
    def build_db(self) -> Path:
        """DuckDB file that dbt writes to during a run."""
        return self.warehouse_dir / "build.duckdb"

    @property
    def gold_db(self) -> Path:
        """Published DuckDB file that the API reads (read-only)."""
        return self.warehouse_dir / "gold.duckdb"

    @property
    def runs_dir(self) -> Path:
        """Directory with one JSON record per pipeline run."""
        return self.data_dir / "runs"


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings object."""
    return Settings()
