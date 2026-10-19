"use client";
// Pieces shared by the six workspace tabs: the tab frame and header, loading / empty / error states, focus-and-highlight
// for checklist links, source lines (Hindi quotes keep the Devanagari original), a change tag and a print helper.
import { AlertTriangle, FileQuestion, RefreshCw } from "lucide-react";
import { useEffect, useRef, useState, type ReactElement, type ReactNode } from "react";
import { AgentGlyph } from "@/components/common/AgentGlyph";
import { SourceChip } from "@/components/common/SourceChip";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { AGENTS } from "@/lib/agents";
import { langLabel } from "@/lib/labels";
import type { WorkspaceTab } from "@/lib/stages";
import type { AgentName, SourceRef } from "@/lib/types";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { cn } from "@/lib/utils";
import { useWorkspace, type Resource } from "@/lib/workspace";

/* ── Focus and highlight ─────────────────────────────────────────────────────────────────────────────────────────── */

/** Stable element id of an item in a tab (a field name, ground id, objection id, "issue-2"...). */
export function focusDomId(tab: WorkspaceTab, id: string): string {
  return `ws-${tab}-${id}`;
}

/** Class for an item that checklist links just focused: a ring plus a tint, so it is not colour alone. */
export function focusClass(focusedId: string | null, id: string): string {
  return focusedId === id ? "ring-2 ring-maroon ring-offset-2 ring-offset-cream bg-maroon/[0.04]" : "";
}

/** Last focus request each tab acted on, kept outside the component so remounting a tab does not replay an old link. */
const handledNonce: Partial<Record<WorkspaceTab, number>> = {};

/**
 * Scrolls to and highlights the item a checklist link (focusTarget) points at in this tab. Items carry
 * `id={focusDomId(tab, id)}` and `tabIndex={-1}`. Call it with `ready` true once the data is on screen.
 */
export function useFocusItem(tab: WorkspaceTab, ready: boolean): string | null {
  const { focusTarget } = useWorkspace();
  const reduced = useReducedMotion();
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!ready || !focusTarget || focusTarget.tab !== tab || handledNonce[tab] === focusTarget.nonce) return;
    handledNonce[tab] = focusTarget.nonce;
    const { id } = focusTarget;
    const frame = requestAnimationFrame(() => {
      const el = document.getElementById(focusDomId(tab, id));
      if (!el) return;
      el.scrollIntoView({ block: "center", behavior: reduced ? "auto" : "smooth" });
      el.focus({ preventScroll: true });
      setFocusedId(id);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setFocusedId(null), 3200);
    });
    return () => cancelAnimationFrame(frame);
  }, [ready, focusTarget, tab, reduced]);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  return focusedId;
}

/* ── Frame, header and states ────────────────────────────────────────────────────────────────────────────────────── */

export function TabShell({ label, children, className }: { label: string; children: ReactNode; className?: string }): ReactElement {
  return (
    <section aria-label={label} className={cn("mx-auto flex w-full max-w-3xl flex-col gap-5 px-4 py-5", className)}>
      {children}
    </section>
  );
}

export interface TabHeaderProps {
  agent: AgentName;
  title: string;
  description: ReactNode;
  /** The agent's signature animation, shown while the agent works. */
  signature?: ReactNode;
  actions?: ReactNode;
}

export function TabHeader({ agent, title, description, signature, actions }: TabHeaderProps): ReactElement {
  const meta = AGENTS[agent];
  return (
    <header className="flex flex-col gap-3 border-b border-line pb-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="eyebrow flex items-center gap-1.5">
            <AgentGlyph agent={agent} size={14} />
            <span>
              {meta.name} <span lang="hi" className="hindi-body normal-case tracking-normal">{meta.nameHi}</span> · {meta.subtitle}
            </span>
          </p>
          <h2 className="mt-1 font-display text-2xl font-semibold leading-tight text-maroon">{title}</h2>
          <p className="mt-1 max-w-prose text-sm text-ink-soft">{description}</p>
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2" data-print-hide>{actions}</div> : null}
      </div>
      {signature ? <div className="max-w-sm">{signature}</div> : null}
    </header>
  );
}

export function SectionTitle({ children, id, aside }: { children: ReactNode; id?: string; aside?: ReactNode }): ReactElement {
  return (
    <div className="flex items-end justify-between gap-3">
      <h3 id={id} className="font-display text-lg font-semibold text-maroon">{children}</h3>
      {aside}
    </div>
  );
}

export interface TabStateProps {
  tab: WorkspaceTab;
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

/** The loading, error or empty view for a tab, or null when the tab has data to show. */
export function tabState(p: TabStateProps): ReactElement | null {
  if (p.hasData) return null;
  if (p.loading) {
    return (
      <TabShell label={`${p.noun}, loading`}>
        <div role="status" className="flex flex-col gap-4">
          <span className="sr-only">Loading {p.noun}</span>
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-4 w-full" />
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      </TabShell>
    );
  }
  if (p.error) {
    return (
      <TabShell label={`${p.noun}, error`}>
        <div role="alert" className="flex flex-col items-start gap-3 rounded-lg border border-sindoor/50 bg-sindoor/[0.05] p-4">
          <p className="flex items-center gap-2 font-semibold text-sindoor">
            <AlertTriangle aria-hidden className="size-4" /> The {p.noun} could not be loaded.
          </p>
          <p className="text-sm text-ink">{p.error}</p>
          <Button variant="secondary" size="sm" onClick={p.onRetry}>
            <RefreshCw aria-hidden /> Try again
          </Button>
        </div>
      </TabShell>
    );
  }
  return (
    <TabShell label={`${p.noun}, empty`}>
      <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-line-strong/60 bg-parchment/60 px-6 py-10 text-center">
        <FileQuestion aria-hidden className="size-8 text-ink-muted" />
        <h2 className="font-display text-xl font-semibold text-maroon">{p.emptyTitle}</h2>
        <p className="max-w-prose text-sm text-ink-soft">{p.emptyBody}</p>
        {p.emptyAction}
      </div>
    </TabShell>
  );
}

/** An inline error or note under a control. */
export function InlineNote({ tone = "error", children, id }: { tone?: "error" | "info"; children: ReactNode; id?: string }): ReactElement {
  return (
    <p id={id} role={tone === "error" ? "alert" : "status"} className={cn("text-xs", tone === "error" ? "font-semibold text-sindoor" : "text-ink-soft")}>
      {children}
    </p>
  );
}

/** Marks a value that changed since the last approval: icon and words, never colour alone. */
export function ChangedTag({ children = "Changed since last approval" }: { children?: ReactNode }): ReactElement {
  return (
    <span data-testid="changed-marker" className="inline-flex items-center gap-1 rounded-pill border border-haldi/60 bg-haldi/[0.12] px-2 py-1 text-xs font-semibold leading-none text-ink">
      <RefreshCw aria-hidden className="size-3" strokeWidth={2.4} />
      {children}
    </span>
  );
}

/* ── Sources ─────────────────────────────────────────────────────────────────────────────────────────────────────── */

/** A quote from the record. Hindi quotes show the Devanagari original and the English underneath (plan §4.5). */
export function SourceQuote({ source, className }: { source: SourceRef | null | undefined; className?: string }): ReactElement | null {
  if (!source?.quote) return null;
  const hindi = (source.lang ?? "").toLowerCase() === "hi";
  return (
    <figure className={cn("border-l-2 border-gold/70 pl-3", className)}>
      <blockquote>
        <p lang={hindi ? "hi" : undefined} className={cn("text-sm text-ink", hindi ? "hindi-body text-base" : "italic")}>
          {source.quote}
        </p>
        {hindi && source.quote_en ? (
          <p lang="en" className="mt-1 text-xs italic text-ink-soft">
            <span className="not-italic font-semibold">English: </span>
            {source.quote_en}
          </p>
        ) : null}
      </blockquote>
    </figure>
  );
}

/** doc · page · route · language, with the chip that selects the source for the case-file viewer. */
export function SourceLine({ source, className }: { source: SourceRef | null | undefined; className?: string }): ReactElement {
  if (!source) {
    return <p className={cn("text-xs text-ink-muted", className)}>No court source for this value.</p>;
  }
  return (
    <div className={cn("flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-soft", className)}>
      <SourceChip source={source} />
      {source.tool ? <span className="cite">Computed by {source.tool}</span> : null}
      {source.chat ? <span className="cite">Counsel, chat {source.chat}</span> : null}
      {source.route ? (
        <span className="cite" title="How the page was read">
          route: {source.route}
        </span>
      ) : null}
      {source.lang ? <span title="Language of the source">{langLabel(source.lang)}</span> : null}
    </div>
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
