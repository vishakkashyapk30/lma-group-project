"use client";
// Cause-list board sorted by urgency with each case's next step (plan §11). No bulk export: opening a case goes to its
// own workspace, where it needs its own approval.
import { ArrowRight, FileWarning, ListChecks } from "lucide-react";
import Link from "next/link";
import { useMemo, type ReactElement } from "react";
import { Badge, Button } from "@/components/ui";
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
        <p className="font-display text-xl text-maroon">The board is empty</p>
        <p className="mt-1 text-sm text-ink-soft">Upload a folder or zip of case files and Pairokar will rank them.</p>
      </div>
    );
  }

  return (
    <div data-testid="desk-board" className={className}>
      <ol aria-label="Triage board, most urgent first" className="m-0 list-none divide-y divide-line overflow-hidden rounded-lg border border-line bg-cream p-0 shadow-sm">
        {sorted.map((c) => (
          <li key={c.case_id} data-testid="triage-card" data-case-id={c.case_id} className="grid gap-x-4 gap-y-3 px-4 py-4 sm:grid-cols-[3.5rem_1fr_auto] sm:px-5">
            <div className="flex items-baseline gap-2 sm:block">
              <span className="font-display text-4xl font-semibold leading-none text-maroon/80 tabular" aria-label={`Urgency rank ${c.urgency_rank}`}>{c.urgency_rank}</span>
            </div>
            <div className="min-w-0 space-y-2.5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="mono">{c.case_id}</Badge>
              </div>
              <ul className="m-0 list-none space-y-1 p-0">
                {c.reasons.map((r) => <li key={r} data-testid="triage-reason" className="font-display text-base font-medium leading-snug text-ink">{r}</li>)}
              </ul>
              {c.flags.length > 0 ? (
                <ul aria-label="Flags" className="m-0 flex list-none flex-wrap gap-1.5 p-0">
                  {c.flags.map((f) => {
                    const p = parseRightsChip(f);
                    return <li key={f} data-testid="triage-flag">{p.status ? <StatusBadge status={p.status} kind="rights" label={p.label} /> : <Badge variant="muted">{p.label}</Badge>}</li>;
                  })}
                </ul>
              ) : null}
              {c.missing_docs.length > 0 ? (
                <div className="flex flex-wrap items-center gap-1.5 text-sm text-haldi">
                  <FileWarning aria-hidden className="size-4" />
                  <span className="font-semibold">Missing:</span>
                  <ul aria-label="Missing documents" className="m-0 flex list-none flex-wrap gap-1.5 p-0">
                    {c.missing_docs.map((d) => <li key={d} data-testid="triage-missing" className="rounded-sm border border-haldi/50 bg-haldi/[0.07] px-1.5 py-0.5 text-xs font-medium">{d}</li>)}
                  </ul>
                </div>
              ) : (
                <p className="text-xs text-neem">No documents missing</p>
              )}
              {c.next_step ? (
                <p data-testid="triage-next-step" className="flex items-start gap-1.5 text-sm text-ink-soft">
                  <ListChecks aria-hidden className="mt-0.5 size-4 shrink-0 text-maroon" />
                  <span><span className="font-semibold text-ink">Next step:</span> {c.next_step}</span>
                </p>
              ) : null}
              <p className="text-xs font-semibold text-neem">Needs its own approval: nothing is exported from the board.</p>
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
