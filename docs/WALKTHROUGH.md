# Walkthrough: how this project works, file by file

This document explains every folder and file in plain English, why each design choice was
made, and ends with ten interview questions and answers. Measured numbers live in
[RESULTS.md](../RESULTS.md); this file does not repeat them so it never goes out of date.

---

## 1. The big picture in one paragraph

Every weekday evening a pipeline downloads new Bank of Canada market data (policy rate,
CORRA, bond yields, exchange rates) and Statistics Canada CPI. It saves the raw answers as
files (**bronze**), cleans them with SQL in dbt (**silver**), reshapes them into tables that
are easy to analyse (**gold**: a star schema plus "marts"), and then runs automatic checks
on the data (**data quality**; the exact count is in RESULTS.md). The results of every check are saved in a
table. A small web API reads the finished database and a dashboard shows both the data and
how healthy it is.

**Medallion architecture** is the name for that bronze → silver → gold layering: each layer
is more trustworthy than the one before, and you can always rebuild a later layer from an
earlier one.

---

## 2. Root folder

| File | What it is |
| --- | --- |
| `README.md` | The project's front page: pitch, screenshots, architecture, quickstart, results. The Highlights and Results blocks are written by `make results`. |
| `RESULTS.md` | Measured metrics from the last `make results` run (row counts, test counts, pass rate, runtimes). Never edited by hand. |
| `Makefile` | Short commands: `make setup`, `make dev`, `make test`, `make pipeline`, `make dagster`, `make docs`, `make results`… `make help` lists them. |
| `docker-compose.yml` | Starts the API (which loads data on first start) and the dashboard in containers. |
| `.github/workflows/ci.yml` | GitHub Actions: ruff lint and format check, the full pipeline on fixtures, pytest, then `next lint`, `next build` and a TypeScript check. |
| `.pre-commit-config.yaml` | Runs ruff and basic hygiene checks before each commit. |
| `.env.example` | Optional settings (data folder, API URLs, CORS). No keys are needed. |
| `.gitignore`, `.gitattributes` | Keep data, build output and secrets out of git; force LF line endings so the Makefile works everywhere. |
| `LICENSE` | MIT. |

---

## 3. `backend/` – Python package `cmdp`

### 3.1 Configuration

| File | Plain English |
| --- | --- |
| `pyproject.toml` | Dependencies (managed by `uv`), ruff rules and pytest settings. Python is pinned to 3.12. |
| `uv.lock` | Exact versions of every dependency so installs are reproducible. |
| `config/series.yaml` | The catalog: one entry per series with its source ID, unit, frequency, freshness threshold, plausible range and whether the anomaly check applies. The Valet IDs were confirmed by calling `/valet/lists/series/json`; the StatCan vector IDs by calling `getSeriesInfoFromVector`. |
| `src/cmdp/config.py` | One `Settings` object (pydantic-settings) with every path: `data/bronze`, `data/warehouse/build.duckdb` (being built) and `data/warehouse/markets.duckdb` (published). |
| `src/cmdp/series.py` | Reads and validates `series.yaml` with Pydantic so a typo fails loudly. |

### 3.2 Extract (bronze)

| File | Plain English |
| --- | --- |
| `extract/http.py` | Creates the HTTP client and `get_json`, which retries up to five times with exponential back-off on network errors, HTTP 429 and HTTP 5xx, but not on 4xx (a wrong URL will not fix itself). |
| `extract/valet.py` | Calls `/valet/observations/<series>/json?start_date=…` and returns each date and value as text exactly as received. |
| `extract/statcan.py` | Calls the WDS `getDataFromVectorByReferencePeriodRange` endpoint for the CPI vectors. |
| `extract/bronze.py` | Writes one Parquet file per series per run to `data/bronze/<source>/<series>/load_date=YYYY-MM-DD/<load_id>.parquet`, with load id, load time and source URL on every row, plus a load-log row (row count, date range, URL). Also answers "what is the last date I already have?" |
| `extract/run.py` | The incremental logic: for each series, ask for dates after the last loaded date (or months after the last month for CPI). On the first run it starts at 2015-01-01 (2014 for CPI so year-over-year inflation exists for 2015). |
| `extract/fixtures.py` | A fake HTTP transport that answers from the JSON files in `tests/fixtures/`. It honours `start_date`, so incremental behaviour is tested exactly as in production, without the internet. |
| `calendar.py` | Builds the Bank of Canada business-day calendar: weekdays minus Ontario public holidays, federal government holidays (for example the National Day for Truth and Reconciliation) and the August Civic Holiday. This rule was checked against the days on which Valet actually publishes yields and FX. |

**Why keep raw text in bronze?** If a cleaning rule is wrong, you fix the rule and rebuild;
you never have to download history again, and you can prove what the source sent.

### 3.3 Transform and test (dbt project in `backend/dbt/`)

dbt turns SQL `select` statements into tables, in dependency order, and runs tests on them.

| Path | Plain English |
| --- | --- |
| `dbt_project.yml` | Project settings: staging and silver go to schema `silver`, marts and dq models to `gold`, everything as tables. Variables for the as-of date and the anomaly window (250) and threshold (5σ). |
| `profiles.yml` | Tells dbt to use DuckDB at the path the pipeline passes in. |
| `macros/utils.sql` | Small helpers: use schema names as written, the as-of date, the bronze path. |
| `models/sources.yml` | Declares the bronze Parquet folders as dbt sources (and gives Dagster their asset keys so lineage connects). |
| `models/staging/stg_valet__observations.sql`, `stg_statcan__observations.sql` | **Rule 1 – typing**: cast the date, parse the value with `TRY_CAST` so bad text becomes null instead of crashing. |
| `models/staging/stg_meta__series.sql`, `stg_meta__calendar.sql`, `stg_meta__load_log.sql` | Typed copies of the catalog, calendar and load log. |
| `models/silver/int_observations_flagged.sql` | **Rules 2 and 3**: label rows with an empty value (`null_value`) and older copies of the same series and date (`duplicate`). Nothing is dropped yet, so counts can be reconciled. |
| `models/silver/int_observations_clean.sql` | The silver table: only kept rows, **rule 4** units standardised with the catalog multiplier, **rule 5** a business-day flag from the calendar. |
| `models/silver/int_observation_removals.sql` | Every removed row with its reason. |
| `models/silver/int_missing_periods.sql` | Business days (or months) between a series' first and last observation that have no value. |
| `models/marts/dim_date.sql` | One row per day: business-day flag, holiday name, month, quarter, year. |
| `models/marts/dim_series.sql` | One row per series: metadata plus first date, last date and row count. |
| `models/marts/fct_observation.sql` | The fact table: series key, date key, value, load id. Grain = one series on one date. |
| `models/marts/mart_yield_curve.sql` | 2, 5, 10-year and long yields side by side, the 2s10s spread in basis points and an inversion flag. |
| `models/marts/mart_fx_daily.sql` | Each currency pair with daily return and 30-day volatility (standard deviation of daily log returns × √252). |
| `models/marts/mart_policy_rate_events.sql` | Every change in the policy rate: date, old rate, new rate, change in basis points. |
| `models/marts/mart_cpi_monthly.sql` | CPI levels with month-over-month and year-over-year inflation (joined on the date 12 months earlier, so a missing month cannot shift the result). |
| `models/marts/mart_real_policy_rate.sql` | Monthly average policy rate minus CPI year-over-year inflation. |
| `models/dq/dq_freshness.sql` | Business days since each series' latest value (since month end for CPI) and a green/amber/red status. |
| `models/dq/dq_completeness.sql` | Expected vs missing periods per series. |
| `models/dq/dq_anomalies.sql` | Day-over-day moves bigger than 5 standard deviations of the previous 250 moves. |
| `models/dq/dq_reconciliation.sql` | Row counts per series: load log vs bronze, bronze vs silver plus removals, silver vs facts. |
| `models/*/schema.yml` | Descriptions of every model and column and the tests attached to them. `docs/DATA_DICTIONARY.md` is generated from these files. |
| `tests/generic/unique_combination.sql` | Custom test: a set of columns is unique together (for example series + date). |
| `tests/generic/dq_tests.sql` | Custom tests: `value_between`, `values_within_catalog_range`, `freshness_within_threshold`, `no_missing_periods`, `no_anomalies`, `reconciles`. |

**Severity policy.** Freshness, completeness and anomaly checks are `warn`: a late source,
a missing day at the source or a genuine market shock is information to surface, not a
reason to stop serving data. Integrity, range and reconciliation checks are `error`: if
keys break or a 25% bond yield appears, the data is wrong.

### 3.4 Data quality results, pipeline and orchestration

| File | Plain English |
| --- | --- |
| `dbt_runner.py` | Runs dbt as a separate process with the right paths and variables. A separate process guarantees DuckDB lets go of the file when dbt finishes. |
| `dq/results.py` | Reads dbt's `run_results.json` and `manifest.json` and writes one row per test to `gold.dq_results`: test name, control category, table, column, severity, status, failing rows, time. |
| `pipeline.py` | The command-line pipeline: write catalog and calendar → extract → `dbt run` → `dbt test` → save DQ results and a `pipeline_runs` row → publish. `--fixtures` runs offline in `data/fixtures/`; `--full-refresh` starts from scratch. |
| `orchestration/definitions.py` | Dagster version of the same steps as software-defined assets: `bronze/*` (Python), every dbt model (via dagster-dbt, grouped into silver, gold and data_quality), `data_quality/dq_results` and `serving/markets_warehouse`. A `daily_refresh` job runs Monday to Friday at 18:00 Toronto time. |

**Why publish by copying?** dbt writes to `build.duckdb`. When everything has passed, the
file is copied and atomically renamed to `markets.duckdb`. The API therefore always reads a
complete, tested database and is never blocked by a running build.

### 3.5 API (`src/cmdp/api/`)

| File | Plain English |
| --- | --- |
| `main.py` | Creates the FastAPI app, allows the dashboard's origin (CORS, GET only) and serves the generated dbt docs at `/dbt-docs/`. |
| `db.py` | Opens a **read-only** DuckDB connection for each request and closes it afterwards; returns HTTP 503 if the warehouse has not been built. |
| `schemas.py` | Pydantic models for every response, which also produce the OpenAPI docs at `/docs`. |
| `routes.py` | The endpoints: `/api/series`, `/api/series/{key}`, `/api/yield-curve`, `/api/fx`, `/api/fx/{pair}`, `/api/policy-rate`, `/api/dq/summary`, `/api/health` and `/api/overview` (the KPI cards). Queries use parameters, never string concatenation of user input. |
| `Dockerfile`, `.dockerignore` | Container that loads data then serves the API. |

### 3.6 Tests (`backend/tests/`)

| File | What it proves |
| --- | --- |
| `test_extract.py` | Parsing, retries on 503 but not 404, bronze layout, and that a second run only fetches new dates and a third fetches nothing. |
| `test_calendar.py` | Christmas, Family Day, Civic Holiday and Truth and Reconciliation Day are not business days; Easter Monday is. |
| `test_pipeline_fixtures.py` | The whole pipeline on fixtures: tables exist, bronze rows = fact rows + removals, spread and inversion maths, 30-day volatility starts at the 31st rate, real rate = policy − inflation. |
| `test_dq.py` | Result collection, every control category present, and a test that **corrupts the data** (a 25% yield, an empty value, a re-delivered file) and checks that range, completeness and reconciliation controls catch it. |
| `test_dagster.py` | The Dagster asset graph loads, bronze links to silver, and the schedule is correct. |
| `test_api.py` | Every endpoint against the fixture warehouse, including 404, 422 and 503 cases. |
| `fixtures/` | Small real samples (2023–2024 Valet, 2022–2024 CPI) recorded by `scripts/make_fixtures.py`. |

---

## 4. `frontend/` – Next.js dashboard

| Path | Plain English |
| --- | --- |
| `package.json` | Next.js 15, React 19, Tailwind, Radix (behind shadcn/ui components), Recharts, TanStack Query, lucide icons, next-themes, Framer Motion. |
| `src/app/layout.tsx` | Loads the Inter font, the theme and data providers and the app shell. |
| `src/app/globals.css` | Design tokens: off-white `#F8FAFC` background, navy `#0B1F3A`, teal `#0EA5A4` accent, red `#DC2626` for alerts, plus chart colours for light and dark mode (validated for colour-blind readers). |
| `src/config/site.ts` | Project name, navigation and the source and licence text for the "About this data" drawer. |
| `src/components/app-shell.tsx` | Header (name, About drawer, GitHub link, dark-mode toggle) and left sidebar; a slide-out menu on phones. |
| `src/components/about-drawer.tsx` | Sources, licences and last refresh (from `/api/health`). |
| `src/components/kpi-card.tsx`, `charts.tsx` | KPI card with change and sparkline; chart card, legend, tooltip and shared axis styles. |
| `src/components/states.tsx`, `status.tsx` | Loading skeletons, empty and error states; status chips that use colour, icon and text together. |
| `src/components/ui/*` | shadcn/ui-style building blocks (button, card, badge, sheet, table, input, skeleton). |
| `src/lib/api.ts`, `types.ts`, `utils.ts` | Typed API calls wrapped in TanStack Query hooks; number and date formatting. |
| `src/app/page.tsx` | **Overview**: five KPI cards with sparklines, 2- and 10-year yields, data quality summary. |
| `src/app/yield-curve/page.tsx` | **Yield Curve**: curve for a chosen date vs one year earlier, a date slider, and the 2s10s spread with inversions shaded. |
| `src/app/fx/page.tsx` | **FX**: pair selector, time range, rate chart and 30-day volatility chart (two charts, never two y-axes). |
| `src/app/policy/page.tsx` | **Policy & Inflation**: step line of the policy rate vs CPI inflation with the 1–3% band, the real policy rate, and a table of decisions. |
| `src/app/data-quality/page.tsx` | **Data Quality**: pass rate, scorecard by control, freshness chips, completeness, anomalies and the test list. |
| `src/app/catalog/page.tsx` | **Data Catalog**: searchable table of series with links to the source and to dbt docs. |
| `scripts/capture-screenshots.mjs` | Takes the README screenshots with headless Chrome. |
| `Dockerfile` | Builds the standalone Next.js server. |

---

## 5. Other folders

| Path | Plain English |
| --- | --- |
| `notebooks/01_eda.ipynb` | Explores the gold tables: coverage, inversion days per year, FX volatility, policy vs inflation, data quality. Executed against the real warehouse with `make notebook`. |
| `docs/ARCHITECTURE.md` | Diagrams of the layers and of one pipeline run, plus the design decisions table. |
| `docs/DATA_DICTIONARY.md` | Every table and column with its tests, generated from `schema.yml`. |
| `docs/img/` | Dashboard screenshots and the Dagster lineage graph. |
| `scripts/make_results.py` | Runs a full refresh and an incremental run, queries the warehouse, runs pytest, writes `RESULTS.md` and fills the README Highlights and Results. |
| `scripts/templates/highlights.md` | The resume bullets with `{placeholders}` that `make results` fills. |
| `scripts/gen_data_dictionary.py` | Builds the data dictionary. |
| `scripts/make_fixtures.py` | Re-records the small fixture samples from the live APIs. |

---

## 6. Design decisions worth remembering

1. **DuckDB instead of a server database**: a single file, fast analytical SQL, no service to
   run. Right size for tens of thousands of rows; swapping to Postgres or Snowflake changes
   only the dbt profile.
2. **dbt for the SQL layers**: dependency ordering, tests, documentation and lineage for free.
3. **Polars for writing Parquet**: fast and typed with a tiny footprint.
4. **Dagster over cron**: assets show lineage and materialisation history; the dbt graph is
   imported automatically, so the UI shows every model.
5. **Fixtures through a mock transport**: the code under test is the production code.
6. **Strict honesty on metrics**: numbers in the README come from `make results` only.

---

## 7. Ten likely interview questions

**1. Walk me through what happens when the pipeline runs.**
It writes the catalog and calendar, then for each series asks the source only for dates after
the last one stored, and writes the raw response to Parquet with load metadata. dbt builds
silver (typed, de-duplicated, standardised, calendar-flagged) and gold (star schema and marts).
`dbt test` runs every quality control; the results go to `gold.dq_results`. Finally the
database is published by atomic rename so the API switches to the new version in one step.

**2. Why a star schema here?**
Different questions slice the same observations by series and by date. A fact table at the
series-by-date grain with `dim_series` and `dim_date` keeps one source of truth, makes joins
predictable, and lets marts like the yield curve be simple pivots of the fact table.

**3. How do you handle incremental loads, and what are the risks?**
Each series restarts the day after its last stored date. The risk is revisions to past values,
which this approach does not pick up. Silver already keeps the latest copy of a duplicated
date, so the fix is a look-back window plus keeping each vintage – listed under "What I'd do next".

**4. How do you know the data is complete?**
A Bank of Canada business-day calendar defines which days should have data. Completeness
lists every expected business day (or month) without an observation between a series' first
and last date. I calibrated the calendar against Valet publishing days so the check flags
real gaps, not holidays.

**5. Explain your anomaly check. Why warn instead of fail?**
For each daily series I compare the day-over-day change with the standard deviation of the
previous 250 changes and flag moves above 5σ. Rate decisions and market shocks produce real
large moves, so a flag means "look at this", not "this is wrong". The policy rate is excluded
because it is a step series.

**6. What does reconciliation prove?**
That no row is lost silently: load-log rows equal bronze rows, bronze equals silver plus the
documented removals, and silver equals the fact table. A test that injects a re-delivered
file shows the load-log check catches files written outside the extractor.

**7. Why is the API read-only, and how does it avoid locking problems?**
It opens a read-only DuckDB connection per request and closes it, and it reads a published
copy, not the file dbt is writing. There is no write path from the internet, and builds never
block reads.

**8. How is the 2s10s spread computed, and what does inversion mean?**
10-year yield minus 2-year yield, in basis points. When it is negative the curve is inverted:
markets expect lower short-term rates in future, historically a recession signal.

**9. How is FX volatility computed?**
Daily log returns, sample standard deviation over the last 30 business days, annualised by
√252 and shown in percent. It is null until 30 returns exist, which a test checks.

**10. How does CI work without internet access to the sources?**
Small real samples live in `tests/fixtures/`. A mock HTTP transport serves them, honouring
date filters, so the full pipeline (extract → dbt → tests → publish) and the API tests run on
GitHub Actions offline. The frontend job lints, builds and type-checks the dashboard.
