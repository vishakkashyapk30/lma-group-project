"use client";
// Stepper: a horizontal list of steps with a state each (done, current, open, locked), joined by hairlines.
// Presentation and arrow-key movement only; the caller decides what a click does.
import { Check, Lock } from "lucide-react";
import { Children, Fragment, useRef, type KeyboardEvent, type ReactElement, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export type StepState = "done" | "current" | "open" | "locked";

export interface StepperProps {
  label: string;
  children: ReactNode;
  className?: string;
}

/** The list. Left/Right/Home/End move focus between items marked `data-stepper-item`. */
export function Stepper({ label, children, className }: StepperProps): ReactElement {
  const ref = useRef<HTMLOListElement>(null);
  const onKeyDown = (e: KeyboardEvent<HTMLOListElement>) => {
    if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(e.key)) return;
    const items = Array.from(ref.current?.querySelectorAll<HTMLElement>("[data-stepper-item]") ?? []);
    const at = items.indexOf(document.activeElement as HTMLElement);
    if (at < 0) return;
    e.preventDefault();
    const to = e.key === "Home" ? 0 : e.key === "End" ? items.length - 1 : (at + (e.key === "ArrowRight" ? 1 : -1) + items.length) % items.length;
    items[to]?.focus();
  };
  const kids = Children.toArray(children);
  return (
    <ol ref={ref} aria-label={label} onKeyDown={onKeyDown} className={cn("flex items-center overflow-x-auto", className)}>
      {kids.map((k, i) => (
        <Fragment key={i}>
          {i > 0 ? <li aria-hidden className="mx-1 h-px w-3 shrink-0 bg-line-strong/50 lg:w-5" /> : null}
          {k}
        </Fragment>
      ))}
    </ol>
  );
}

const WORD: Record<StepState, string> = { done: "Done", current: "In progress", open: "Open", locked: "Locked" };

export interface StepIndicatorProps {
  state: StepState;
  className?: string;
}

/** A 16 px mark: check when done, filled ring when current, empty ring when open, lock when locked. */
export function StepIndicator({ state, className }: StepIndicatorProps): ReactElement {
  const base = "grid size-4 shrink-0 place-items-center rounded-full";
  if (state === "done") return <span aria-hidden className={cn(base, "bg-neem text-cream", className)}><Check className="size-2.5" strokeWidth={3.2} /></span>;
  if (state === "current") return <span aria-hidden className={cn(base, "border-2 border-maroon", className)}><span className="size-1.5 rounded-full bg-maroon" /></span>;
  if (state === "locked") return <span aria-hidden className={cn(base, "text-ink-muted", className)}><Lock className="size-3.5" /></span>;
  return <span aria-hidden className={cn(base, "border-2 border-line-strong", className)} />;
}

export interface StepProps {
  label: string;
  state: StepState;
  viewed?: boolean;
  onClick?: () => void;
  title?: string;
  testId?: string;
  describedBy?: string;
  /** Visually hidden prefix read by screen readers. */
  srPrefix?: string;
}

/** One step: indicator and label, with the state word shown in the label's title and read by assistive tech. */
export function Step({ label, state, viewed = false, onClick, title, testId, describedBy, srPrefix }: StepProps): ReactElement {
  const locked = state === "locked";
  return (
    <li className="shrink-0">
      <button
        type="button"
        data-stepper-item=""
        data-testid={testId}
        data-state={state}
        aria-current={viewed ? "step" : undefined}
        aria-disabled={locked || undefined}
        aria-describedby={describedBy}
        onClick={onClick}
        title={title}
        className={cn(
          "flex h-8 items-center gap-2 rounded-md px-2 text-sm transition-colors duration-fast",
          viewed ? "bg-maroon/[0.08] font-semibold text-maroon" : locked ? "cursor-not-allowed text-ink-muted" : "text-ink-soft hover:bg-ink/[0.05] hover:text-ink",
        )}
      >
        <StepIndicator state={state} />
        <span className="whitespace-nowrap">
          {srPrefix ? <span className="sr-only">{srPrefix} </span> : null}
          {label}
          <span className="sr-only">, {WORD[state]}</span>
        </span>
      </button>
    </li>
  );
}
