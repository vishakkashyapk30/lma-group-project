"use client";
// Cases: matters by stage with rights to check (urgent first) and items needing attention.
import { Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type ReactElement } from "react";
import { PageHeader } from "@/components/common/PageHeader";
import { useShell } from "@/components/shell/ShellProvider";
import { Button, EmptyState, Input, Skeleton } from "@/components/ui";
import { fieldClasses } from "@/components/ui/input";
import { listCases } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { STAGES } from "@/lib/stages";
import { RIGHTS_URGENCY, parseRightsChip } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { Stage } from "@/lib/types";
import { CaseCard, type CaseSummaryWithActivity } from "./CaseCard";

export interface CauseListProps {
  className?: string;
}

function urgency(c: CaseSummaryWithActivity): number {
  let best = 99;
  for (const chip of c.rights_chips ?? []) {
    const s = parseRightsChip(chip).status;
    if (s) best = Math.min(best, RIGHTS_URGENCY[s]);
  }
  return best;
}

export function CauseList({ className }: CauseListProps): ReactElement {
  const { setNewCaseOpen } = useShell();
  const [cases, setCases] = useState<CaseSummaryWithActivity[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [stage, setStage] = useState<Stage | "ALL">("ALL");

  const load = useCallback(async () => {
    try {
      setError(null);
      setCases(await listCases());
    } catch (e) {
      setError(errorMessage(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const visible = useMemo(() => {
    if (!cases) return [];
    const q = query.trim().toLowerCase();
    return cases
      .filter((c) => (stage === "ALL" || c.stage === stage) && (!q || `${c.title} ${c.case_id} ${c.rights_chips.join(" ")}`.toLowerCase().includes(q)))
      .map((c, i) => ({ c, i }))
      .sort((a, b) => urgency(a.c) - urgency(b.c) || b.c.needs_attention - a.c.needs_attention || a.i - b.i)
      .map((x) => x.c);
  }, [cases, query, stage]);

  const attention = useMemo(() => (cases ?? []).reduce((s, c) => s + c.needs_attention, 0), [cases]);

  return (
    <div className={cn("mx-auto max-w-content px-4 py-8 sm:px-6 sm:py-10", className)}>
      <PageHeader title="Cases" description="Every matter, with the most urgent possible entitlement first. These are things to check, never advice or a prediction." />

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <div className="relative min-w-[14rem] flex-1">
          <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-muted" />
          <Input
            type="search"
            aria-label="Search cases"
            placeholder="Search by title, case number or right"
            className="pl-9"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-ink-soft">
          Stage
          <select className={cn(fieldClasses, "h-9 w-auto min-w-[10rem]")} value={stage} onChange={(e) => setStage(e.target.value as Stage | "ALL")}>
            <option value="ALL">All stages</option>
            {STAGES.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </label>
        <p className="text-sm text-ink-soft" role="status" aria-live="polite">
          {cases ? <>{visible.length} of {cases.length} matters{attention > 0 ? <> · <span className="font-medium text-haldi">{attention} items need attention</span></> : null}</> : error ? null : "Loading matters"}
        </p>
      </div>

      <section aria-label="Matters" className="mt-4 overflow-hidden rounded-lg border border-line bg-cream">
        {error ? (
          <div role="alert" className="bg-cream p-6 text-sm text-sindoor">
            Could not load the cause list: {error}{" "}
            <Button variant="link" onClick={() => void load()}>Try again</Button>
          </div>
        ) : !cases ? (
          <div className="space-y-px bg-cream" aria-busy="true">
            {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[4.5rem] rounded-none" />)}
          </div>
        ) : visible.length === 0 ? (
          <EmptyState
            title={cases.length === 0 ? "No cases yet" : "No case matches"}
            description={cases.length === 0 ? "Start a case and upload the file. Every page is read and filed for you." : "Clear the search or choose another stage."}
            action={cases.length === 0 ? <Button onClick={() => setNewCaseOpen(true)}>New case</Button> : undefined}
          />
        ) : (
          <ol className="m-0 list-none p-0">
            {visible.map((c) => (
              <li key={c.case_id}><CaseCard summary={c} /></li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

export default CauseList;
