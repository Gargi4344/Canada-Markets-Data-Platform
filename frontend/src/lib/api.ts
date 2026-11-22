"use client";

import { useQuery } from "@tanstack/react-query";

import type {
  DqSummary,
  FxResponse,
  HealthResponse,
  OverviewResponse,
  PolicyRateResponse,
  SeriesMeta,
  SeriesObservations,
  YieldCurveResponse,
} from "@/lib/types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Error raised for non-2xx API responses; keeps the server's `detail` message. */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

/** GET a JSON endpoint of the FastAPI service. */
export async function getJson<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`);
  } catch {
    throw new ApiError(0, `Cannot reach the API at ${API_URL}. Is \`make api\` running?`);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* body was not JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const useHealth = () =>
  useQuery({ queryKey: ["health"], queryFn: () => getJson<HealthResponse>("/api/health") });

export const useOverview = () =>
  useQuery({ queryKey: ["overview"], queryFn: () => getJson<OverviewResponse>("/api/overview") });

export const useSeries = () =>
  useQuery({ queryKey: ["series"], queryFn: () => getJson<SeriesMeta[]>("/api/series") });

export const useSeriesObservations = (key: string, start?: string) =>
  useQuery({
    queryKey: ["series-obs", key, start],
    queryFn: () =>
      getJson<SeriesObservations>(`/api/series/${encodeURIComponent(key)}${start ? `?start=${start}` : ""}`),
  });

export const useYieldCurve = (date: string | null) =>
  useQuery({
    queryKey: ["yield-curve", date],
    queryFn: () =>
      getJson<YieldCurveResponse>(`/api/yield-curve${date ? `?date=${encodeURIComponent(date)}` : ""}`),
    placeholderData: (prev) => prev,
  });

export const useFxPairs = () =>
  useQuery({ queryKey: ["fx-pairs"], queryFn: () => getJson<string[]>("/api/fx") });

export const useFx = (pair: string) =>
  useQuery({
    queryKey: ["fx", pair],
    queryFn: () => getJson<FxResponse>(`/api/fx/${encodeURIComponent(pair)}`),
    placeholderData: (prev) => prev,
  });

export const usePolicyRate = () =>
  useQuery({ queryKey: ["policy-rate"], queryFn: () => getJson<PolicyRateResponse>("/api/policy-rate") });

export const useDqSummary = () =>
  useQuery({
    queryKey: ["dq-summary"],
    queryFn: () => getJson<DqSummary>("/api/dq/summary?anomalies_limit=100"),
  });
