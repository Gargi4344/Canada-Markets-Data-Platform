"use client";

import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

import { Sparkline } from "@/components/charts";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { fmt, fmtDate, signed } from "@/lib/utils";

/** Headline number with its change, an optional status badge and a sparkline. */
export function KpiCard({
  label,
  value,
  unit,
  digits = 2,
  change,
  changeDigits = 2,
  changeLabel,
  asOf,
  badge,
  spark,
}: {
  label: string;
  value: number | null;
  unit?: string;
  digits?: number;
  change?: number | null;
  changeDigits?: number;
  changeLabel?: string;
  asOf?: string | null;
  badge?: { label: string; variant: "success" | "warning" | "destructive" | "muted" | "accent" } | null;
  spark?: { date: string; value: number }[];
}) {
  const Arrow = !change ? Minus : change > 0 ? ArrowUpRight : ArrowDownRight;
  return (
    <Card className="flex flex-col gap-2 p-5">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        {badge && <Badge variant={badge.variant}>{badge.label}</Badge>}
      </div>
      <p className="text-3xl font-semibold tracking-tight tabular">
        {fmt(value, digits)}
        {unit && <span className="ml-1 text-base font-medium text-muted-foreground">{unit}</span>}
      </p>
      {change !== undefined && change !== null && (
        <p className="flex items-center gap-1 text-xs text-muted-foreground tabular">
          <Arrow className="h-3.5 w-3.5" />
          <span className="font-medium text-foreground">{signed(change, changeDigits)}</span>
          {changeLabel}
        </p>
      )}
      {(change === undefined || change === null) && changeLabel && (
        <p className="text-xs text-muted-foreground tabular">{changeLabel}</p>
      )}
      {spark && spark.length > 1 && <Sparkline data={spark} digits={digits} unit={unit === "%" ? "%" : ""} />}
      {asOf && <p className="text-xs text-muted-foreground">As of {fmtDate(asOf)}</p>}
    </Card>
  );
}
