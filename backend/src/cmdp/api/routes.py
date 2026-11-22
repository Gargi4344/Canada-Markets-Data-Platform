"""API routes. Every query reads the gold (and DQ) tables of the published warehouse."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from cmdp.api.db import Db, one, rows
from cmdp.api.schemas import (
    Anomaly,
    Completeness,
    Curve,
    CurvePoint,
    DqSummary,
    DqTest,
    Freshness,
    FxPoint,
    FxResponse,
    HealthResponse,
    Kpi,
    OverviewResponse,
    Point,
    PolicyEvent,
    PolicyMonth,
    PolicyRateResponse,
    SeriesMeta,
    SeriesObservations,
    SpreadPoint,
    YieldCurveResponse,
)

router = APIRouter(prefix="/api")

TENORS = [("2Y", 2.0, "yield_2y"), ("5Y", 5.0, "yield_5y"), ("10Y", 10.0, "yield_10y")]
TENORS.append(("Long", 30.0, "yield_long"))

SERIES_SQL = """
select s.series_key, s.source_id, s.source, s.category, s.series_name, s.unit, s.frequency,
       s.description, s.first_date, s.last_date, s.observation_count,
       f.status as freshness_status
from gold.dim_series s
left join gold.dq_freshness f using (series_key)
"""


def source_url(source: str, source_id: str) -> str:
    """Human-readable page for a series at its source."""
    if source == "boc_valet":
        return f"https://www.bankofcanada.ca/valet/series/{source_id}"
    return "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401"


def to_meta(r: dict) -> SeriesMeta:
    """Build a ``SeriesMeta`` from a dim_series row."""
    return SeriesMeta(**r, source_url=source_url(r["source"], r["source_id"]))


@router.get("/health", response_model=HealthResponse, tags=["meta"])
def health(db: Db) -> HealthResponse:
    """Service status and the last pipeline run time."""
    run = one(
        db,
        "select run_id, finished_at, status, duration_s, as_of from gold.pipeline_runs"
        " order by finished_at desc limit 1",
    )
    total = one(db, "select count(*) as n from gold.fct_observation")
    return HealthResponse(
        status="ok",
        warehouse="markets.duckdb",
        last_run_id=run and run["run_id"],
        last_run_at=run and run["finished_at"],
        last_run_status=run and run["status"],
        last_run_duration_s=run and run["duration_s"],
        as_of=run and run["as_of"],
        total_observations=total and total["n"],
    )


@router.get("/series", response_model=list[SeriesMeta], tags=["series"])
def list_series(db: Db) -> list[SeriesMeta]:
    """Catalog of all series with metadata and freshness status."""
    return [to_meta(r) for r in rows(db, SERIES_SQL + " order by s.category, s.series_key")]


@router.get("/series/{key}", response_model=SeriesObservations, tags=["series"])
def series_observations(
    key: str,
    db: Db,
    start: Annotated[date | None, Query(description="First date (inclusive)")] = None,
    end: Annotated[date | None, Query(description="Last date (inclusive)")] = None,
) -> SeriesObservations:
    """Observations for one series, optionally between two dates."""
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    meta = one(db, SERIES_SQL + " where s.series_key = ?", [key.upper()])
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Unknown series '{key}'")
    obs = rows(
        db,
        "select obs_date as date, value from gold.fct_observation where series_key = ?"
        " and (? is null or obs_date >= ?) and (? is null or obs_date <= ?) order by obs_date",
        [meta["series_key"], start, start, end, end],
    )
    return SeriesObservations(
        series=to_meta(meta),
        start=start,
        end=end,
        count=len(obs),
        observations=[Point(**o) for o in obs],
    )


def _curve_on_or_before(db: Db, d: date) -> Curve | None:
    """The yield curve on ``d`` or the closest earlier business day with data."""
    r = one(
        db,
        "select * from gold.mart_yield_curve where obs_date <= ? order by obs_date desc limit 1",
        [d],
    )
    if r is None:
        return None
    return Curve(
        date=r["obs_date"],
        points=[CurvePoint(tenor=t, years=y, yield_pct=r[c]) for t, y, c in TENORS],
        spread_2s10s_bps=r["spread_2s10s_bps"],
        is_inverted=r["is_inverted"],
    )


@router.get("/yield-curve", response_model=YieldCurveResponse, tags=["markets"])
def yield_curve(
    db: Db,
    date_: Annotated[date | None, Query(alias="date", description="Curve date")] = None,
) -> YieldCurveResponse:
    """Curve for a date and the same date one year earlier, plus the 2s10s spread history."""
    bounds = one(db, "select min(obs_date) lo, max(obs_date) hi from gold.mart_yield_curve")
    if not bounds or bounds["hi"] is None:
        raise HTTPException(status_code=404, detail="No yield curve data")
    target = min(date_ or bounds["hi"], bounds["hi"])
    current = _curve_on_or_before(db, target)
    if current is None:
        raise HTTPException(status_code=404, detail=f"No curve on or before {target}")
    try:
        one_year = current.date.replace(year=current.date.year - 1)
    except ValueError:  # 29 February
        one_year = current.date - timedelta(days=365)
    history = rows(
        db,
        "select obs_date as date, spread_2s10s_bps, is_inverted from gold.mart_yield_curve"
        " order by obs_date",
    )
    return YieldCurveResponse(
        requested_date=date_,
        available_from=bounds["lo"],
        available_to=bounds["hi"],
        current=current,
        year_ago=_curve_on_or_before(db, one_year),
        spread_history=[SpreadPoint(**h) for h in history],
    )


@router.get("/fx", response_model=list[str], tags=["markets"])
def fx_pairs(db: Db) -> list[str]:
    """Available currency pairs."""
    return [r["pair"] for r in rows(db, "select distinct pair from gold.mart_fx_daily order by 1")]


@router.get("/fx/{pair}", response_model=FxResponse, tags=["markets"])
def fx(
    pair: str,
    db: Db,
    start: Annotated[date | None, Query()] = None,
    end: Annotated[date | None, Query()] = None,
) -> FxResponse:
    """Rates, daily returns and 30-day volatility for one pair (for example USDCAD)."""
    pair = pair.upper().replace("/", "").replace("-", "")
    obs = rows(
        db,
        "select obs_date as date, rate, daily_return_pct, vol_30d_pct from gold.mart_fx_daily"
        " where pair = ? and (? is null or obs_date >= ?) and (? is null or obs_date <= ?)"
        " order by obs_date",
        [pair, start, start, end, end],
    )
    if not obs:
        raise HTTPException(status_code=404, detail=f"No data for pair '{pair}'")
    unit = one(db, "select unit from gold.dim_series where series_key = ?", [f"FX_{pair}"])
    points = [FxPoint(**o) for o in obs]
    return FxResponse(
        pair=pair, unit=unit["unit"] if unit else "", latest=points[-1], observations=points
    )


@router.get("/policy-rate", response_model=PolicyRateResponse, tags=["policy"])
def policy_rate(db: Db) -> PolicyRateResponse:
    """Rate decisions and the monthly real policy rate (policy rate minus CPI inflation)."""
    current = one(
        db,
        "select value from gold.fct_observation where series_key = 'POLICY_RATE'"
        " order by obs_date desc limit 1",
    )
    if current is None:
        raise HTTPException(status_code=404, detail="No policy rate data")
    events = rows(
        db,
        "select effective_date, old_rate, new_rate, change_bps, direction"
        " from gold.mart_policy_rate_events order by effective_date",
    )
    monthly = rows(
        db,
        "select month, policy_rate_avg, policy_rate_eom, cpi_yoy_pct, real_policy_rate"
        " from gold.mart_real_policy_rate order by month",
    )
    return PolicyRateResponse(
        current_rate=current["value"],
        events=[PolicyEvent(**e) for e in events],
        monthly=[PolicyMonth(**m) for m in monthly],
    )


@router.get("/dq/summary", response_model=DqSummary, tags=["data quality"])
def dq_summary(db: Db, anomalies_limit: Annotated[int, Query(ge=1, le=500)] = 50) -> DqSummary:
    """Pass/fail counts, freshness per series and the latest anomalies."""
    run = one(
        db,
        "select run_id, max(run_at) as run_at from gold.dq_results group by run_id"
        " order by run_at desc limit 1",
    )
    if run is None:
        raise HTTPException(status_code=404, detail="No data quality results yet")
    tests = rows(
        db,
        "select test_name, dq_category, table_name, column_name, severity, status, failed_rows"
        " from gold.dq_results where run_id = ? order by dq_category, test_name",
        [run["run_id"]],
    )
    by_cat: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for t in tests:
        by_cat[t["dq_category"]][t["status"]] += 1
        by_cat[t["dq_category"]]["total"] += 1
    count = {s: sum(t["status"] == s for t in tests) for s in ("pass", "warn", "fail", "error")}
    freshness = rows(
        db,
        "select series_key, category, latest_obs_date, business_days_since,"
        " threshold_business_days, status from gold.dq_freshness order by category, series_key",
    )
    completeness = rows(
        db,
        "select series_key, expected_periods, missing_periods, completeness_pct"
        " from gold.dq_completeness order by series_key",
    )
    anomalies = rows(
        db,
        "select series_key, obs_date, value, change, z_score from gold.dq_anomalies"
        " order by obs_date desc, abs(z_score) desc limit ?",
        [anomalies_limit],
    )
    n_anom = one(db, "select count(*) as n from gold.dq_anomalies")
    return DqSummary(
        run_id=run["run_id"],
        run_at=run["run_at"],
        total=len(tests),
        passed=count["pass"],
        warned=count["warn"],
        failed=count["fail"],
        errored=count["error"],
        pass_rate_pct=round(100.0 * count["pass"] / len(tests), 1) if tests else 0.0,
        by_category={k: dict(v) for k, v in by_cat.items()},
        tests=[DqTest(**t) for t in tests],
        freshness=[Freshness(**f) for f in freshness],
        completeness=[Completeness(**c) for c in completeness],
        anomalies=[Anomaly(**a) for a in anomalies],
        anomaly_count=n_anom["n"] if n_anom else 0,
    )


def _spark(db: Db, sql: str, params: list, n: int) -> list[Point]:
    """Return the last ``n`` points of a (date, value) query, oldest first."""
    pts = rows(db, f"select * from ({sql}) order by date desc limit {int(n)}", params)
    return [Point(**p) for p in reversed(pts)]


@router.get("/overview", response_model=OverviewResponse, tags=["meta"])
def overview(db: Db) -> OverviewResponse:
    """Headline KPIs with sparklines for the overview page."""
    obs = "select obs_date as date, value from gold.fct_observation where series_key = ?"
    kpis: list[Kpi] = []

    policy = _spark(db, obs, ["POLICY_RATE"], 260)
    last_event = one(
        db,
        "select change_bps, effective_date from gold.mart_policy_rate_events"
        " order by effective_date desc limit 1",
    )
    if policy:
        kpis.append(
            Kpi(
                key="policy_rate",
                label="Policy rate",
                value=policy[-1].value,
                unit="%",
                as_of=policy[-1].date,
                change=last_event["change_bps"] if last_event else None,
                change_label=(
                    f"bps at last change ({last_event['effective_date']})" if last_event else ""
                ),
                sparkline=policy,
            )
        )

    ten = _spark(db, obs, ["GOC_10Y"], 120)
    if len(ten) >= 2:
        kpis.append(
            Kpi(
                key="goc_10y",
                label="10-year GoC yield",
                value=ten[-1].value,
                unit="%",
                as_of=ten[-1].date,
                change=round((ten[-1].value - ten[-2].value) * 100, 1),
                change_label="bps vs previous day",
                sparkline=ten,
            )
        )

    spread = _spark(
        db,
        "select obs_date as date, spread_2s10s_bps as value from gold.mart_yield_curve",
        [],
        120,
    )
    if len(spread) >= 2:
        kpis.append(
            Kpi(
                key="spread_2s10s",
                label="2s10s spread",
                value=spread[-1].value,
                unit="bps",
                as_of=spread[-1].date,
                change=round(spread[-1].value - spread[-2].value, 1),
                change_label="bps vs previous day",
                badge="inverted" if spread[-1].value < 0 else "normal",
                sparkline=spread,
            )
        )

    usd = _spark(db, obs, ["FX_USDCAD"], 120)
    if len(usd) >= 2:
        kpis.append(
            Kpi(
                key="usdcad",
                label="USD/CAD",
                value=usd[-1].value,
                unit="CAD",
                as_of=usd[-1].date,
                change=round((usd[-1].value / usd[-2].value - 1) * 100, 2),
                change_label="% vs previous day",
                sparkline=usd,
            )
        )

    cpi = _spark(
        db,
        "select month as date, yoy_pct as value from gold.mart_cpi_monthly"
        " where series_key = 'CPI_ALL' and yoy_pct is not null",
        [],
        36,
    )
    if len(cpi) >= 2:
        kpis.append(
            Kpi(
                key="cpi_yoy",
                label="CPI inflation (y/y)",
                value=cpi[-1].value,
                unit="%",
                as_of=cpi[-1].date,
                change=round(cpi[-1].value - cpi[-2].value, 2),
                change_label="pp vs previous month",
                sparkline=cpi,
            )
        )

    run = one(db, "select max(finished_at) as t from gold.pipeline_runs")
    return OverviewResponse(kpis=kpis, last_refreshed=run["t"] if run else None)
