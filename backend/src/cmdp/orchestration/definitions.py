"""Dagster definitions for the medallion pipeline.

Asset graph (see the lineage view in the Dagster UI)::

    bronze/*  (Python extract)  ->  silver dbt models  ->  gold dbt marts  ->
    data_quality/dq_results (dbt test -> gold.dq_results)  ->  serving/markets_warehouse

Start the UI with ``make dagster`` (http://localhost:3070). The ``daily_refresh`` schedule
runs every weekday at 18:00 Toronto time, after the Bank of Canada publishes its daily data.
"""

# No `from __future__ import annotations`: Dagster inspects the real context type hints.

import json
import os
from collections.abc import Iterator, Mapping
from datetime import date
from typing import Any

from dagster import (
    AssetExecutionContext,
    AssetKey,
    AssetSelection,
    AssetSpec,
    DefaultScheduleStatus,
    Definitions,
    MaterializeResult,
    MetadataValue,
    ScheduleDefinition,
    asset,
    define_asset_job,
    multi_asset,
)
from dagster_dbt import (
    DagsterDbtTranslator,
    DagsterDbtTranslatorSettings,
    DbtCliResource,
    DbtProject,
    dbt_assets,
)

from cmdp.config import get_settings
from cmdp.dbt_runner import dbt_env, run_dbt
from cmdp.extract.bronze import new_load_id
from cmdp.pipeline import publish, step_extract, step_quality
from cmdp.series import load_catalog

SETTINGS = get_settings()
os.environ.update(dbt_env(SETTINGS))

DBT_PROJECT = DbtProject(
    project_dir=SETTINGS.dbt_project_dir,
    profiles_dir=SETTINGS.dbt_project_dir,
    install_deps=False,
)
DBT_PROJECT.prepare_if_dev()
if not DBT_PROJECT.manifest_path.exists():  # fresh checkout or CI: build the manifest once
    run_dbt(SETTINGS, ["parse"])

BRONZE_KEYS = ["series_catalog", "calendar", "boc_valet", "statcan_wds", "load_log"]


class MedallionTranslator(DagsterDbtTranslator):
    """Group dbt models by medallion layer, using their folder in the dbt project."""

    def get_asset_spec(
        self, manifest: Mapping[str, Any], unique_id: str, project: DbtProject | None
    ) -> AssetSpec:
        """Return the default spec with the group set to silver, gold or data_quality."""
        spec = super().get_asset_spec(manifest, unique_id, project)
        node = manifest.get("nodes", {}).get(unique_id)
        if node is None:  # sources keep their bronze keys and group
            return spec
        folder = node.get("fqn", ["", ""])[1]
        group = {"staging": "silver", "silver": "silver", "marts": "gold", "dq": "data_quality"}
        return spec.replace_attributes(group_name=group.get(folder, "gold"))


@multi_asset(
    specs=[
        AssetSpec(
            ["bronze", key],
            group_name="bronze",
            description=f"Raw Parquet files in data/bronze ({key}).",
        )
        for key in BRONZE_KEYS
    ],
    name="bronze_extract",
)
def bronze_extract(context: AssetExecutionContext) -> Iterator[MaterializeResult]:
    """Incrementally extract Bank of Canada and Statistics Canada data to bronze Parquet."""
    catalog = load_catalog(SETTINGS.series_config)
    records = step_extract(SETTINGS, catalog, date.today(), new_load_id())
    by_source = {"boc_valet": 0, "statcan_wds": 0}
    for r in records:
        by_source[r.source] = by_source.get(r.source, 0) + r.row_count
    context.log.info("new rows per source: %s", by_source)
    for key in BRONZE_KEYS:
        meta: dict[str, Any] = {}
        if key in by_source:
            meta["new_rows"] = by_source[key]
        if key == "load_log":
            meta["series_loaded"] = len(records)
        yield MaterializeResult(asset_key=AssetKey(["bronze", key]), metadata=meta)


@dbt_assets(
    manifest=DBT_PROJECT.manifest_path,
    project=DBT_PROJECT,
    dagster_dbt_translator=MedallionTranslator(
        settings=DagsterDbtTranslatorSettings(enable_asset_checks=False)
    ),
)
def cmdp_dbt_models(context: AssetExecutionContext, dbt: DbtCliResource):
    """Build the silver and gold dbt models (``dbt run``)."""
    args = ["run", "--vars", json.dumps({"as_of": date.today().isoformat()})]
    yield from dbt.cli(args, context=context).stream()


@asset(
    key=["data_quality", "dq_results"],
    deps=[cmdp_dbt_models],
    group_name="data_quality",
    description="Runs every dbt data test and appends the outcomes to gold.dq_results.",
)
def dq_results(context: AssetExecutionContext) -> MaterializeResult:
    """Run the data quality controls and store their results."""
    summary, ok = step_quality(SETTINGS, context.run_id, date.today())
    if not ok:
        context.log.warning("error-severity data quality tests failed: %s", summary)
    return MaterializeResult(
        metadata={k: MetadataValue.float(float(v)) for k, v in summary.items()}
    )


@asset(
    key=["serving", "markets_warehouse"],
    deps=[dq_results],
    group_name="serving",
    description="Publishes data/warehouse/markets.duckdb, which the FastAPI service reads.",
)
def markets_warehouse() -> MaterializeResult:
    """Copy the build warehouse to the published file the API reads."""
    publish(SETTINGS)
    return MaterializeResult(metadata={"path": MetadataValue.path(str(SETTINGS.gold_db))})


daily_refresh_job = define_asset_job("daily_refresh", selection=AssetSelection.all())

daily_refresh_schedule = ScheduleDefinition(
    job=daily_refresh_job,
    cron_schedule="0 18 * * 1-5",
    execution_timezone="America/Toronto",
    default_status=DefaultScheduleStatus.RUNNING,
)

defs = Definitions(
    assets=[bronze_extract, cmdp_dbt_models, dq_results, markets_warehouse],
    jobs=[daily_refresh_job],
    schedules=[daily_refresh_schedule],
    resources={"dbt": DbtCliResource(project_dir=DBT_PROJECT)},
)
