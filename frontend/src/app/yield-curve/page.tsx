"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { C, ChartCard, TooltipBox, axisProps } from "@/components/charts";
import { KpiCard } from "@/components/kpi-card";
import { PageHeader } from "@/components/page-header";
import { ChartSkeleton, ErrorState, KpiSkeleton } from "@/components/states";
import { useYieldCurve } from "@/lib/api";
import type { SpreadPoint } from "@/lib/types";
import { fmt, fmtDate, fmtMonth } from "@/lib/utils";

/** Contiguous date ranges during which the curve was inverted. */
function inversionRanges(history: SpreadPoint[]): { from: string; to: string }[] {
  const out: { from: string; to: string }[] = [];
  let start: string | null = null;
  history.forEach((p, i) => {
    if (p.is_inverted && start === null) start = p.date;
    const endsHere = start !== null && (!p.is_inverted || i === history.length - 1);
    if (endsHere) {
      out.push({ from: start!, to: p.is_inverted ? p.date : history[i - 1].date });
      start = null;
    }
  });
  return out;
}

export default function YieldCurvePage() {
  const [committed, setCommitted] = useState<string | null>(null);
  const [index, setIndex] = useState<number | null>(null);
  const curve = useYieldCurve(committed);

  const dates = useMemo(() => curve.data?.spread_history.map((p) => p.date) ?? [], [curve.data]);
  const ranges = useMemo(() => inversionRanges(curve.data?.spread_history ?? []), [curve.data]);
  const sliderIndex = index ?? Math.max(dates.length - 1, 0);

  // Debounce the slider so dragging does not fire a request per pixel.
  useEffect(() => {
    if (index === null || !dates[index]) return;
    const t = setTimeout(() => setCommitted(dates[index]), 250);
    return () => clearTimeout(t);
  }, [index, dates]);

  const d = curve.data;
  const chartData =
    d?.current.points.map((p, i) => ({
      tenor: p.tenor,
      current: p.yield_pct,
      yearAgo: d.year_ago?.points[i]?.yield_pct ?? null,
    })) ?? [];
  const y = (t: string) => d?.current.points.find((p) => p.tenor === t)?.yield_pct ?? null;
  const yAgo = (t: string) => d?.year_ago?.points.find((p) => p.tenor === t)?.yield_pct ?? null;

  return (
    <>
      <PageHeader
        title="Yield Curve"
        description="Government of Canada benchmark yields for a chosen date against the same date one year earlier, and the 2s10s spread over time."
      />
      {curve.isLoading && !d && <KpiSkeleton />}
      {curve.isError && !d && <ErrorState error={curve.error} onRetry={() => curve.refetch()} />}
      {d && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard label="2-year yield" value={y("2Y")} unit="%" change={y("2Y") !== null && yAgo("2Y") !== null ? (y("2Y")! - yAgo("2Y")!) * 100 : null} changeDigits={0} changeLabel="bps vs 1 year earlier" asOf={d.current.date} />
            <KpiCard label="10-year yield" value={y("10Y")} unit="%" change={y("10Y") !== null && yAgo("10Y") !== null ? (y("10Y")! - yAgo("10Y")!) * 100 : null} changeDigits={0} changeLabel="bps vs 1 year earlier" asOf={d.current.date} />
            <KpiCard label="Long-term yield" value={y("Long")} unit="%" change={y("Long") !== null && yAgo("Long") !== null ? (y("Long")! - yAgo("Long")!) * 100 : null} changeDigits={0} changeLabel="bps vs 1 year earlier" asOf={d.current.date} />
            <KpiCard
              label="2s10s spread"
              value={d.current.spread_2s10s_bps}
              unit="bps"
              digits={0}
              asOf={d.current.date}
              badge={d.current.is_inverted ? { label: "Inverted", variant: "destructive" } : { label: "Normal", variant: "success" }}
            />
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-5">
            <ChartCard
              className="xl:col-span-2"
              title={`Curve on ${fmtDate(d.current.date)}`}
              description={d.year_ago ? `Compared with ${fmtDate(d.year_ago.date)}. Yields in percent by term.` : "Yields in percent by term."}
              legend={[
                { label: fmtDate(d.current.date), color: C.s1 },
                ...(d.year_ago ? [{ label: `${fmtDate(d.year_ago.date)} (1 year earlier)`, color: C.s2, dashed: true }] : []),
              ]}
            >
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
                    <CartesianGrid stroke={C.grid} vertical={false} />
                    <XAxis dataKey="tenor" {...axisProps} />
                    <YAxis {...axisProps} unit="%" domain={["auto", "auto"]} />
                    <Tooltip
                      cursor={{ stroke: C.axis, strokeDasharray: "3 3" }}
                      content={({ active, payload }) =>
                        active && payload?.length ? (
                          <TooltipBox
                            title={`${payload[0].payload.tenor} term`}
                            rows={[
                              { label: fmtDate(d.current.date), value: `${fmt(payload[0].payload.current)}%`, color: C.s1 },
                              ...(d.year_ago ? [{ label: fmtDate(d.year_ago.date), value: `${fmt(payload[0].payload.yearAgo)}%`, color: C.s2 }] : []),
                            ]}
                          />
                        ) : null
                      }
                    />
                    <Line dataKey="current" stroke={C.s1} strokeWidth={2} dot={{ r: 4, fill: C.s1, strokeWidth: 0 }} isAnimationActive={false} />
                    {d.year_ago && (
                      <Line dataKey="yearAgo" stroke={C.s2} strokeWidth={2} strokeDasharray="5 4" dot={{ r: 4, fill: C.s2, strokeWidth: 0 }} isAnimationActive={false} />
                    )}
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-4">
                <label htmlFor="curve-date" className="mb-1 flex justify-between text-xs text-muted-foreground">
                  <span>Choose a date</span>
                  <span className="font-medium text-foreground tabular">{fmtDate(dates[sliderIndex])}</span>
                </label>
                <input
                  id="curve-date"
                  type="range"
                  min={0}
                  max={Math.max(dates.length - 1, 0)}
                  value={sliderIndex}
                  onChange={(e) => setIndex(Number(e.target.value))}
                  className="w-full accent-[hsl(var(--accent))]"
                  aria-valuetext={fmtDate(dates[sliderIndex])}
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>{fmtDate(d.available_from)}</span>
                  <span>{fmtDate(d.available_to)}</span>
                </div>
              </div>
            </ChartCard>

            <ChartCard
              className="xl:col-span-3"
              title="2s10s spread over time"
              description="10-year minus 2-year yield, basis points. Shaded periods are inversions (spread below zero)."
              legend={[
                { label: "2s10s spread", color: C.s1 },
                { label: "Inverted curve", color: C.alert, swatch: "area" },
              ]}
            >
              <div className="h-[360px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={d.spread_history} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
                    <CartesianGrid stroke={C.grid} vertical={false} />
                    <XAxis dataKey="date" {...axisProps} tickFormatter={fmtMonth} minTickGap={56} />
                    <YAxis {...axisProps} domain={["auto", "auto"]} />
                    {ranges.map((r) => (
                      <ReferenceArea key={r.from} x1={r.from} x2={r.to} fill={C.alert} fillOpacity={1} ifOverflow="extendDomain" />
                    ))}
                    <ReferenceLine y={0} stroke={C.axis} />
                    <ReferenceLine x={d.current.date} stroke={C.axis} strokeDasharray="3 3" />
                    <Tooltip
                      cursor={{ stroke: C.axis, strokeDasharray: "3 3" }}
                      content={({ active, payload }) =>
                        active && payload?.length ? (
                          <TooltipBox
                            title={fmtDate(String(payload[0].payload.date))}
                            rows={[
                              { label: "Spread", value: `${fmt(Number(payload[0].value), 0)} bps`, color: C.s1 },
                              { label: "Curve", value: payload[0].payload.is_inverted ? "Inverted" : "Normal" },
                            ]}
                          />
                        ) : null
                      }
                    />
                    <Line type="monotone" dataKey="spread_2s10s_bps" stroke={C.s1} strokeWidth={2} dot={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <p className="mt-3 text-xs text-muted-foreground">
                {ranges.length} inversion periods since {fmtDate(d.available_from)}.
              </p>
            </ChartCard>
          </div>
        </>
      )}
      {curve.isLoading && !d && <div className="mt-6"><ChartSkeleton /></div>}
    </>
  );
}
