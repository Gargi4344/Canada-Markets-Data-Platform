/** Types that mirror the FastAPI response models (backend/src/cmdp/api/schemas.py). */

export interface Point {
  date: string;
  value: number;
}

export interface SeriesMeta {
  series_key: string;
  source_id: string;
  source: string;
  category: string;
  series_name: string;
  unit: string;
  frequency: string;
  description: string;
  first_date: string | null;
  last_date: string | null;
  observation_count: number;
  freshness_status: string | null;
  source_url: string;
}

export interface SeriesObservations {
  series: SeriesMeta;
  count: number;
  observations: Point[];
}

export interface CurvePoint {
  tenor: string;
  years: number;
  yield_pct: number | null;
}

export interface Curve {
  date: string;
  points: CurvePoint[];
  spread_2s10s_bps: number | null;
  is_inverted: boolean;
}

export interface SpreadPoint {
  date: string;
  spread_2s10s_bps: number;
  is_inverted: boolean;
}

export interface YieldCurveResponse {
  requested_date: string | null;
  available_from: string;
  available_to: string;
  current: Curve;
  year_ago: Curve | null;
  spread_history: SpreadPoint[];
}

export interface FxPoint {
  date: string;
  rate: number;
  daily_return_pct: number | null;
  vol_30d_pct: number | null;
}

export interface FxResponse {
  pair: string;
  unit: string;
  latest: FxPoint;
  observations: FxPoint[];
}

export interface PolicyEvent {
  effective_date: string;
  old_rate: number;
  new_rate: number;
  change_bps: number;
  direction: "hike" | "cut";
}

export interface PolicyMonth {
  month: string;
  policy_rate_avg: number;
  policy_rate_eom: number;
  cpi_yoy_pct: number;
  real_policy_rate: number;
}

export interface PolicyRateResponse {
  current_rate: number;
  events: PolicyEvent[];
  monthly: PolicyMonth[];
  target_band: [number, number];
  inflation_target: number;
}

export interface DqTest {
  test_name: string;
  dq_category: string;
  table_name: string | null;
  column_name: string | null;
  severity: string;
  status: "pass" | "warn" | "fail" | "error";
  failed_rows: number;
}

export interface Freshness {
  series_key: string;
  category: string;
  latest_obs_date: string | null;
  business_days_since: number;
  threshold_business_days: number;
  status: "green" | "amber" | "red";
}

export interface Completeness {
  series_key: string;
  expected_periods: number;
  missing_periods: number;
  completeness_pct: number;
}

export interface Anomaly {
  series_key: string;
  obs_date: string;
  value: number;
  change: number;
  z_score: number;
}

export interface DqSummary {
  run_id: string;
  run_at: string;
  total: number;
  passed: number;
  warned: number;
  failed: number;
  errored: number;
  pass_rate_pct: number;
  by_category: Record<string, Record<string, number>>;
  tests: DqTest[];
  freshness: Freshness[];
  completeness: Completeness[];
  anomalies: Anomaly[];
  anomaly_count: number;
}

export interface Kpi {
  key: string;
  label: string;
  value: number;
  unit: string;
  as_of: string;
  change: number | null;
  change_label: string;
  badge: string | null;
  sparkline: Point[];
}

export interface OverviewResponse {
  kpis: Kpi[];
  last_refreshed: string | null;
}

export interface HealthResponse {
  status: string;
  warehouse: string;
  last_run_id: string | null;
  last_run_at: string | null;
  last_run_status: string | null;
  last_run_duration_s: number | null;
  as_of: string | null;
  total_observations: number | null;
}
