"use client";
// "Details" (plan §13.1, §13.4, §6.3): a side drawer, closed by default, with everything that is not the lawyer's task: the raw
// statuses and ids of the record, the live agent-trace graph (React Flow, dynamic, ssr: false), the current RetrievalPlan steps and
// each slot's state (FILLED, WEAK, MISSING), the budget and the raw event log. The graph is a picture of the same event stream
// that the log lists in text, so nothing is graph-only.
import * as DialogPrimitive from "@radix-ui/react-dialog";
import dynamic from "next/dynamic";
import { X } from "lucide-react";
import { useMemo, useState, type ReactElement } from "react";
import { StatusBadge } from "@/components/common/StatusBadge";
import { isAgentName } from "@/lib/agents";
import { dossierEntries } from "@/lib/fields";
import { formatClock, humanize } from "@/lib/format";
import { FACTOR_LABELS } from "@/lib/labels";
import { MOCK_CASE_ID, MOCK_RETRIEVAL_PLANS } from "@/lib/mock/case0007";
import { parseSlotAssessment } from "@/lib/status";
import { toolLabel } from "@/lib/stores";
import type { AgentEvent, BudgetLeft, Factor, PlanStep } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";
import { BudgetMeter } from "./BudgetMeter";

export interface TraceDrawerProps {
  caseId: string;
  open: boolean;
  onClose: () => void;
  className?: string;
}

const TraceGraph = dynamic(() => import("./TraceGraph"), {
  ssr: false,
  loading: () => <div className="grid h-full place-items-center text-sm text-ink-soft">Loading the trace graph…</div>,
});

interface PlanView {
  key: string;
  factor: string;
  round: number;
  steps: PlanStep[];
  assessment: Record<string, string>;
  next?: string | null;
  budget_left?: BudgetLeft;
}

function factorLabel(factor: string): string {
  return FACTOR_LABELS[factor as Factor] ?? humanize(factor);
}

/** Plans reconstructed from the event stream: one per factor, steps from the TOOL_CALLs, slot states from the TOOL_RESULTs. */
function derivePlans(events: readonly AgentEvent[]): PlanView[] {
  const byFactor = new Map<string, PlanView>();
  const get = (factor: string): PlanView => {
    let p = byFactor.get(factor);
    if (!p) {
      p = { key: factor, factor, round: 1, steps: [], assessment: {} };
      byFactor.set(factor, p);
    }
    return p;
  };
  for (const e of events) {
    const factor = typeof e.inputs?.factor === "string" ? e.inputs.factor : typeof e.outputs?.factor === "string" ? e.outputs.factor : null;
    if (!factor) continue;
    const plan = get(factor);
    if (e.kind === "TOOL_CALL" && e.tool) {
      const args: Record<string, unknown> = { ...e.inputs };
      const slot = args.slot;
      delete args.slot;
      delete args.store;
      delete args.factor;
      plan.steps.push({ slot: typeof slot === "string" ? slot : e.tool, tool: e.tool, args });
    } else if (e.kind === "TOOL_RESULT") {
      const slot = typeof e.outputs.slot === "string" ? e.outputs.slot : null;
      if (slot && typeof e.outputs.assessment === "string") plan.assessment[slot] = e.outputs.assessment;
    } else if (e.kind === "AGENT_MESSAGE" && typeof e.outputs.round === "number") {
      plan.round = Math.max(plan.round, e.outputs.round);
    } else if (e.kind === "BUDGET_HIT") {
      plan.next = "Budget spent: Sutradhar stops and reports what is still missing.";
    }
  }
  return Array.from(byFactor.values()).filter((p) => p.steps.length > 0);
}

function argSummary(args: Record<string, unknown>): string {
  const parts = Object.entries(args)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .slice(0, 3)
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : typeof v === "object" ? "…" : String(v)}`);
  return parts.join(" · ");
}

export function TraceDrawer({ caseId, open, onClose, className }: TraceDrawerProps): ReactElement {
  const ws = useWorkspace();
  const [picked, setPicked] = useState<string | null>(null);

  const plans: PlanView[] = useMemo(() => {
    if (ws.mode === "demo" && caseId === MOCK_CASE_ID) {
      return MOCK_RETRIEVAL_PLANS.map((p, i) => ({ ...p, key: `${p.factor}-${p.round}-${i}` }));
    }
    return derivePlans(ws.events);
  }, [ws.mode, caseId, ws.events]);

  const plan = plans.find((p) => p.key === picked) ?? plans[plans.length - 1] ?? null;
  const slots = plan ? Array.from(new Set([...plan.steps.map((s) => s.slot), ...Object.keys(plan.assessment)])) : [];
  const recent = ws.events.slice(-30).reverse();
  const sutradharCalls = ws.events.slice(ws.activity.runStart).filter((e) => e.kind === "TOOL_CALL" && String(e.actor).toUpperCase() === "SUTRADHAR");
  const calls = ws.events.slice(ws.activity.runStart).filter((e) => e.kind === "TOOL_CALL").length;

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(o) => !o && onClose()} modal={false}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Content
          onInteractOutside={(e) => e.preventDefault()}
          data-testid="trace-drawer"
          aria-describedby="trace-desc"
          className={cn(
            "fixed bottom-0 right-0 top-[var(--nav-h)] z-drawer flex w-[min(100vw,36rem)] flex-col border-l border-line bg-cream shadow-lg",
            "data-[state=open]:animate-slide-in-right data-[state=closed]:animate-slide-out-right",
            className,
          )}
        >
          <header className="flex items-start gap-3 border-b border-line px-4 py-3">
            <div className="min-w-0 flex-1">
              <DialogPrimitive.Title className="font-display text-lg font-semibold text-ink">Details</DialogPrimitive.Title>
              <DialogPrimitive.Description id="trace-desc" className="text-sm text-ink-soft">
                How this case was worked out: the record, the lookups made, the budget and the event log.
              </DialogPrimitive.Description>
              <p className="mt-1 text-sm text-ink-soft">
                {ws.streamStatus === "open" ? "Receiving events" : ws.streamStatus === "reconnecting" ? "Reconnecting to the event stream" : `Event stream ${ws.streamStatus}`}
                {ws.mode === "demo" ? " (sample data)" : ""}, {calls} call{calls === 1 ? "" : "s"} in this run
              </p>
            </div>
            <DialogPrimitive.Close className="grid size-8 shrink-0 place-items-center rounded-md text-ink-soft hover:bg-ink/[0.06] hover:text-ink">
              <X aria-hidden className="size-4" />
              <span className="sr-only">Close details</span>
            </DialogPrimitive.Close>
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4">
            <section aria-labelledby="trace-record-title">
              <h3 id="trace-record-title" className="mb-2 font-display text-base font-semibold text-ink">
                Record
              </h3>
              <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 text-xs">
                {(["GATE_1_DOSSIER", "GATE_2_EXPORT"] as const).map((g) => (
                  <div key={g} className="contents">
                    <dt className="font-mono text-ink-soft">{g}</dt>
                    <dd className="m-0 font-mono text-ink">{ws.gates.status[g] ? (ws.gates.status[g]?.open ? "OPEN" : "APPROVED") : "NOT_LOADED"}</dd>
                  </div>
                ))}
                {ws.data.dossier
                  ? dossierEntries(ws.data.dossier).map(([name, f]) => (
                      <div key={name} className="contents">
                        <dt className="font-mono text-ink-soft">{name}</dt>
                        <dd className="m-0 font-mono text-ink" data-status={f.status}>
                          {f.status}
                          {f.source?.route ? <span className="text-ink-muted"> {f.source.route}</span> : null}
                        </dd>
                      </div>
                    ))
                  : null}
              </dl>
              {ws.data.ingestion ? (
                <p className="mt-2 text-xs text-ink-muted">
                  Filed from {ws.data.ingestion.file}: {ws.data.ingestion.filed.timeline_events} dated events, {ws.data.ingestion.filed.parties} parties,{" "}
                  {ws.data.ingestion.filed.sections} sections, {ws.data.ingestion.filed.chunks} chunks.
                </p>
              ) : null}
            </section>

            <section aria-labelledby="trace-graph-title" className="mt-6">
              <h3 id="trace-graph-title" className="mb-1.5 font-display text-base font-semibold text-ink">
                Agents, tools and stores
              </h3>
              <div role="group" aria-label={`Trace graph of the current run: ${calls} calls. The event log below lists the same calls in text.`} className="h-72 overflow-hidden rounded-md border border-line bg-parchment">
                {open ? <TraceGraph events={ws.events} runStart={ws.activity.runStart} /> : null}
              </div>
              <p className="mt-1 text-2xs text-ink-muted">Edges light gold as calls happen: agent to tool to store. ×n counts repeated calls.</p>
            </section>

            <section aria-labelledby="trace-plan-title" className="mt-5">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <h3 id="trace-plan-title" className="font-display text-base font-semibold text-ink">
                  Retrieval plan
                </h3>
                {plans.length > 1 ? (
                  <>
                    <label htmlFor="trace-plan-pick" className="sr-only">
                      Choose a factor and round
                    </label>
                    <select
                      id="trace-plan-pick"
                      value={plan?.key ?? ""}
                      onChange={(e) => setPicked(e.target.value)}
                      className="ml-auto h-8 max-w-[16rem] rounded-md border border-line-strong/60 bg-cream px-2 text-xs text-ink"
                    >
                      {plans.map((p) => (
                        <option key={p.key} value={p.key}>
                          {factorLabel(p.factor)} · round {p.round}
                        </option>
                      ))}
                    </select>
                  </>
                ) : null}
              </div>
              {plan ? (
                <div className="rounded-md border border-line-strong/50 bg-cream">
                  <p className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-line px-3 py-2 text-xs text-ink-soft">
                    <span className="font-semibold text-ink">{factorLabel(plan.factor)}</span>
                    <span>round {plan.round}</span>
                    {plan.budget_left ? (
                      <span className="font-mono">
                        left: {plan.budget_left.store_calls} calls · {plan.budget_left.tokens.toLocaleString("en-IN")} tokens
                      </span>
                    ) : null}
                  </p>
                  <ol aria-label="Plan steps" className="divide-y divide-line">
                    {plan.steps.map((s, i) => {
                      const raw = plan.assessment[s.slot];
                      const parsed = raw ? parseSlotAssessment(raw) : null;
                      return (
                        <li key={`${s.slot}-${i}`} className="flex flex-wrap items-start gap-x-3 gap-y-1 px-3 py-2">
                          <span className="font-mono text-2xs text-ink-muted">{i + 1}</span>
                          <div className="min-w-0 flex-1">
                            <p className="text-sm">
                              <span className="font-semibold text-ink">{s.slot.replace(/_/g, " ")}</span>
                              <span className="text-ink-soft"> via </span>
                              <span className="font-mono text-xs text-ink" title={toolLabel(s.tool)}>{s.tool}</span>
                            </p>
                            <p className="truncate font-mono text-2xs text-ink-muted" title={JSON.stringify(s.args)}>{argSummary(s.args)}</p>
                          </div>
                          {parsed?.status ? (
                            <StatusBadge status={parsed.status} kind="slot" size="sm" detail={parsed.note ?? undefined} />
                          ) : (
                            <span className="text-2xs text-ink-muted">checking…</span>
                          )}
                        </li>
                      );
                    })}
                  </ol>
                  <div className="border-t border-line px-3 py-2">
                    <p className="mb-1 text-2xs font-semibold text-ink-soft">Slot states</p>
                    <ul className="flex flex-wrap gap-1.5" aria-label="Slot states">
                      {slots.map((slot) => {
                        const parsed = plan.assessment[slot] ? parseSlotAssessment(plan.assessment[slot]) : null;
                        return (
                          <li key={slot} className="inline-flex items-center gap-1.5 rounded-sm border border-line bg-parchment/60 py-0.5 pl-1.5 pr-0.5 text-2xs">
                            <span className="font-mono text-ink">{slot}</span>
                            {parsed?.status ? <StatusBadge status={parsed.status} kind="slot" size="sm" detail={parsed.note ?? undefined} /> : <span className="pr-1 text-ink-muted">pending</span>}
                          </li>
                        );
                      })}
                    </ul>
                    {plan.next ? (
                      <p className="mt-2 text-xs text-ink">
                        <span className="font-semibold text-ink">Next: </span>
                        {plan.next}
                      </p>
                    ) : null}
                  </div>
                </div>
              ) : (
                <p className="rounded-md border border-dashed border-line-strong/60 p-3 text-sm text-ink-soft">
                  No retrieval plan yet. Sutradhar plans when counsel asks for the brief, or when a chat question needs the stores.
                </p>
              )}
            </section>

            <section aria-labelledby="trace-calls-title" className="mt-5">
              <h3 id="trace-calls-title" className="mb-2 font-display text-base font-semibold text-ink">
                Sutradhar&apos;s tool calls <span className="font-sans text-xs font-normal text-ink-soft">({sutradharCalls.length})</span>
              </h3>
              {sutradharCalls.length === 0 ? (
                <p className="text-sm text-ink-soft">No tool calls yet in this run.</p>
              ) : (
                <ol aria-label="Tool calls in this run" className="divide-y divide-line rounded-md border border-line-strong/50 text-sm">
                  {sutradharCalls.map((e, i) => (
                    <li key={e.event_id} data-testid="trace-step" data-tool={e.tool ?? ""} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 px-3 py-2">
                      <span className="font-mono text-2xs text-ink-muted">{i + 1}</span>
                      <span className="font-mono text-xs font-semibold text-ink" title={e.tool ? toolLabel(e.tool) : undefined}>{e.tool}</span>
                      <span className="min-w-0 flex-1 truncate font-mono text-2xs text-ink-muted" title={JSON.stringify(e.inputs)}>{argSummary(e.inputs ?? {})}</span>
                      <time className="font-mono text-2xs text-ink-muted" dateTime={e.ts}>{formatClock(e.ts)}</time>
                    </li>
                  ))}
                </ol>
              )}
            </section>

            <section aria-labelledby="trace-budget-title" className="mt-5">
              <h3 id="trace-budget-title" className="mb-2 font-display text-base font-semibold text-ink">
                Budget
              </h3>
              <BudgetMeter caseId={caseId} />
            </section>

            <section aria-labelledby="trace-log-title" className="mt-5">
              <h3 id="trace-log-title" className="mb-2 font-display text-base font-semibold text-ink">
                Event log <span className="font-sans text-xs font-normal text-ink-soft">(latest {recent.length})</span>
              </h3>
              {recent.length === 0 ? (
                <p className="text-sm text-ink-soft">No events yet.</p>
              ) : (
                <ol className="divide-y divide-line rounded-md border border-line-strong/50 text-xs">
                  {recent.map((e) => (
                    <li key={e.event_id} className="flex flex-wrap items-baseline gap-x-2 px-2.5 py-1.5">
                      <time className="font-mono text-2xs text-ink-muted" dateTime={e.ts}>{formatClock(e.ts)}</time>
                      <span className="font-semibold text-ink">{isAgentName(String(e.actor).toUpperCase()) ? humanize(String(e.actor)) : String(e.actor)}</span>
                      <span className="font-mono text-2xs text-ink">{e.kind.toLowerCase()}</span>
                      {e.tool ? <span className="font-mono text-2xs text-ink-soft">{e.tool}</span> : null}
                      {typeof e.outputs?.text === "string" ? <span className="basis-full text-ink-soft">{e.outputs.text}</span> : null}
                    </li>
                  ))}
                </ol>
              )}
            </section>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

export default TraceDrawer;
