"use client";
// Triage board sorted by urgency with each case's next step. No bulk export: opening a case goes to its
// own workspace, where it needs its own approval.
import { ArrowRight, FileWarning, ListChecks } from "lucide-react";
import Link from "next/link";
import { useMemo, type ReactElement } from "react";
import { Button } from "@/components/ui";
import { StatusBadge } from "@/components/common/StatusBadge";
import { openDeskCase } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { parseRightsChip } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { TriageCard } from "@/lib/types";

export interface TriageBoardProps {
  cards: TriageCard[];
  className?: string;
}

export function TriageBoard({ cards, className }: TriageBoardProps): ReactElement {
  const sorted = useMemo(() => [...cards].sort((a, b) => a.urgency_rank - b.urgency_rank), [cards]);

  // Opening a case tells the desk router (best effort) and goes to the case's own workspace, where it needs its own approval.
  const open = (id: string) => {
    void openDeskCase(id).catch(() => undefined);
  };

  if (sorted.length === 0) {
    return (
      <div data-testid="desk-board" className={cn("rounded-lg border border-dashed border-line-strong/60 bg-cream p-10 text-center", className)}>
        <p className="font-display text-lg font-semibold">The board is empty</p>
        <p className="mt-1 text-sm text-ink-soft">Add a folder or zip of case files and they will be ranked here.</p>
      </div>
    );
  }

  return (
    <div data-testid="desk-board" className={className}>
      <ol aria-label="Triage board, most urgent first" className="m-0 list-none divide-y divide-line overflow-hidden rounded-lg border border-line bg-cream p-0">
        {sorted.map((c) => (
          <li key={c.case_id} data-testid="triage-card" data-case-id={c.case_id} className="grid gap-x-4 gap-y-3 px-4 py-4 sm:grid-cols-[1fr_auto] sm:px-5">
            <div className="min-w-0 space-y-2">
              <p className="flex flex-wrap items-baseline gap-x-3 text-xs text-ink-muted">
                <span className="font-mono">{c.case_id}</span>
                <span className="tabular">Priority {c.urgency_rank}</span>
              </p>
              <ul className="m-0 list-none space-y-1 p-0">
                {c.reasons.map((r) => <li key={r} data-testid="triage-reason" className="font-display text-[1.0625rem] font-semibold leading-snug text-ink">{r}</li>)}
              </ul>
              {c.flags.length > 0 ? (
                <ul aria-label="Flags" className="m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0">
                  {c.flags.map((f) => {
                    const p = parseRightsChip(f);
                    return <li key={f} data-testid="triage-flag">{p.status ? <StatusBadge status={p.status} kind="rights" label={p.label} /> : <span className="text-[13px] text-ink-soft">{p.label}</span>}</li>;
                  })}
                </ul>
              ) : null}
              {c.missing_docs.length > 0 ? (
                <div className="flex flex-wrap items-center gap-1.5 text-sm text-haldi">
                  <FileWarning aria-hidden className="size-4" />
                  <span className="font-medium">Missing:</span>
                  <ul aria-label="Missing documents" className="m-0 flex list-none flex-wrap gap-1.5 p-0">
                    {c.missing_docs.map((d) => <li key={d} data-testid="triage-missing" className="text-sm">{d}</li>)}
                  </ul>
                </div>
              ) : (
                <p className="text-xs text-neem">No documents missing</p>
              )}
              {c.next_step ? (
                <p data-testid="triage-next-step" className="flex items-start gap-1.5 text-sm text-ink-soft">
                  <ListChecks aria-hidden className="mt-0.5 size-4 shrink-0 text-maroon" />
                  <span><span className="font-medium text-ink">Next step:</span> {c.next_step}</span>
                </p>
              ) : null}
            </div>
            <div className="flex items-start sm:justify-end">
              <Button asChild variant="secondary" size="sm">
                <Link href={`/case/${encodeURIComponent(c.case_id)}`} onClick={() => open(c.case_id)} aria-label={`Open ${c.case_id}`}>
                  Open case <ArrowRight aria-hidden />
                </Link>
              </Button>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

export default TriageBoard;
