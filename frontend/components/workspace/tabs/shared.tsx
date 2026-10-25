"use client";
// Pieces shared by the workspace steps: focus-and-highlight for "jump to it" links, loading / empty / error states,
// inline notes, a quiet "changed" marker, source quotes (Hindi keeps the Devanagari original) and a print helper.
import { AlertTriangle, RefreshCw } from "lucide-react";
import { useEffect, useRef, useState, type ReactElement, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { WorkspaceTab } from "@/lib/stages";
import type { SourceRef } from "@/lib/types";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { cn } from "@/lib/utils";
import { useWorkspace, type Resource } from "@/lib/workspace";

/* ── Focus and highlight ─────────────────────────────────────────────────────────────────────────────────────────── */

/** Stable element id of an item in a step (a field name, ground id, objection id, "issue-2"...). */
export function focusDomId(tab: WorkspaceTab, id: string): string {
  return `ws-${tab}-${id}`;
}

/** Class for an item that a "jump to it" link just focused: a ring plus a tint, so it is not colour alone. */
export function focusClass(focusedId: string | null, id: string): string {
  return focusedId === id ? "ring-2 ring-maroon ring-offset-2 ring-offset-parchment bg-maroon/[0.04]" : "";
}

/** Last focus request each section acted on, kept outside the component so remounting does not replay an old link. */
const handledNonce: Partial<Record<WorkspaceTab, number>> = {};

export interface FocusedItem {
  id: string;
  intent?: "edit";
}

/**
 * Scrolls to and highlights the item a "jump to it" link (focusTarget) points at in this section. Items carry
 * `id={focusDomId(tab, id)}` and `tabIndex={-1}`. Call it with `ready` true once the data is on screen. Returns the id that
 * was just focused (for the highlight) and what the link asked for.
 */
export function useFocusItem(tab: WorkspaceTab, ready: boolean): FocusedItem | null {
  const { focusTarget } = useWorkspace();
  const reduced = useReducedMotion();
  const [focused, setFocused] = useState<FocusedItem | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!ready || !focusTarget || focusTarget.tab !== tab || handledNonce[tab] === focusTarget.nonce) return;
    handledNonce[tab] = focusTarget.nonce;
    const { id, intent } = focusTarget;
    setFocused({ id, intent });
    const frame = requestAnimationFrame(() => {
      const el = document.getElementById(focusDomId(tab, id));
      if (!el) return;
      el.scrollIntoView({ block: "center", behavior: reduced ? "auto" : "smooth" });
      el.focus({ preventScroll: true });
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setFocused(null), 3200);
    });
    return () => cancelAnimationFrame(frame);
  }, [ready, focusTarget, tab, reduced]);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  return focused;
}

/* ── States ──────────────────────────────────────────────────────────────────────────────────────────────────────── */

export interface StateProps {
  resource: Resource;
  noun: string;
  loading: boolean;
  error: string | undefined;
  hasData: boolean;
  onRetry: () => void;
  emptyTitle: string;
  emptyBody: ReactNode;
  emptyAction?: ReactNode;
}

/** The loading, error or empty view for a step's content, or null when there is data to show. */
export function stepState(p: StateProps): ReactElement | null {
  if (p.hasData) return null;
  if (p.loading) {
    return (
      <div role="status" className="flex flex-col gap-4">
        <span className="sr-only">Loading {p.noun}</span>
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }
  if (p.error) {
    return (
      <div role="alert" className="flex flex-col items-start gap-3 border-l-2 border-sindoor pl-4">
        <p className="flex items-center gap-2 font-medium text-sindoor">
          <AlertTriangle aria-hidden className="size-4" /> The {p.noun} could not be loaded.
        </p>
        <p className="text-sm text-ink">{p.error}</p>
        <Button variant="secondary" size="sm" onClick={p.onRetry}>
          <RefreshCw aria-hidden /> Try again
        </Button>
      </div>
    );
  }
  return (
    <div className="flex flex-col items-start gap-2 border-y border-line py-8">
      <h3 className="font-display text-lg font-semibold text-ink">{p.emptyTitle}</h3>
      <p className="max-w-prose text-sm text-ink-soft">{p.emptyBody}</p>
      {p.emptyAction ? <div className="mt-2">{p.emptyAction}</div> : null}
    </div>
  );
}

/** A section heading inside a step. */
export function SectionTitle({ children, id, aside }: { children: ReactNode; id?: string; aside?: ReactNode }): ReactElement {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <h3 id={id} className="font-display text-xl font-semibold text-ink">{children}</h3>
      {aside}
    </div>
  );
}

/** An inline error or note under a control. */
export function InlineNote({ tone = "error", children, id }: { tone?: "error" | "info"; children: ReactNode; id?: string }): ReactElement {
  return (
    <p id={id} role={tone === "error" ? "alert" : "status"} className={cn("text-sm", tone === "error" ? "font-medium text-sindoor" : "text-ink-soft")}>
      {children}
    </p>
  );
}

/** Marks a value that changed since the last confirmation: icon and words, never colour alone. */
export function ChangedTag({ children = "Changed since you confirmed" }: { children?: ReactNode }): ReactElement {
  return (
    <span data-testid="changed-marker" className="inline-flex items-center gap-1 text-xs font-medium text-haldi">
      <RefreshCw aria-hidden className="size-3" strokeWidth={2.4} />
      {children}
    </span>
  );
}

/* ── Sources ─────────────────────────────────────────────────────────────────────────────────────────────────────── */

/**
 * A quote from the record. A Hindi quote shows the Devanagari original with the English beside it where there is room (below
 * it on narrow screens), as the plan asks (§4.5).
 */
export function SourceQuote({ source, className }: { source: SourceRef | null | undefined; className?: string }): ReactElement | null {
  if (!source?.quote) return null;
  const hindi = (source.lang ?? "").toLowerCase() === "hi";
  const both = hindi && Boolean(source.quote_en);
  return (
    <figure className={cn("m-0", className)}>
      <blockquote className={cn("m-0 grid gap-x-5 gap-y-3", both && "xl:grid-cols-2")}>
        <p lang={hindi ? "hi" : undefined} className={cn("border-l-2 border-line-strong pl-3 text-ink", hindi ? "hindi-body text-base" : "doc-text text-base italic")}>
          {source.quote}
        </p>
        {both ? (
          <p lang="en" className="border-l-2 border-line pl-3 text-sm text-ink-soft">
            {source.quote_en}
          </p>
        ) : null}
      </blockquote>
    </figure>
  );
}

/* ── Printing ────────────────────────────────────────────────────────────────────────────────────────────────────── */

/** Prints one element on its own (the workspace around it stays out of the page) by copying it, with the page's styles, into a hidden frame. */
export function printElement(el: HTMLElement, title: string): void {
  const iframe = document.createElement("iframe");
  iframe.setAttribute("aria-hidden", "true");
  iframe.tabIndex = -1;
  iframe.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;";
  document.body.appendChild(iframe);
  const doc = iframe.contentDocument;
  const win = iframe.contentWindow;
  if (!doc || !win) {
    iframe.remove();
    window.print();
    return;
  }
  const styles = Array.from(document.querySelectorAll('link[rel="stylesheet"], style')).map((n) => n.outerHTML).join("");
  const safeTitle = title.replace(/[<>&]/g, "");
  doc.open();
  doc.write(
    `<!doctype html><html lang="en" class="${document.documentElement.className}"><head><meta charset="utf-8"><title>${safeTitle}</title>${styles}` +
      `<style>body{background:#fff;margin:0;padding:16px}</style></head><body>${el.outerHTML}</body></html>`,
  );
  doc.close();
  let printed = false;
  const run = () => {
    if (printed) return;
    printed = true;
    win.focus();
    win.print();
    setTimeout(() => iframe.remove(), 1500);
  };
  iframe.onload = run;
  setTimeout(run, 900);
}
