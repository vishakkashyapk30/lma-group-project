"use client";
// The filed documents: what each one is, how many pages, and whether it was read. How each page was read (language, route,
// confidence) opens under "Reading details". Choosing a document opens its first page beside the content.
import { ChevronDown } from "lucide-react";
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
  /** Called after a document is chosen (a popover closes itself). */
  onPick?: () => void;
  className?: string;
}

export function pageRange(d: DocumentEntry): { first: number; last: number; count: number } {
  const first = d.pages[0] ?? d.page_routes[0]?.page ?? 1;
  const last = d.pages[d.pages.length - 1] ?? first;
  return { first, last, count: Math.max(1, last - first + 1) };
}

/** The kind of page and every reading step any page of the document went through, in order (TEXT, LAYOUT, OCR, VISION). */
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

export function DocumentList({ caseId, onPick, className }: DocumentListProps): ReactElement {
  const ws = useWorkspace();
  const [open, setOpen] = useState<string | null>(null);
  const report = ws.data.ingestion;
  const documents = report?.documents ?? [];
  const demo = ws.mode === "demo";

  if (ws.loading.ingestion && !report) {
    return (
      <div className={cn("flex flex-col gap-3 p-4", className)} aria-busy="true" aria-label="Loading documents">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <p className={cn("text-sm text-ink-soft", className)}>
        Nothing is filed for case <span className="font-mono">{caseId}</span> yet.
      </p>
    );
  }

  return (
    <ul aria-label={`Documents (${documents.length})`} className={cn("divide-y divide-line", className)}>
      {documents.map((d) => {
        const range = pageRange(d);
        const route = routeSummary(d);
        const bad = d.page_routes.filter((p) => p.status === "UNREADABLE");
        const active = ws.activeDocId === d.doc_id && ws.selectedSource?.doc_id === d.doc_id;
        const expanded = open === d.doc_id;
        const title = demo ? MOCK_DOC_TITLES[d.doc_id] : undefined;
        return (
          <li key={d.doc_id} data-testid="document-item" data-doc-id={d.doc_id}>
            <div className="flex items-start gap-1">
              <button
                type="button"
                onClick={() => {
                  ws.selectSource({ doc: d.doc_id, page: range.first }, "document list");
                  onPick?.();
                }}
                aria-current={active ? "true" : undefined}
                className={cn("min-w-0 flex-1 rounded-md px-2 py-2.5 text-left hover:bg-parchment-deep/60", active && "bg-parchment-deep/60")}
              >
                <span className="block">
                  <span data-testid="doc-type-stamp" className="font-medium text-ink">{DOC_TYPE_LABELS[d.type]}</span>
                  {title ? <span className="ml-2 text-sm text-ink-soft">{title}</span> : null}
                </span>
                <span className="mt-0.5 flex flex-wrap items-center gap-x-3 text-sm text-ink-soft">
                  <span className="tabular">{range.count === 1 ? "1 page" : `${range.count} pages`}</span>
                  {bad.length > 0 ? (
                    <StatusBadge status="UNREADABLE" kind="page" detail={bad.length === 1 ? "1 page" : `${bad.length} pages`} />
                  ) : (
                    <span className="text-ink-muted">Read</span>
                  )}
                </span>
              </button>
              <button
                type="button"
                aria-expanded={expanded}
                aria-controls={`pages-${d.doc_id}`}
                onClick={() => setOpen(expanded ? null : d.doc_id)}
                className="mt-1.5 inline-flex h-8 shrink-0 items-center gap-1 rounded-md px-2 text-sm text-ink-soft hover:bg-ink/[0.06] hover:text-ink"
              >
                Reading details
                <ChevronDown aria-hidden className={cn("size-4 transition-transform duration-fast", expanded && "rotate-180")} />
                <span className="sr-only"> for {DOC_TYPE_LABELS[d.type]}</span>
              </button>
            </div>
            {expanded ? (
              <div id={`pages-${d.doc_id}`} className="mb-3 ml-2 border-l border-line pl-4">
                <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink-soft">
                  <span className="font-mono text-xs">{d.doc_id}</span>
                  <Badge variant="mono" size="sm" lang={d.lang === "hi" ? "hi" : undefined} title={langLabel(d.lang)}>{d.lang}</Badge>
                  <Badge variant="mono" size="sm">{route.kind}</Badge>
                  {route.rungs.map((r) => (
                    <Badge key={r} variant="mono" size="sm" data-testid="route-badge" data-route={r} title={ROUTE_BADGES[r].label}>
                      {ROUTE_BADGES[r].badge}
                    </Badge>
                  ))}
                  {d.type_confidence != null && d.type_confidence < 0.9 ? <span>Label confidence {Math.round(d.type_confidence * 100)}%</span> : null}
                </p>
                <ul className="mt-2 flex flex-col">
                  {d.page_routes.map((p) => (
                    <li key={p.page}>
                      <button
                        type="button"
                        onClick={() => {
                          ws.selectSource({ doc: d.doc_id, page: p.page }, "document list");
                          onPick?.();
                        }}
                        className="flex w-full flex-wrap items-center gap-x-3 gap-y-0.5 rounded-sm px-1.5 py-1 text-left text-sm hover:bg-parchment-deep/60"
                      >
                        <span className="tabular font-medium text-ink">Page {p.page}</span>
                        <span className="text-ink-soft">{p.kind}</span>
                        <span className="font-mono text-xs text-ink-muted">{p.route.join(" → ")}</span>
                        {p.ocr_conf != null ? <span className="tabular text-xs text-ink-muted">{Math.round(p.ocr_conf * 100)}% sure</span> : null}
                        {p.status === "UNREADABLE" ? <StatusBadge status={p.status} kind="page" size="sm" /> : null}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

export default DocumentList;
