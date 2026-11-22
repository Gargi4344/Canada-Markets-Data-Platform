"""Generate docs/DATA_DICTIONARY.md from the dbt schema.yml and sources.yml files.

Usage (from ``backend/``)::

    uv run python ../scripts/gen_data_dictionary.py
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "backend" / "dbt" / "models"
OUT = ROOT / "docs" / "DATA_DICTIONARY.md"

LAYERS = [
    ("staging", "Silver: staging", "silver"),
    ("silver", "Silver: cleaning and checks", "silver"),
    ("marts", "Gold: star schema and marts", "gold"),
    ("dq", "Gold: data quality models", "gold"),
]


def test_names(tests: list | None) -> str:
    """Render a list of dbt data tests as short names."""
    names = []
    for t in tests or []:
        if isinstance(t, str):
            names.append(t)
        else:
            (kind, cfg), *_ = t.items()
            names.append((cfg or {}).get("name", kind) if isinstance(cfg, dict) else kind)
    return ", ".join(f"`{n}`" for n in names)


def clean(text: str | None) -> str:
    """Collapse whitespace and escape pipes for a Markdown table cell."""
    return " ".join((text or "").split()).replace("|", "\\|")


def render_model(model: dict, schema: str) -> list[str]:
    """Markdown for one model: description, model-level tests and a column table."""
    lines = [f"### `{schema}.{model['name']}`", "", clean(model.get("description")), ""]
    if model.get("data_tests"):
        lines += [f"Model tests: {test_names(model['data_tests'])}", ""]
    cols = model.get("columns") or []
    if cols:
        lines += ["| Column | Description | Tests |", "| --- | --- | --- |"]
        for c in cols:
            lines.append(
                f"| `{c['name']}` | {clean(c.get('description'))} | {test_names(c.get('data_tests'))} |"
            )
        lines.append("")
    return lines


def main() -> None:
    """Write the data dictionary."""
    lines = [
        "# Data dictionary",
        "",
        "Generated from the dbt `schema.yml` and `sources.yml` files by",
        "`scripts/gen_data_dictionary.py` (`make docs`). Do not edit by hand.",
        "For lineage, open the dbt docs (`make docs`, then `/dbt-docs/` on the API).",
        "",
        "## Bronze: raw sources",
        "",
    ]
    sources = yaml.safe_load((MODELS / "sources.yml").read_text(encoding="utf-8"))
    for src in sources["sources"]:
        for table in src["tables"]:
            lines += [
                f"### `{src['name']}.{table['name']}`",
                "",
                clean(table.get("description")),
                "",
            ]
            if table.get("columns"):
                lines += ["| Column | Description |", "| --- | --- |"]
                lines += [
                    f"| `{c['name']}` | {clean(c.get('description'))} |" for c in table["columns"]
                ]
                lines.append("")
    for folder, title, schema in LAYERS:
        lines += [f"## {title}", ""]
        doc = yaml.safe_load((MODELS / folder / "schema.yml").read_text(encoding="utf-8"))
        for model in doc.get("models", []):
            lines += render_model(model, schema)
    lines += [
        "## Gold: tables written by Python",
        "",
        "### `gold.dq_results`",
        "",
        "One row per data quality test per pipeline run (written by `cmdp.dq.results`).",
        "",
        "| Column | Description |",
        "| --- | --- |",
        "| `run_id` | Pipeline run identifier. |",
        "| `run_at` | When the results were collected (UTC). |",
        "| `test_unique_id` | dbt unique id of the test. |",
        "| `test_name` | Test name. |",
        "| `test_type` | Generic test used (not_null, value_between, ...). |",
        "| `dq_category` | integrity, range, freshness, completeness, anomaly or reconciliation. |",
        "| `table_name` | Model the test checks. |",
        "| `column_name` | Column the test checks, if any. |",
        "| `severity` | error or warn. |",
        "| `status` | pass, warn, fail or error. |",
        "| `failed_rows` | Number of rows that failed. |",
        "| `execution_time_s` | Test run time in seconds. |",
        "| `message` | dbt message. |",
        "",
        "### `gold.pipeline_runs`",
        "",
        "One row per pipeline run: mode, as-of date, timings per step, rows extracted and",
        "data quality counts (written by `cmdp.pipeline`).",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
