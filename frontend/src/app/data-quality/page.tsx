"use client";

import { useState } from "react";

import { KpiCard } from "@/components/kpi-card";
import { PageHeader } from "@/components/page-header";
import { FreshnessChip, TestStatus } from "@/components/status";
import { EmptyState, ErrorState, KpiSkeleton } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useDqSummary } from "@/lib/api";
import { fmt, fmtDate, fmtDateTime } from "@/lib/utils";

const CATEGORY_LABEL: Record<string, string> = {
  integrity: "Integrity (not null, unique, relationships, accepted values)",
  range: "Range (yields -1% to 20%, FX > 0, catalog ranges)",
  freshness: "Freshness (latest value within 5 business days)",
  completeness: "Completeness (no missing business days or months)",
  anomaly: "Anomaly (day-over-day move > 5σ of the last 250 days)",
  reconciliation: "Reconciliation (load log = bronze = silver + removals = facts)",
};
const ORDER = ["freshness", "completeness", "range", "anomaly", "reconciliation", "integrity"];

/** Pass / warn / fail proportions of one control category, with counts as text. */
function CategoryBar({ counts }: { counts: Record<string, number> }) {
  const total = counts.total ?? 0;
  const parts = [
    { key: "pass", cls: "bg-success", label: "passed" },
    { key: "warn", cls: "bg-warning", label: "warnings" },
    { key: "fail", cls: "bg-destructive", label: "failed" },
    { key: "error", cls: "bg-destructive", label: "errors" },
  ].filter((p) => (counts[p.key] ?? 0) > 0);
  return (
    <div>
      <div className="flex h-2.5 w-full gap-0.5 overflow-hidden rounded-full bg-muted" role="img" aria-label={parts.map((p) => `${counts[p.key]} ${p.label}`).join(", ")}>
        {parts.map((p) => (
          <div key={p.key} className={`${p.cls} h-full`} style={{ width: `${(100 * counts[p.key]) / total}%` }} title={`${counts[p.key]} ${p.label}`} />
        ))}
      </div>
      <p className="mt-1 text-xs text-muted-foreground tabular">
        {parts.map((p) => `${counts[p.key]} ${p.label}`).join(" · ")} of {total}
      </p>
    </div>
  );
}

export default function DataQualityPage() {
  const dq = useDqSummary();
  const [showAll, setShowAll] = useState(false);
  const d = dq.data;
  const tests = d ? (showAll ? d.tests : d.tests.filter((t) => t.status !== "pass")) : [];

  return (
    <>
      <PageHeader
        title="Data Quality"
        description="Results of every data quality control from the latest pipeline run (stored in gold.dq_results). Monitoring checks warn; structural checks fail the run."
        actions={d && <p className="text-xs text-muted-foreground">Run {d.run_id} · {fmtDateTime(d.run_at)}</p>}
      />
      {dq.isLoading && <KpiSkeleton />}
      {dq.isError && <ErrorState error={dq.error} onRetry={() => dq.refetch()} />}
      {d && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard label="Pass rate" value={d.pass_rate_pct} unit="%" digits={1} change={null} changeLabel={`${d.passed} of ${d.total} tests passed`} />
            <KpiCard label="Warnings" value={d.warned} digits={0} badge={d.warned ? { label: "Review", variant: "warning" } : { label: "None", variant: "success" }} />
            <KpiCard label="Failures and errors" value={d.failed + d.errored} digits={0} badge={d.failed + d.errored ? { label: "Action needed", variant: "destructive" } : { label: "None", variant: "success" }} />
            <KpiCard label="Anomalies flagged" value={d.anomaly_count} digits={0} badge={{ label: "For review", variant: "muted" }} />
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Scorecard by control</CardTitle>
                <CardDescription>Tests per data quality control and their outcome.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {ORDER.filter((c) => d.by_category[c]).map((c) => (
                  <div key={c}>
                    <p className="mb-1 text-sm font-medium">{CATEGORY_LABEL[c] ?? c}</p>
                    <CategoryBar counts={d.by_category[c]} />
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Freshness per series</CardTitle>
                <CardDescription>
                  Business days since the latest value (since month end for CPI). Green within the
                  threshold, amber within twice the threshold, red beyond.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="flex flex-wrap gap-2">
                  {d.freshness.map((f) => (
                    <li key={f.series_key} title={`Latest ${fmtDate(f.latest_obs_date)} · ${f.business_days_since} of ${f.threshold_business_days} business days`}>
                      <FreshnessChip status={f.status} text={`${f.series_key} · ${f.business_days_since}d`} />
                    </li>
                  ))}
                </ul>
                <Table className="mt-4">
                  <TableHeader>
                    <TableRow>
                      <TableHead>Series</TableHead>
                      <TableHead className="text-right">Completeness</TableHead>
                      <TableHead className="text-right">Missing periods</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {d.completeness.map((c) => (
                      <TableRow key={c.series_key}>
                        <TableCell className="font-medium">{c.series_key}</TableCell>
                        <TableCell className="text-right tabular">{fmt(c.completeness_pct, 2)}%</TableCell>
                        <TableCell className="text-right tabular">
                          {c.missing_periods} of {c.expected_periods.toLocaleString("en-CA")}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>

          <Card className="mt-6">
            <CardHeader>
              <CardTitle>Anomalies</CardTitle>
              <CardDescription>
                Latest {d.anomalies.length} of {d.anomaly_count} day-over-day moves larger than 5 standard
                deviations of the previous 250 moves. Flags for review, not errors: rate decisions and
                market shocks cause genuine large moves.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {d.anomalies.length === 0 ? (
                <EmptyState title="No anomalies flagged" />
              ) : (
                <div className="max-h-96 overflow-y-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Date</TableHead>
                        <TableHead>Series</TableHead>
                        <TableHead className="text-right">Value</TableHead>
                        <TableHead className="text-right">Change</TableHead>
                        <TableHead className="text-right">z-score</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {d.anomalies.map((a) => (
                        <TableRow key={`${a.series_key}-${a.obs_date}`}>
                          <TableCell className="tabular">{fmtDate(a.obs_date)}</TableCell>
                          <TableCell className="font-medium">{a.series_key}</TableCell>
                          <TableCell className="text-right tabular">{fmt(a.value, 4)}</TableCell>
                          <TableCell className="text-right tabular">{fmt(a.change, 4)}</TableCell>
                          <TableCell className="text-right tabular">{fmt(a.z_score, 1)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="mt-6">
            <CardHeader className="flex-row flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle>Tests</CardTitle>
                <CardDescription>
                  {showAll ? `All ${d.tests.length} tests.` : `${tests.length} tests that did not pass.`}
                </CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={() => setShowAll((v) => !v)}>
                {showAll ? "Show only issues" : `Show all ${d.tests.length}`}
              </Button>
            </CardHeader>
            <CardContent>
              {tests.length === 0 ? (
                <EmptyState title="Every test passed" />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Test</TableHead>
                      <TableHead>Control</TableHead>
                      <TableHead>Table</TableHead>
                      <TableHead>Severity</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Failing rows</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {tests.map((t) => (
                      <TableRow key={t.test_name}>
                        <TableCell className="max-w-xs truncate font-mono text-xs" title={t.test_name}>{t.test_name}</TableCell>
                        <TableCell>{t.dq_category}</TableCell>
                        <TableCell className="font-mono text-xs">{t.table_name ?? "–"}</TableCell>
                        <TableCell>{t.severity}</TableCell>
                        <TableCell><TestStatus status={t.status} /></TableCell>
                        <TableCell className="text-right tabular">{t.failed_rows}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </>
      )}
      {dq.isLoading && <Skeleton className="mt-6 h-96 rounded-2xl" />}
    </>
  );
}
