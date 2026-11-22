# Architecture

## Overview

```mermaid
flowchart LR
  subgraph Sources
    V[Bank of Canada Valet API]
    W[Statistics Canada WDS]
  end
  subgraph Bronze["Bronze (data/bronze, Parquet)"]
    BV[boc_valet/&lt;series&gt;/load_date=…]
    BW[statcan_wds/&lt;series&gt;/load_date=…]
    BL[_loads: load log]
    BM[_meta: series catalog, calendar]
  end
  subgraph Silver["Silver (dbt, schema silver)"]
    ST[stg_* typed staging]
    FL[int_observations_flagged]
    CL[int_observations_clean]
    RM[int_observation_removals]
    MP[int_missing_periods]
  end
  subgraph Gold["Gold (dbt, schema gold)"]
    DD[dim_date]
    DS[dim_series]
    FO[fct_observation]
    MK[mart_yield_curve · mart_fx_daily · mart_policy_rate_events · mart_cpi_monthly · mart_real_policy_rate]
    DQM[dq_freshness · dq_completeness · dq_anomalies · dq_reconciliation]
  end
  DQR[(gold.dq_results)]
  PUB[(data/warehouse/markets.duckdb)]
  V --> BV
  W --> BW
  BV & BW & BL & BM --> ST --> FL --> CL & RM
  CL --> MP
  CL --> DS & FO
  BM --> DD
  DD & DS --> FO --> MK
  FO & DS & MP & RM --> DQM
  DQM & MK & FO -->|dbt test| DQR
  Gold --> PUB
  DQR --> PUB
  PUB --> API[FastAPI, read-only] --> UI[Next.js dashboard]
  DAG[Dagster daily_refresh, Mon–Fri 18:00 Toronto] -.orchestrates.-> Bronze & Silver & Gold & DQR & PUB
```

## Runtime flow of one pipeline run

```mermaid
sequenceDiagram
  participant P as cmdp.pipeline (or Dagster)
  participant X as Extractors
  participant D as dbt (subprocess)
  participant B as build.duckdb
  participant M as markets.duckdb
  P->>X: write catalog + calendar to bronze/_meta
  X->>X: for each series, start = last loaded date + 1
  X->>X: GET Valet / WDS (retries on 429, 5xx, timeouts)
  X-->>P: Parquet files + load log rows
  P->>D: dbt run (silver + gold)
  D->>B: tables in silver and gold schemas
  P->>D: dbt test (all data quality controls)
  D-->>P: run_results.json
  P->>B: insert gold.dq_results, gold.pipeline_runs
  P->>M: copy build.duckdb, then atomic rename
```

## Key design decisions

| Decision | Why |
| --- | --- |
| Bronze is raw text in Parquet, partitioned by series and load date | Reproducible: silver can always be rebuilt from bronze; load metadata gives lineage back to the exact URL. |
| Incremental by "last loaded date + 1" | Fast daily runs and polite use of public APIs. |
| DuckDB file per environment, published by copy + rename | The API reads a stable file while the next build runs; no lock contention on Windows or Linux. |
| dbt runs in a subprocess | Releases DuckDB file handles at exit so the build can be published immediately. |
| All models materialised as tables | The published file is self-contained (no views pointing at Parquet paths). |
| Monitoring checks warn, structural checks error | Source gaps and market shocks are findings to show, not reasons to stop serving data; broken keys or impossible values are. |
| Business-day calendar from the `holidays` package plus the Civic Holiday | Calibrated against Valet publishing days so completeness checks flag real gaps only. |
| Fixture transport for httpx | Tests and CI exercise the real extract code path with no network access. |
| Read-only, per-request DuckDB connections in the API | No write path from the internet; connections never pin the file. |

## Schemas

- `silver`: staging and intermediate models (typed, cleaned, flagged).
- `gold`: star schema, marts, data quality models, `dq_results`, `pipeline_runs`.

See [DATA_DICTIONARY.md](DATA_DICTIONARY.md) for every column.
