"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { C, ChartCard, TooltipBox, axisProps } from "@/components/charts";
import { KpiCard } from "@/components/kpi-card";
import { PageHeader } from "@/components/page-header";
import { ChartSkeleton, EmptyState, ErrorState, KpiSkeleton } from "@/components/states";
import { Button } from "@/components/ui/button";
import { useFx, useFxPairs } from "@/lib/api";
import { fmt, fmtDate, fmtMonth } from "@/lib/utils";

const RANGES = [
  { key: "1Y", years: 1 },
  { key: "3Y", years: 3 },
  { key: "5Y", years: 5 },
  { key: "All", years: 0 },
] as const;

const label = (pair: string) => `${pair.slice(0, 3)}/${pair.slice(3)}`;

export default function FxPage() {
  const pairs = useFxPairs();
  const [pair, setPair] = useState("USDCAD");
  const [range, setRange] = useState<(typeof RANGES)[number]["key"]>("3Y");
  const fx = useFx(pair);

  const data = useMemo(() => {
    const obs = fx.data?.observations ?? [];
    const years = RANGES.find((r) => r.key === range)!.years;
    if (!years || !obs.length) return obs;
    const last = new Date(`${obs[obs.length - 1].date}T00:00:00`);
    last.setFullYear(last.getFullYear() - years);
    const cutoff = last.toISOString().slice(0, 10);
    return obs.filter((o) => o.date >= cutoff);
  }, [fx.data, range]);

  const first = data[0];
  const latest = fx.data?.latest;
  const digits = pair === "JPYCAD" ? 5 : 4;

  return (
    <>
      <PageHeader
        title="FX"
        description="Bank of Canada daily exchange rates in Canadian dollars per unit of foreign currency, with daily returns and 30-day volatility."
        actions={
          <div className="flex flex-wrap gap-1" role="group" aria-label="Currency pair">
            {(pairs.data ?? ["USDCAD"]).map((p) => (
              <Button key={p} size="sm" variant={p === pair ? "default" : "outline"} onClick={() => setPair(p)} aria-pressed={p === pair}>
                {label(p)}
              </Button>
            ))}
          </div>
        }
      />
      {fx.isLoading && !fx.data && <KpiSkeleton />}
      {fx.isError && <ErrorState error={fx.error} onRetry={() => fx.refetch()} />}
      {fx.data && latest && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard label={`${label(pair)} rate`} value={latest.rate} unit={fx.data.unit} digits={digits} asOf={latest.date} />
            <KpiCard label="Daily return" value={latest.daily_return_pct} unit="%" asOf={latest.date} />
            <KpiCard label="30-day volatility (annualised)" value={latest.vol_30d_pct} unit="%" asOf={latest.date} />
            <KpiCard
              label={`Change over ${range === "All" ? "full history" : range}`}
              value={first ? (latest.rate / first.rate - 1) * 100 : null}
              unit="%"
              asOf={first?.date ? `${first.date}` : null}
            />
          </div>

          <div className="mt-4 flex gap-1" role="group" aria-label="Time range">
            {RANGES.map((r) => (
              <Button key={r.key} size="sm" variant={r.key === range ? "default" : "ghost"} onClick={() => setRange(r.key)} aria-pressed={r.key === range}>
                {r.key}
              </Button>
            ))}
          </div>

          {data.length === 0 ? (
            <EmptyState title="No observations in this range" />
          ) : (
            <div className="mt-4 grid gap-6 xl:grid-cols-2">
              <ChartCard title={`${label(pair)} exchange rate`} description={`${fx.data.unit}, business days from ${fmtDate(data[0].date)}.`}>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
                      <CartesianGrid stroke={C.grid} vertical={false} />
                      <XAxis dataKey="date" {...axisProps} tickFormatter={fmtMonth} minTickGap={56} />
                      <YAxis {...axisProps} domain={["auto", "auto"]} tickFormatter={(v) => fmt(v, digits - 1)} width={64} />
                      <Tooltip
                        cursor={{ stroke: C.axis, strokeDasharray: "3 3" }}
                        content={({ active, payload }) =>
                          active && payload?.length ? (
                            <TooltipBox
                              title={fmtDate(String(payload[0].payload.date))}
                              rows={[
                                { label: "Rate", value: fmt(payload[0].payload.rate, digits), color: C.s1 },
                                { label: "Daily return", value: `${fmt(payload[0].payload.daily_return_pct)}%` },
                              ]}
                            />
                          ) : null
                        }
                      />
                      <Line type="monotone" dataKey="rate" stroke={C.s1} strokeWidth={2} dot={false} isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>

              <ChartCard
                title="30-day rolling volatility"
                description="Standard deviation of the last 30 daily log returns, annualised (×√252), percent."
              >
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
                      <CartesianGrid stroke={C.grid} vertical={false} />
                      <XAxis dataKey="date" {...axisProps} tickFormatter={fmtMonth} minTickGap={56} />
                      <YAxis {...axisProps} unit="%" domain={[0, "auto"]} />
                      <Tooltip
                        cursor={{ stroke: C.axis, strokeDasharray: "3 3" }}
                        content={({ active, payload }) =>
                          active && payload?.length ? (
                            <TooltipBox
                              title={fmtDate(String(payload[0].payload.date))}
                              rows={[{ label: "30-day volatility", value: `${fmt(payload[0].payload.vol_30d_pct)}%`, color: C.s3 }]}
                            />
                          ) : null
                        }
                      />
                      <Line type="monotone" dataKey="vol_30d_pct" stroke={C.s3} strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>
            </div>
          )}
        </>
      )}
      {fx.isLoading && !fx.data && <div className="mt-6"><ChartSkeleton /></div>}
    </>
  );
}
