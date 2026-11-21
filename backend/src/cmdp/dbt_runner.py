"""Thin wrapper around dbt's programmatic runner."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from cmdp.config import Settings


@dataclass
class DbtResult:
    """Outcome of one dbt command."""

    command: str
    success: bool
    run_results: dict | None


def dbt_env(settings: Settings) -> dict[str, str]:
    """Environment variables that tell the dbt project where bronze and DuckDB live."""
    return {
        "CMDP_BRONZE_PATH": settings.bronze_dir.resolve().as_posix(),
        "CMDP_DBT_DB_PATH": settings.build_db.resolve().as_posix(),
    }


def run_dbt(settings: Settings, args: list[str], as_of: str | None = None) -> DbtResult:
    """Run a dbt command (for example ``["run"]``) against the project and return its result.

    ``success`` is False only when dbt itself errors or a test with ``error`` severity
    fails; warnings do not fail the command.
    """
    settings.warehouse_dir.mkdir(parents=True, exist_ok=True)
    project = str(settings.dbt_project_dir)
    run_results_path = Path(project) / "target" / "run_results.json"
    run_results_path.unlink(missing_ok=True)
    full = [
        *args,
        "--project-dir",
        project,
        "--profiles-dir",
        project,
        "--vars",
        json.dumps({"as_of": as_of or ""}),
    ]
    # A subprocess guarantees DuckDB releases its file lock when dbt finishes, so the
    # warehouse can be published right after (an in-process run keeps the file open).
    proc = subprocess.run(
        [sys.executable, "-c", "from dbt.cli.main import cli; cli()", *full],
        env={**os.environ, **dbt_env(settings)},
        check=False,
    )
    run_results = (
        json.loads(run_results_path.read_text(encoding="utf-8"))
        if run_results_path.exists()
        else None
    )
    return DbtResult(command=" ".join(args), success=proc.returncode == 0, run_results=run_results)


def load_manifest(settings: Settings) -> dict:
    """Return the parsed ``target/manifest.json`` of the last dbt invocation."""
    path = settings.dbt_project_dir / "target" / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))
