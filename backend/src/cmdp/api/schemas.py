"""Pydantic response models for the API."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class SeriesMeta(BaseModel):
    """Catalog entry for one series."""

    series_key: str
    source_id: str
    source: str
    category: str
    series_name: str
    unit: str
    frequency: str
    description: str
    first_date: date | None
    last_date: date | None
    observation_count: int
    freshness_status: str | None = None
    source_url: str


class Point(BaseModel):
    """One dated value."""

    date: date
    value: float


class SeriesObservations(BaseModel):
    """Observations of one series between two dates."""

    series: SeriesMeta
    start: date | None
    end: date | None
    count: int
    observations: list[Point]


class CurvePoint(BaseModel):
    """One tenor on the yield curve."""

    tenor: str
    years: float
    yield_pct: float | None


class Curve(BaseModel):
    """The yield curve on one date."""

    date: date
    points: list[CurvePoint]
    spread_2s10s_bps: float | None
    is_inverted: bool


class SpreadPoint(BaseModel):
    """2s10s spread on one date."""

    date: date
    spread_2s10s_bps: float
    is_inverted: bool


class YieldCurveResponse(BaseModel):
    """Curve on the requested date, one year earlier, and the spread history."""

    requested_date: date | None
    available_from: date
    available_to: date
    current: Curve
    year_ago: Curve | None
    spread_history: list[SpreadPoint]


class FxPoint(BaseModel):
    """One day of an exchange rate."""

    date: date
    rate: float
    daily_return_pct: float | None
    vol_30d_pct: float | None


class FxResponse(BaseModel):
    """Exchange rate history with returns and volatility."""

    pair: str
    unit: str
    latest: FxPoint
    observations: list[FxPoint]


class PolicyEvent(BaseModel):
    """One change in the policy rate."""

    effective_date: date
    old_rate: float
    new_rate: float
    change_bps: int
    direction: str


class PolicyMonth(BaseModel):
    """Policy rate, inflation and the real policy rate for one month."""

    month: date
    policy_rate_avg: float
    policy_rate_eom: float
    cpi_yoy_pct: float
    real_policy_rate: float


class PolicyRateResponse(BaseModel):
    """Rate decisions and the monthly real policy rate."""

    current_rate: float
    events: list[PolicyEvent]
    monthly: list[PolicyMonth]
    target_band: tuple[float, float] = (1.0, 3.0)
    inflation_target: float = 2.0


class DqTest(BaseModel):
    """Latest outcome of one data quality test."""

    test_name: str
    dq_category: str
    table_name: str | None
    column_name: str | None
    severity: str
    status: str
    failed_rows: int


class Freshness(BaseModel):
    """Freshness of one series."""

    series_key: str
    category: str
    latest_obs_date: date | None
    business_days_since: int
    threshold_business_days: int
    status: str


class Completeness(BaseModel):
    """Completeness of one series."""

    series_key: str
    expected_periods: int
    missing_periods: int
    completeness_pct: float


class Anomaly(BaseModel):
    """One flagged day-over-day move."""

    series_key: str
    obs_date: date
    value: float
    change: float
    z_score: float


class DqSummary(BaseModel):
    """Scorecard of the latest data quality run."""

    run_id: str
    run_at: datetime
    total: int
    passed: int
    warned: int
    failed: int
    errored: int
    pass_rate_pct: float
    by_category: dict[str, dict[str, int]]
    tests: list[DqTest]
    freshness: list[Freshness]
    completeness: list[Completeness]
    anomalies: list[Anomaly]
    anomaly_count: int


class Kpi(BaseModel):
    """One headline number with a sparkline."""

    key: str
    label: str
    value: float
    unit: str
    as_of: date
    change: float | None
    change_label: str
    badge: str | None = None
    sparkline: list[Point]


class OverviewResponse(BaseModel):
    """Headline KPIs for the overview page."""

    kpis: list[Kpi]
    last_refreshed: datetime | None


class HealthResponse(BaseModel):
    """Service status and the last pipeline run."""

    status: str
    warehouse: str
    last_run_id: str | None = None
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    last_run_duration_s: float | None = None
    as_of: date | None = None
    total_observations: int | None = None
