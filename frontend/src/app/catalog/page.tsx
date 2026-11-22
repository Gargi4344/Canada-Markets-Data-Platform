"use client";

import { ExternalLink, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { KpiCard } from "@/components/kpi-card";
import { PageHeader } from "@/components/page-header";
import { FreshnessChip } from "@/components/status";
import { EmptyState, ErrorState, KpiSkeleton } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { API_URL, useSeries } from "@/lib/api";
import { fmtDate } from "@/lib/utils";

export default function CatalogPage() {
  const series = useSeries();
  const [q, setQ] = useState("");
  const rows = useMemo(() => {
    const term = q.trim().toLowerCase();
    return (series.data ?? []).filter((s) =>
      !term
        ? true
        : [s.series_key, s.series_name, s.source_id, s.category, s.unit, s.description]
            .join(" ")
            .toLowerCase()
            .includes(term),
    );
  }, [series.data, q]);
  const total = series.data?.reduce((n, s) => n + s.observation_count, 0) ?? 0;

  return (
    <>
      <PageHeader
        title="Data Catalog"
        description="Every series in the warehouse with its source, unit, frequency and coverage. Column-level documentation and lineage are in the dbt docs."
        actions={
          <Button variant="outline" size="sm" asChild>
            <a href={`${API_URL}/dbt-docs/index.html`} target="_blank" rel="noreferrer">
              dbt docs (lineage and data dictionary) <ExternalLink />
            </a>
          </Button>
        }
      />
      {series.isLoading && <KpiSkeleton count={3} />}
      {series.isError && <ErrorState error={series.error} onRetry={() => series.refetch()} />}
      {series.data && (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <KpiCard label="Series" value={series.data.length} digits={0} />
            <KpiCard label="Observations" value={total} digits={0} />
            <KpiCard label="Sources" value={new Set(series.data.map((s) => s.source)).size} digits={0} />
          </div>
          <Card className="mt-6">
            <CardContent className="pt-6">
              <div className="relative mb-4 max-w-sm">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search series, IDs, units…"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  className="pl-9"
                  aria-label="Search the catalog"
                />
              </div>
              {rows.length === 0 ? (
                <EmptyState title="No series match your search" hint="Try a series key such as GOC_10Y or a word like 'yield'." />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Series</TableHead>
                      <TableHead>Source ID</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead>Unit</TableHead>
                      <TableHead>Frequency</TableHead>
                      <TableHead>Coverage</TableHead>
                      <TableHead className="text-right">Rows</TableHead>
                      <TableHead>Freshness</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((s) => (
                      <TableRow key={s.series_key}>
                        <TableCell className="min-w-64">
                          <p className="font-medium">{s.series_name}</p>
                          <p className="font-mono text-xs text-muted-foreground">{s.series_key}</p>
                          <p className="mt-1 text-xs text-muted-foreground">{s.description}</p>
                        </TableCell>
                        <TableCell>
                          <a href={s.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-mono text-xs text-accent hover:underline">
                            {s.source_id} <ExternalLink className="h-3 w-3" />
                          </a>
                        </TableCell>
                        <TableCell><Badge variant="muted">{s.category.replace("_", " ")}</Badge></TableCell>
                        <TableCell className="text-xs">{s.unit}</TableCell>
                        <TableCell className="text-xs">{s.frequency}</TableCell>
                        <TableCell className="whitespace-nowrap text-xs tabular">
                          {fmtDate(s.first_date)} – {fmtDate(s.last_date)}
                        </TableCell>
                        <TableCell className="text-right tabular">{s.observation_count.toLocaleString("en-CA")}</TableCell>
                        <TableCell><FreshnessChip status={s.freshness_status} /></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </>
      )}
      {series.isLoading && <Skeleton className="mt-6 h-96 rounded-2xl" />}
    </>
  );
}
