# Canada Markets Data Platform - developer commands.
# Requires: uv (https://docs.astral.sh/uv/), Node.js 20+, GNU make.

BACKEND := backend
FRONTEND := frontend
RUN := cd $(BACKEND) && uv run
API_PORT ?= 8000
WEB_PORT ?= 3000
DAGSTER_PORT ?= 3070

.PHONY: help setup lint format test pipeline pipeline-fixtures incremental api web dev \
        dagster docs results screenshots notebook frontend-check clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

setup: ## Install Python (uv) and Node dependencies and the pre-commit hook
	cd $(BACKEND) && uv sync
	cd $(FRONTEND) && npm ci
	-cd $(BACKEND) && uv run pre-commit install --config ../.pre-commit-config.yaml

lint: ## Ruff lint and format check
	$(RUN) ruff check . && uv run ruff format --check .

format: ## Auto-format Python code
	$(RUN) ruff check --fix . && uv run ruff format .

test: ## Run the pytest suite (offline, uses fixtures)
	$(RUN) pytest

pipeline: ## Load real data (2015 to today): extract -> dbt -> data quality -> publish
	$(RUN) python -m cmdp.pipeline run

incremental: ## Re-run the pipeline; only dates after the last loaded date are fetched
	$(RUN) python -m cmdp.pipeline run

pipeline-fixtures: ## Run the whole pipeline offline on the committed fixtures
	$(RUN) python -m cmdp.pipeline run --fixtures --full-refresh

api: ## Start the FastAPI service on :8000
	$(RUN) uvicorn cmdp.api.main:app --host 0.0.0.0 --port $(API_PORT)

web: ## Start the Next.js dashboard on :3000
	cd $(FRONTEND) && npm run dev -- --port $(WEB_PORT)

dev: pipeline ## Load real data, then start the API and the dashboard together
	@echo "Dashboard: http://localhost:$(WEB_PORT)   API: http://localhost:$(API_PORT)/docs"
	$(MAKE) -j2 api web

dagster: ## Start the Dagster UI (assets, lineage, daily schedule) on :3070
	cd $(BACKEND) && DAGSTER_HOME=$$(pwd)/.dagster_home uv run dagster dev -m cmdp.orchestration.definitions -p $(DAGSTER_PORT)

docs: ## Generate dbt docs and docs/DATA_DICTIONARY.md
	$(RUN) python -m cmdp.pipeline docs
	$(RUN) python ../scripts/gen_data_dictionary.py

notebook: ## Execute notebooks/01_eda.ipynb against the gold warehouse
	$(RUN) jupyter nbconvert --to notebook --execute --inplace ../notebooks/01_eda.ipynb

results: ## Measure everything and regenerate RESULTS.md and the README results/highlights
	$(RUN) python ../scripts/make_results.py

screenshots: ## Capture README screenshots (needs `make api` and `make web` running)
	cd $(FRONTEND) && node ../scripts/capture_screenshots.mjs

frontend-check: ## Lint and build the frontend
	cd $(FRONTEND) && npm run lint && npm run build

clean: ## Delete local data and build artefacts
	rm -rf data $(BACKEND)/dbt/target $(BACKEND)/dbt/logs $(FRONTEND)/.next
