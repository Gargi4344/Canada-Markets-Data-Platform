"use client";

import { CircleCheck, CircleX, TriangleAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";

const FRESH = {
  green: { variant: "success", label: "Fresh", Icon: CircleCheck },
  amber: { variant: "warning", label: "Late", Icon: TriangleAlert },
  red: { variant: "destructive", label: "Stale", Icon: CircleX },
} as const;

/** Freshness chip: colour plus icon plus text, never colour alone. */
export function FreshnessChip({ status, text }: { status: string | null; text?: string }) {
  const s = FRESH[(status ?? "red") as keyof typeof FRESH] ?? FRESH.red;
  return (
    <Badge variant={s.variant}>
      <s.Icon />
      {text ?? s.label}
    </Badge>
  );
}

const TEST = {
  pass: { variant: "success", label: "Pass", Icon: CircleCheck },
  warn: { variant: "warning", label: "Warn", Icon: TriangleAlert },
  fail: { variant: "destructive", label: "Fail", Icon: CircleX },
  error: { variant: "destructive", label: "Error", Icon: CircleX },
} as const;

/** Status chip for a data quality test. */
export function TestStatus({ status }: { status: string }) {
  const s = TEST[status as keyof typeof TEST] ?? TEST.error;
  return (
    <Badge variant={s.variant}>
      <s.Icon />
      {s.label}
    </Badge>
  );
}
