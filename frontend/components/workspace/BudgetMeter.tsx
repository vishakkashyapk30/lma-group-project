"use client";
// Budget meter (plan §6.2): tokens spent against the case budget (150K) and store calls made, with the per-factor limit
// (8 calls) and any BUDGET_HIT where Sutradhar stopped and reported what was missing. Never colour alone.
import { Gauge } from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactElement } from "react";
import { STORES, STORE_LIST } from "@/lib/stores";
import { formatNumberIN } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";

export const TOKEN_BUDGET = 150_000;
export const STORE_CALLS_PER_FACTOR = 8;

export interface BudgetMeterProps {
  caseId: string;
  className?: string;
  /** "popover": a compact button that opens the breakdown (header); "panel": the breakdown inline (trace drawer). */
  variant?: "popover" | "panel";
}

function tone(ratio: number): { bar: string; text: string; word: string } {
  if (ratio >= 1) return { bar: "bg-sindoor", text: "text-sindoor", word: "budget spent" };
  if (ratio >= 0.8) return { bar: "bg-haldi", text: "text-haldi", word: "nearly spent" };
  return { bar: "bg-neem", text: "text-neem", word: "within budget" };
}

function Meter({ label, value, max, valueText, ratio }: { label: string; value: number; max: number; valueText: string; ratio: number }): ReactElement {
  const t = tone(ratio);
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-2 text-xs">
        <span className="font-semibold text-ink">{label}</span>
        <span className="font-mono text-ink-soft">
          {valueText} <span className={cn("font-sans font-semibold", t.text)}>· {t.word}</span>
        </span>
      </div>
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={Math.min(value, max)}
        aria-valuetext={`${valueText}, ${t.word}`}
        className="h-2 overflow-hidden rounded-pill bg-line"
      >
        <div className={cn("h-full rounded-pill transition-[width] duration-base", t.bar)} style={{ width: `${Math.min(100, Math.round(ratio * 100))}%` }} />
      </div>
    </div>
  );
}

function BudgetBody({ className }: { className?: string }): ReactElement {
  const ws = useWorkspace();
  const budget = ws.data.budget;
  const cap = budget?.tokens_cap ?? TOKEN_BUDGET;
  const spent = budget?.tokens_spent ?? 0;
  const calls = budget?.store_calls ?? {};
  const totalCalls = Object.values(calls).reduce((a, b) => a + b, 0);
  const top = Math.max(1, ...Object.values(calls));
  const hits = ws.activity.budgetHits;

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <Meter label="Tokens" value={spent} max={cap} valueText={`${formatNumberIN(spent)} of ${formatNumberIN(cap)}`} ratio={cap ? spent / cap : 0} />
      <div>
        <div className="mb-1.5 flex items-baseline justify-between gap-2 text-xs">
          <span className="font-semibold text-ink">Store calls</span>
          <span className="font-mono text-ink-soft">{totalCalls} in total · limit {STORE_CALLS_PER_FACTOR} per factor</span>
        </div>
        <ul aria-label="Store calls by store" className="grid grid-cols-2 gap-x-3 gap-y-1">
          {STORE_LIST.filter((s) => (calls[s.id] ?? 0) > 0).map((s) => (
            <li key={s.id} className="flex items-center gap-2 text-2xs text-ink-soft">
              <span className="w-[5.5rem] shrink-0 truncate" title={`${s.id}: ${s.contents}`}>{STORES[s.id].label}</span>
              <span aria-hidden className="h-1.5 flex-1 rounded-pill bg-line">
                <span className="block h-full rounded-pill bg-maroon/70" style={{ width: `${Math.round(((calls[s.id] ?? 0) / top) * 100)}%` }} />
              </span>
              <span className="w-4 text-right font-mono text-ink">{calls[s.id]}</span>
            </li>
          ))}
        </ul>
        {totalCalls === 0 ? <p className="text-xs text-ink-muted">No store has been queried yet.</p> : null}
      </div>
      {hits.length > 0 ? (
        <div className="rounded-md border border-haldi/40 bg-haldi/[0.07] p-2 text-xs" role="note">
          <p className="mb-1 font-semibold text-haldi">Budget reached on this run</p>
          <ul className="space-y-0.5 text-ink">
            {hits.map((h) => {
              const missing = Array.isArray(h.outputs.missing) ? (h.outputs.missing as unknown[]).join(", ") : null;
              return (
                <li key={h.event_id}>
                  {typeof h.inputs.factor === "string" ? h.inputs.factor.replace(/_/g, " ") : "A factor"}: {String(h.outputs.store_calls ?? "?")} of{" "}
                  {String(h.outputs.limit ?? STORE_CALLS_PER_FACTOR)} calls used
                  {missing ? `; reported missing: ${missing}` : ""}.
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

export function BudgetMeter({ className, variant = "popover" }: BudgetMeterProps): ReactElement {
  const ws = useWorkspace();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (variant === "panel") {
    return (
      <section aria-label="Budget" className={className}>
        <BudgetBody />
      </section>
    );
  }

  const budget = ws.data.budget;
  const cap = budget?.tokens_cap ?? TOKEN_BUDGET;
  const spent = budget?.tokens_spent ?? 0;
  const ratio = cap ? spent / cap : 0;
  const t = tone(ratio);
  return (
    <div ref={rootRef} className={cn("relative", className)}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className="flex h-9 items-center gap-2 rounded-md border border-line-strong/60 bg-cream px-2.5 text-xs text-ink hover:border-maroon/60"
      >
        <Gauge aria-hidden className="size-4 text-maroon" />
        <span className="font-semibold">Budget</span>
        <span aria-hidden className="hidden h-1.5 w-14 overflow-hidden rounded-pill bg-line sm:block">
          <span className={cn("block h-full rounded-pill", t.bar)} style={{ width: `${Math.min(100, Math.round(ratio * 100))}%` }} />
        </span>
        <span className="font-mono text-ink-soft">{formatNumberIN(Math.round(spent / 1000))}K / {formatNumberIN(Math.round(cap / 1000))}K</span>
        <span className="sr-only">tokens, {t.word}. Open the breakdown.</span>
      </button>
      {open ? (
        <div id={panelId} className="absolute right-0 top-full z-drawer mt-2 w-[min(22rem,calc(100vw-2rem))] rounded-lg border border-gold/50 bg-cream p-4 shadow-lg">
          <p className="mb-3 font-display text-sm font-semibold text-maroon">What this case has spent</p>
          <BudgetBody />
        </div>
      ) : null}
    </div>
  );
}

export default BudgetMeter;
