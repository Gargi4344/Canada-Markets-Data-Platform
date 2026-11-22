"use client";

import {
  Area,
  AreaChart,
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
import { ChartSkeleton, EmptyState, ErrorState, KpiSkeleton } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { usePolicyRate } from "@/lib/api";
import { fmt, fmtDate, fmtMonth, signed } from "@/lib/utils";

export default function PolicyPage() {
  const policy = usePolicyRate();
  const d = policy.data;
  const last = d?.monthly[d.monthly.length - 1];
  const hikes = d?.events.filter((e) => e.direction === "hike").length ?? 0;
  const cuts = d?.events.filter((e) => e.direction === "cut").length ?? 0;

  return (
    <>
      <PageHeader
        title="Policy & Inflation"
        description="The Bank of Canada policy rate against CPI inflation, the 1–3% inflation-control target range, and the real policy rate."
      />
      {policy.isLoading && <KpiSkeleton />}
      {policy.isError && <ErrorState error={policy.error} onRetry={() => policy.refetch()} />}
      {d && !last && <EmptyState title="No monthly data yet" />}
      {d && last && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard label="Policy rate" value={d.current_rate} unit="%" asOf={d.events.at(-1)?.effective_date} />
            <KpiCard
              label="CPI inflation (y/y)"
              value={last.cpi_yoy_pct}
              unit="%"
              asOf={last.month}
              badge={
                last.cpi_yoy_pct > d.target_band[1] || last.cpi_yoy_pct < d.target_band[0]
                  ? { label: "Outside 1–3%", variant: "warning" }
                  : { label: "Inside 1–3%", variant: "success" }
              }
            />
            <KpiCard
              label="Real policy rate"
              value={last.real_policy_rate}
              unit="pp"
              asOf={last.month}
              badge={last.real_policy_rate < 0 ? { label: "Negative", variant: "muted" } : { label: "Positive", variant: "muted" }}
            />
            <KpiCard label="Rate changes in the data" value={d.events.length} digits={0} changeLabel={`${hikes} hikes, ${cuts} cuts`} change={null} />
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-2">
            <ChartCard
              title="Policy rate and CPI inflation"
              description="Monthly, percent. The policy rate is the end-of-month target (step line); the shaded band is the 1–3% target range around the 2% midpoint."
              legend={[
                { label: "Policy rate (end of month)", color: C.s1 },
                { label: "CPI inflation, year over year", color: C.s2 },
                { label: "1–3% target range", color: C.band, swatch: "area" },
              ]}
            >
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={d.monthly} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
                    <CartesianGrid stroke={C.grid} vertical={false} />
                    <XAxis dataKey="month" {...axisProps} tickFormatter={fmtMonth} minTickGap={56} />
                    <YAxis {...axisProps} unit="%" domain={["auto", "auto"]} />
                    <ReferenceArea y1={d.target_band[0]} y2={d.target_band[1]} fill={C.band} fillOpacity={1} />
                    <ReferenceLine y={d.inflation_target} stroke={C.axis} strokeDasharray="4 4" />
                    <Tooltip
                      cursor={{ stroke: C.axis, strokeDasharray: "3 3" }}
                      content={({ active, payload }) =>
                        active && payload?.length ? (
                          <TooltipBox
                            title={fmtMonth(String(payload[0].payload.month))}
                            rows={[
                              { label: "Policy rate", value: `${fmt(payload[0].payload.policy_rate_eom)}%`, color: C.s1 },
                              { label: "CPI y/y", value: `${fmt(payload[0].payload.cpi_yoy_pct, 1)}%`, color: C.s2 },
                            ]}
                          />
                        ) : null
                      }
                    />
                    <Line type="stepAfter" dataKey="policy_rate_eom" stroke={C.s1} strokeWidth={2} dot={false} isAnimationActive={false} />
                    <Line type="monotone" dataKey="cpi_yoy_pct" stroke={C.s2} strokeWidth={2} dot={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>

            <ChartCard
              title="Real policy rate"
              description="Average policy rate in the month minus CPI inflation, percentage points. Below zero, policy is accommodative in real terms."
            >
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={d.monthly} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
                    <CartesianGrid stroke={C.grid} vertical={false} />
                    <XAxis dataKey="month" {...axisProps} tickFormatter={fmtMonth} minTickGap={56} />
                    <YAxis {...axisProps} unit="%" domain={["auto", "auto"]} />
                    <ReferenceLine y={0} stroke={C.axis} />
                    <Tooltip
                      cursor={{ stroke: C.axis, strokeDasharray: "3 3" }}
                      content={({ active, payload }) =>
                        active && payload?.length ? (
                          <TooltipBox
                            title={fmtMonth(String(payload[0].payload.month))}
                            rows={[
                              { label: "Real policy rate", value: `${fmt(payload[0].payload.real_policy_rate)} pp`, color: C.s3 },
                              { label: "Policy rate (avg)", value: `${fmt(payload[0].payload.policy_rate_avg)}%` },
                              { label: "CPI y/y", value: `${fmt(payload[0].payload.cpi_yoy_pct, 1)}%` },
                            ]}
                          />
                        ) : null
                      }
                    />
                    <Area type="monotone" dataKey="real_policy_rate" stroke={C.s3} strokeWidth={2} fill={C.s3} fillOpacity={0.15} isAnimationActive={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>
          </div>

          <Card className="mt-6">
            <CardHeader>
              <CardTitle>Rate decisions</CardTitle>
              <CardDescription>
                Every change in the target for the overnight rate in the data. The effective date is the
                first business day the new target appears in Valet series V39079.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Effective date</TableHead>
                    <TableHead className="text-right">Old rate</TableHead>
                    <TableHead className="text-right">New rate</TableHead>
                    <TableHead className="text-right">Change</TableHead>
                    <TableHead>Direction</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {[...d.events].reverse().map((e) => (
                    <TableRow key={e.effective_date}>
                      <TableCell className="tabular">{fmtDate(e.effective_date)}</TableCell>
                      <TableCell className="text-right tabular">{fmt(e.old_rate)}%</TableCell>
                      <TableCell className="text-right tabular">{fmt(e.new_rate)}%</TableCell>
                      <TableCell className="text-right tabular">{signed(e.change_bps, 0)} bps</TableCell>
                      <TableCell>
                        <Badge variant={e.direction === "hike" ? "warning" : "accent"}>{e.direction}</Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
      {policy.isLoading && <div className="mt-6"><ChartSkeleton /></div>}
    </>
  );
}
