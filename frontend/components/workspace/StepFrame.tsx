"use client";
// The frame every step shares: a title, one sentence of intent, what is running, the step's content, and one primary button
// pinned to the foot of the reading column.
import { ArrowRight } from "lucide-react";
import type { ReactElement, ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ProgressLine } from "./ProgressLine";

export interface StepFrameProps {
  title: string;
  /** One short sentence under the title. */
  intro?: ReactNode;
  /** Things beside the title (print, for example). */
  actions?: ReactNode;
  children: ReactNode;
  /** The step's primary button; omit it while there is nothing to continue to. */
  footer?: ReactNode;
  className?: string;
}

export function StepFrame({ title, intro, actions, children, footer, className }: StepFrameProps): ReactElement {
  return (
    <section aria-labelledby="step-title" className={cn("mx-auto w-full max-w-[48rem] px-5 pt-8 sm:px-8", !footer && "pb-16", className)}>
      <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <h2 id="step-title" tabIndex={-1} className="font-display text-3xl font-semibold leading-tight text-ink outline-none">
            {title}
          </h2>
          {intro ? <p className="mt-1.5 max-w-prose text-ink-soft">{intro}</p> : null}
        </div>
        {actions ? <div data-print-hide className="flex shrink-0 gap-2">{actions}</div> : null}
      </header>
      <div className="mt-6 flex flex-col gap-8">
        <ProgressLine />
        {children}
      </div>
      {footer}
    </section>
  );
}

export interface StepFooterProps {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  busy?: boolean;
  /** Why the button is disabled, or a line to read before pressing it. */
  hint?: ReactNode;
  testId?: string;
  /** A quieter button beside the primary one. */
  secondary?: ReactNode;
  /** Draw the arrow (a button that moves to the next step). */
  next?: boolean;
}

export function StepFooter({ label, onClick, disabled, busy, hint, testId, secondary, next = true }: StepFooterProps): ReactElement {
  return (
    <div data-print-hide data-step-footer className="sticky bottom-0 z-raised -mx-5 mt-12 border-t border-line-strong/50 bg-parchment px-5 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:-mx-8 sm:px-8">
      <div className="flex flex-wrap items-center justify-end gap-x-4 gap-y-2">
        {hint ? <p id="step-hint" className="mr-auto min-w-0 text-sm text-ink-soft">{hint}</p> : null}
        {secondary}
        <Button data-testid={testId} size="lg" onClick={onClick} disabled={disabled || busy} aria-describedby={hint && disabled ? "step-hint" : undefined}>
          {label}
          {next ? <ArrowRight aria-hidden /> : null}
        </Button>
      </div>
    </div>
  );
}
