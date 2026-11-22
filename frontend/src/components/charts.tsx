"use client";

import { Line, LineChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn, fmt, fmtDate } from "@/lib/utils";

/** Chart colours come from CSS variables so light and dark mode each use validated steps. */
export const C = {
  s1: "var(--series-1)",
  s2: "var(--series-2)",
  s3: "var(--series-3)",
  grid: "var(--chart-grid)",
  axis: "var(--chart-axis)",
  band: "var(--chart-band)",
  alert: "var(--chart-alert)",
  critical: "hsl(var(--destructive))",
};

export const axisProps = {
  stroke: C.axis,
  tick: { fill: C.axis, fontSize: 12 },
  tickLine: false,
  axisLine: { stroke: C.grid },
} as const;

/** Card that frames a chart with a title, a description and an optional legend. */
export function ChartCard({
  title,
  description,
  legend,
  actions,
  children,
  className,
}: {
  title: string;
  description?: string;
  legend?: { label: string; color: string; dashed?: boolean; swatch?: "line" | "area" }[];
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn("min-w-0", className)}>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3">
        <div>
          <CardTitle>{title}</CardTitle>
          {description && <CardDescription className="mt-1">{description}</CardDescription>}
        </div>
        {actions}
      </CardHeader>
      <CardContent>
        {legend && legend.length > 0 && (
          <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground" aria-label="Legend">
            {legend.map((l) => (
              <li key={l.label} className="flex items-center gap-1.5">
                {l.swatch === "area" ? (
                  <span className="inline-block h-3 w-3 rounded-sm" style={{ background: l.color }} />
                ) : (
                  <span
                    className="inline-block w-4"
                    style={{ borderTop: `2px ${l.dashed ? "dashed" : "solid"} ${l.color}` }}
                  />
                )}
                {l.label}
              </li>
            ))}
          </ul>
        )}
        {children}
      </CardContent>
    </Card>
  );
}

/** Tooltip body shared by the charts: date heading and one row per series. */
export function TooltipBox({
  title,
  rows,
}: {
  title: string;
  rows: { label: string; value: string; color?: string }[];
}) {
  return (
    <div className="rounded-xl border bg-card px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-medium">{title}</p>
      {rows.map((r) => (
        <p key={r.label} className="flex items-center gap-2 tabular">
          {r.color && <span className="inline-block h-2 w-2 rounded-full" style={{ background: r.color }} />}
          <span className="text-muted-foreground">{r.label}</span>
          <span className="ml-auto pl-3 font-medium">{r.value}</span>
        </p>
      ))}
    </div>
  );
}

/** Small line chart for KPI cards, with a hover tooltip. */
export function Sparkline({
  data,
  digits = 2,
  unit = "",
}: {
  data: { date: string; value: number }[];
  digits?: number;
  unit?: string;
}) {
  return (
    <div className="h-14 w-full" aria-hidden>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 2, bottom: 4, left: 2 }}>
          <YAxis hide domain={["dataMin", "dataMax"]} />
          <Tooltip
            cursor={{ stroke: C.grid }}
            content={({ active, payload }) =>
              active && payload?.length ? (
                <TooltipBox
                  title={fmtDate(String(payload[0].payload.date))}
                  rows={[{ label: "Value", value: `${fmt(Number(payload[0].value), digits)}${unit}` }]}
                />
              ) : null
            }
          />
          <Line type="monotone" dataKey="value" stroke={C.s1} strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
