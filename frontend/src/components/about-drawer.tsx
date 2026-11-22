"use client";

import { ExternalLink, Info } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { site } from "@/config/site";
import { useHealth } from "@/lib/api";
import { fmtDate, fmtDateTime } from "@/lib/utils";

/** "About this data" drawer: sources, licences and when the data was last refreshed. */
export function AboutDrawer() {
  const health = useHealth();
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm">
          <Info />
          <span className="hidden sm:inline">About this data</span>
        </Button>
      </SheetTrigger>
      <SheetContent>
        <div>
          <SheetTitle>About this data</SheetTitle>
          <SheetDescription>{site.tagline}</SheetDescription>
        </div>

        <section className="space-y-3">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Sources</h4>
          {site.sources.map((s) => (
            <div key={s.name} className="rounded-xl border p-4 text-sm">
              <a href={s.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-medium hover:underline">
                {s.name} <ExternalLink className="h-3 w-3" />
              </a>
              <p className="mt-1 text-muted-foreground">{s.detail}</p>
              <p className="mt-2 text-xs">
                Licence:{" "}
                <a href={s.licenceUrl} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                  {s.licence}
                </a>
              </p>
            </div>
          ))}
        </section>

        <section className="space-y-2 text-sm">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Last refreshed</h4>
          {health.isLoading && <p className="text-muted-foreground">Loading…</p>}
          {health.isError && <p className="text-destructive">{(health.error as Error).message}</p>}
          {health.data && (
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
              <dt className="text-muted-foreground">Pipeline run</dt>
              <dd className="tabular">{fmtDateTime(health.data.last_run_at)}</dd>
              <dt className="text-muted-foreground">Data as of</dt>
              <dd className="tabular">{fmtDate(health.data.as_of)}</dd>
              <dt className="text-muted-foreground">Status</dt>
              <dd>{health.data.last_run_status ?? "–"}</dd>
              <dt className="text-muted-foreground">Observations</dt>
              <dd className="tabular">{health.data.total_observations?.toLocaleString("en-CA") ?? "–"}</dd>
            </dl>
          )}
        </section>

        <p className="mt-auto text-xs text-muted-foreground">
          Data is downloaded from the public APIs at runtime and is not redistributed in the code
          repository. This dashboard is for information only and is not investment advice.
        </p>
      </SheetContent>
    </Sheet>
  );
}
