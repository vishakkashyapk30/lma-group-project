"use client";
// The filed documents (plan §4.6, §13.5): type, language and route badges ("FIR · hi · scanned → OCR"), page range,
// page count and status. Choosing a document shows it in the viewer; its pages expand to per-page routes.
import { ChevronDown, FileText, HelpCircle } from "lucide-react";
import { useState, type ReactElement } from "react";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { DOC_TYPE_LABELS, ROUTE_BADGES, langLabel, routeStepRung } from "@/lib/labels";
import { MOCK_DOC_TITLES } from "@/lib/mock/case0007";
import type { DocumentEntry, ParseRoute } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";

export interface DocumentListProps {
  caseId: string;
  className?: string;
}

function pageRange(d: DocumentEntry): { first: number; last: number; count: number } {
  const first = d.pages[0] ?? d.page_routes[0]?.page ?? 1;
  const last = d.pages[d.pages.length - 1] ?? first;
  return { first, last, count: Math.max(1, last - first + 1) };
}

/**
 * "scanned, handwriting" and every ladder rung any page of the document went through (TEXT, LAYOUT, OCR, VISION), in ladder
 * order. Asking counsel is not a reading rung: it shows as the page's UNREADABLE status and as Munshi's question.
 */
function routeSummary(d: DocumentEntry): { kind: string; rungs: ParseRoute[] } {
  const kinds = Array.from(new Set(d.page_routes.map((p) => p.kind.split(",")[0].trim()).filter(Boolean)));
  const seen = new Set<ParseRoute>();
  for (const p of d.page_routes) {
    for (const step of p.route) {
      const rung = routeStepRung(step);
      if (rung && rung !== "ask_counsel") seen.add(rung);
    }
  }
  const rungs = [...seen].sort((a, b) => ROUTE_BADGES[a].step - ROUTE_BADGES[b].step);
  return { kind: kinds[0] ?? "unknown", rungs };
}

export function DocumentList({ caseId, className }: DocumentListProps): ReactElement {
  const ws = useWorkspace();
  const [open, setOpen] = useState<string | null>(null);
  const report = ws.data.ingestion;
  const documents = report?.documents ?? [];
  const demo = ws.mode === "demo";

  if (ws.loading.ingestion && !report) {
    return (
      <div className={cn("flex flex-col gap-2 p-3", className)} aria-busy="true" aria-label="Loading documents">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className={cn("p-3", className)}>
        <p className="rounded-md border border-dashed border-line-strong/60 bg-cream p-3 text-sm text-ink-soft">
          Nothing is filed for case <span className="font-mono">{caseId}</span> yet. Drop a bundle below and Munshi will split it, label each document and
          show how every page was read.
        </p>
      </div>
    );
  }

  const unreadable = documents.reduce((n, d) => n + d.page_routes.filter((p) => p.status === "UNREADABLE").length, 0);

  return (
    <div className={cn("flex flex-col", className)}>
      <ul aria-label={`Filed documents (${documents.length})`} className="flex flex-col divide-y divide-line">
        {documents.map((d) => {
          const range = pageRange(d);
          const route = routeSummary(d);
          const bad = d.page_routes.filter((p) => p.status === "UNREADABLE");
          const active = ws.activeDocId === d.doc_id;
          const expanded = open === d.doc_id;
          const title = demo ? MOCK_DOC_TITLES[d.doc_id] : undefined;
          return (
            <li key={d.doc_id} data-testid="document-item" data-doc-id={d.doc_id} className={cn("relative", active && "bg-gold/10")}>
              {active ? <span aria-hidden className="absolute inset-y-0 left-0 w-1 bg-maroon" /> : null}
              <div className="flex items-start gap-1 pr-2">
                <button
                  type="button"
                  onClick={() => ws.selectSource({ doc: d.doc_id, page: range.first }, "document list")}
                  aria-current={active ? "true" : undefined}
                  className="flex min-w-0 flex-1 items-start gap-2.5 rounded-sm px-3 py-2.5 text-left hover:bg-parchment-deep/50"
                >
                  <FileText aria-hidden className={cn("mt-0.5 size-4 shrink-0", active ? "text-maroon" : "text-ink-muted")} />
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <span data-testid="doc-type-stamp" className="font-display text-sm font-semibold text-ink">{DOC_TYPE_LABELS[d.type]}</span>
                      <span className="font-mono text-2xs text-ink-muted">{d.doc_id}</span>
                      {bad.length > 0 ? <StatusBadge status="UNREADABLE" kind="page" size="sm" detail={`${bad.length} page${bad.length === 1 ? "" : "s"}`} /> : null}
                    </span>
                    {title ? <span className="mt-0.5 block truncate text-xs text-ink-soft">{title}</span> : null}
                    <span className="mt-1.5 flex flex-wrap items-center gap-1">
                      <Badge variant="mono" size="sm" lang={d.lang === "hi" ? "hi" : undefined} title={langLabel(d.lang)}>{d.lang}</Badge>
                      <Badge variant="mono" size="sm" title="What kind of pages these are">{route.kind}</Badge>
                      {route.rungs.map((r) => (
                        <Badge key={r} variant="mono" size="sm" data-testid="route-badge" data-route={r} title={ROUTE_BADGES[r].label}>
                          {ROUTE_BADGES[r].badge}
                        </Badge>
                      ))}
                      <Badge variant="outline" size="sm">
                        {range.count === 1 ? `p.${range.first}` : `pp.${range.first}–${range.last}`} · {range.count} page{range.count === 1 ? "" : "s"}
                      </Badge>
                      {d.type_confidence != null && d.type_confidence < 0.9 ? (
                        <Badge variant="haldi" size="sm" title="Munshi's confidence in the document label">
                          label {Math.round(d.type_confidence * 100)}%
                        </Badge>
                      ) : null}
                    </span>
                  </span>
                </button>
                <button
                  type="button"
                  aria-expanded={expanded}
                  aria-controls={`pages-${d.doc_id}`}
                  onClick={() => setOpen(expanded ? null : d.doc_id)}
                  className="mt-2 grid size-8 shrink-0 place-items-center rounded-md text-ink-soft hover:bg-ink/[0.06] hover:text-ink"
                >
                  <ChevronDown aria-hidden className={cn("size-4 transition-transform duration-fast", expanded && "rotate-180")} />
                  <span className="sr-only">{expanded ? "Hide" : "Show"} page routes for {DOC_TYPE_LABELS[d.type]} {d.doc_id}</span>
                </button>
              </div>
              {expanded ? (
                <ul id={`pages-${d.doc_id}`} className="mx-3 mb-2.5 ml-9 flex flex-col gap-1 border-l border-line pl-3">
                  {d.page_routes.map((p) => (
                    <li key={p.page}>
                      <button
                        type="button"
                        onClick={() => ws.selectSource({ doc: d.doc_id, page: p.page }, "document list")}
                        className="flex w-full flex-wrap items-center gap-x-2 gap-y-0.5 rounded-sm px-1.5 py-1 text-left text-xs hover:bg-parchment-deep/60"
                      >
                        <span className="font-mono font-semibold text-ink">p.{p.page}</span>
                        <span className="text-ink-soft">{p.kind}</span>
                        <span className="font-mono text-ink-muted">{p.route.join(" → ")}</span>
                        {p.ocr_conf != null ? <span className="font-mono text-ink-muted">conf {Math.round(p.ocr_conf * 100)}%</span> : null}
                        <StatusBadge status={p.status} kind="page" size="sm" />
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          );
        })}
      </ul>

      {report && (report.questions.length > 0 || report.gaps.length > 0 || unreadable > 0) ? (
        <div className="m-3 rounded-md border border-haldi/40 bg-haldi/[0.06] p-3 text-xs text-ink">
          <p className="mb-1 flex items-center gap-1.5 font-display text-sm font-semibold text-maroon">
            <HelpCircle aria-hidden className="size-4" /> Munshi asks
          </p>
          <ul className="list-disc space-y-1 pl-4">
            {report.questions.map((q) => (
              <li key={q}>{q}</li>
            ))}
            {report.gaps.map((g) => (
              <li key={g.item}>
                <span className="font-semibold">{g.item}:</span> {g.action}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {report ? (
        <p className="px-3 pb-2 text-2xs text-ink-muted">
          Filed from {report.file}: {report.filed.timeline_events} dated events, {report.filed.parties} parties, {report.filed.sections} sections,{" "}
          {report.filed.chunks} chunks.
        </p>
      ) : null}
    </div>
  );
}

export default DocumentList;
