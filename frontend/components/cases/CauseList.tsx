"use client";
// Cause list: matters as numbered rows by stage with Rights Radar chips (urgent first) and items needing attention;
// New case (plan §13.5).
import { Plus, Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactElement } from "react";
import { useRouter } from "next/navigation";
import {
  Button, Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, Input, Skeleton,
} from "@/components/ui";
import { fieldClasses } from "@/components/ui/input";
import { createCase, listCases, onApiModeChange, getApiMode, type ApiMode } from "@/lib/api";
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
  const router = useRouter();
  const [cases, setCases] = useState<CaseSummaryWithActivity[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [stage, setStage] = useState<Stage | "ALL">("ALL");
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [mode, setMode] = useState<ApiMode>("demo");

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
    setMode(getApiMode());
    return onApiModeChange(setMode);
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

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      const created = await createCase(title.trim() || null);
      setOpen(false);
      setTitle("");
      router.push(`/case/${created.case_id}`);
    } catch (err) {
      setCreateError(errorMessage(err));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className={cn("mx-auto max-w-content px-4 py-8 sm:px-6 sm:py-10", className)}>
      <header className="flex flex-wrap items-end justify-between gap-4 border-b-2 border-maroon/70 pb-5">
        <div>
          <p className="font-sans text-xs font-semibold uppercase tracking-caps text-ink-soft">Matters before counsel</p>
          <h1 className="font-display text-4xl font-semibold text-maroon sm:text-5xl">Cause list</h1>
          <p className="mt-1 max-w-prose text-sm text-ink-soft">
            Every matter, with the most urgent possible entitlement first. These are things to check, never advice or a prediction.
          </p>
        </div>
        <Button onClick={() => setOpen(true)} size="lg"><Plus aria-hidden /> New case</Button>
      </header>

      <div className="mt-5 flex flex-wrap items-center gap-3">
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
        <label className="flex items-center gap-2 text-sm font-semibold text-ink-soft">
          Stage
          <select className={cn(fieldClasses, "h-10 w-auto min-w-[10rem]")} value={stage} onChange={(e) => setStage(e.target.value as Stage | "ALL")}>
            <option value="ALL">All stages</option>
            {STAGES.map((s) => <option key={s.id} value={s.id}>{s.numeral}. {s.label}</option>)}
          </select>
        </label>
        <p className="text-sm text-ink-soft" role="status" aria-live="polite">
          {cases ? <>{visible.length} of {cases.length} matters{attention > 0 ? <> · <strong className="text-haldi">{attention} items need attention</strong></> : null}</> : "Loading matters"}
        </p>
      </div>

      <section aria-label="Matters" className="mt-4 overflow-hidden rounded-lg border border-line shadow-sm">
        {error ? (
          <div role="alert" className="bg-cream p-6 text-sm text-sindoor">
            Could not load the cause list: {error}{" "}
            <Button variant="link" onClick={() => void load()}>Try again</Button>
          </div>
        ) : !cases ? (
          <div className="space-y-px bg-cream" aria-busy="true">
            {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24 rounded-none" />)}
          </div>
        ) : visible.length === 0 ? (
          <div className="bg-cream p-10 text-center">
            <p className="font-display text-xl text-maroon">{cases.length === 0 ? "No matters yet" : "No matter matches"}</p>
            <p className="mt-1 text-sm text-ink-soft">
              {cases.length === 0 ? "Start a case and upload the file; Munshi will read and file every page." : "Clear the search or choose another stage."}
            </p>
          </div>
        ) : (
          <ol className="m-0 list-none p-0">
            {visible.map((c, i) => (
              <li key={c.case_id}><CaseCard summary={c} index={i + 1} /></li>
            ))}
          </ol>
        )}
      </section>
      {mode === "demo" ? <p className="mt-3 text-xs text-ink-muted">Demo data: new cases are kept in this browser only.</p> : null}

      <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) setCreateError(null); }}>
        <DialogContent size="sm">
          <form onSubmit={onCreate}>
            <DialogHeader>
              <DialogTitle>New case</DialogTitle>
              <DialogDescription className="text-sm text-ink-soft">
                A title helps you find it later. Use initials or a short reference, not the client&apos;s full name.
              </DialogDescription>
            </DialogHeader>
            <DialogBody>
              <label htmlFor="new-case-title" className="mb-1 block text-sm font-semibold">Case title (optional)</label>
              <Input id="new-case-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. State v. R.K., bail application" autoFocus />
              {createError ? <p role="alert" className="mt-2 text-sm text-sindoor">{createError}</p> : null}
            </DialogBody>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={creating}>{creating ? "Creating" : "Create and open"}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default CauseList;
