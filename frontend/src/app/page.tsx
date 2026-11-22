"use client";

import Link from "next/link";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { C, ChartCard, TooltipBox, axisProps } from "@/components/charts";
import { KpiCard } from "@/components/kpi-card";
import { PageHeader } from "@/components/page-header";
import { ChartSkeleton, EmptyState, ErrorState, KpiSkeleton } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useDqSummary, useOverview, useSeriesObservations } from "@/lib/api";
import type { Kpi } from "@/lib/types";
import { fmt, fmtDate, fmtDateTime, fmtMonth } from "@/lib/utils";

const DIGITS: Record<string, number> = { spread_2s10s: 0, usdcad: 4, cpi_yoy: 1 };
const CHANGE_DIGITS: Record<string, number> = { policy_rate: 0, goc_10y: 0, spread_2s10s: 0, usdcad: 2, cpi_yoy: 2 };

function threeYearsAgo(): string {
  const d = new Date();
  d.setFullYear(d.getFullYear() - 3);
  return d.toISOString().slice(0, 10);
}

function badgeFor(k: Kpi) {
  if (k.badge === "inverted") return { label: "Inverted", variant: "destructive" as const };
  if (k.badge === "normal") return { label: "Normal", variant: "success" as const };
  return null;
}

function YieldsChart() {
  const start = threeYearsAgo();
  const two = useSeriesObservations("GOC_2Y", start);
  const ten = useSeriesObservations("GOC_10Y", start);
  if (two.isLoading || ten.isLoading) return <ChartSkeleton />;
  if (two.isError || ten.isError) return <ErrorState error={two.error ?? ten.error} onRetry={() => { two.refetch(); ten.refetch(); }} />;
  const byDate = new Map<string, { date: string; y2?: number; y10?: number }>();
  two.data!.observations.forEach((o) => byDate.set(o.date, { date: o.date, y2: o.value }));
  ten.data!.observations.forEach((o) => byDate.set(o.date, { ...(byDate.get(o.date) ?? { date: o.date }), y10: o.value }));
  const data = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
  if (!data.length) return <EmptyState title="No yield data in the last three years" />;
  return (
    <ChartCard
      title="2-year and 10-year Government of Canada yields"
      description="Last three years, percent. When the 2-year sits above the 10-year the curve is inverted."
      legend={[
        { label: "2-year", color: C.s1 },
        { label: "10-year", color: C.s2 },
      ]}
    >
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis dataKey="date" {...axisProps} tickFormatter={fmtMonth} minTickGap={48} />
            <YAxis {...axisProps} unit="%" domain={["auto", "auto"]} />
            <Tooltip
              cursor={{ stroke: C.axis, strokeDasharray: "3 3" }}
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <TooltipBox
                    title={fmtDate(String(payload[0].payload.date))}
                    rows={[
                      { label: "2-year", value: `${fmt(payload[0].payload.y2)}%`, color: C.s1 },
                      { label: "10-year", value: `${fmt(payload[0].payload.y10)}%`, color: C.s2 },
                    ]}
                  />
                ) : null
              }
            />
            <Line type="monotone" dataKey="y2" stroke={C.s1} strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="y10" stroke={C.s2} strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  );
}

function DqGlance() {
  const dq = useDqSummary();
  return (
    <Card className="flex flex-col gap-3 p-6">
      <p className="text-sm font-medium text-muted-foreground">Data quality, latest run</p>
      {dq.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {dq.isError && <p className="text-sm text-destructive">{(dq.error as Error).message}</p>}
      {dq.data && (
        <>
          <p className="text-3xl font-semibold tabular">
            {fmt(dq.data.pass_rate_pct, 1)}
            <span className="ml-1 text-base text-muted-foreground">% passed</span>
          </p>
          <p className="text-sm text-muted-foreground tabular">
            {dq.data.passed} of {dq.data.total} tests passed · {dq.data.warned} warnings ·{" "}
            {dq.data.failed + dq.data.errored} failures · {dq.data.anomaly_count} anomalies flagged
          </p>
          <Button variant="outline" size="sm" className="self-start" asChild>
            <Link href="/data-quality">Open the scorecard</Link>
          </Button>
        </>
      )}
    </Card>
  );
}

export default function OverviewPage() {
  const overview = useOverview();
  return (
    <>
      <PageHeader
        title="Overview"
        description="Headline Canadian market indicators from the gold layer of the warehouse, refreshed by the daily pipeline."
        actions={
          overview.data?.last_refreshed && (
            <p className="text-xs text-muted-foreground">Last refresh: {fmtDateTime(overview.data.last_refreshed)}</p>
          )
        }
      />
      {overview.isLoading && <KpiSkeleton count={5} />}
      {overview.isError && <ErrorState error={overview.error} onRetry={() => overview.refetch()} />}
      {overview.data && overview.data.kpis.length === 0 && <EmptyState title="No KPIs yet" hint="Run `make pipeline` to load data." />}
      {overview.data && overview.data.kpis.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          {overview.data.kpis.map((k) => (
            <KpiCard
              key={k.key}
              label={k.label}
              value={k.value}
              unit={k.unit}
              digits={DIGITS[k.key] ?? 2}
              change={k.change}
              changeDigits={CHANGE_DIGITS[k.key] ?? 2}
              changeLabel={k.change_label}
              asOf={k.as_of}
              badge={badgeFor(k)}
              spark={k.sparkline}
            />
          ))}
        </div>
      )}
      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <YieldsChart />
        </div>
        <DqGlance />
      </div>
    </>
  );
}
