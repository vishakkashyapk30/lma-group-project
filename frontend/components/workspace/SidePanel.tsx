"use client";
// The one panel on the right: the source page, or the chat. On a wide screen it sits beside the reading column; on a narrow
// one it is a full-screen sheet that rises from the bottom. Opening one closes the other, so there are never more than two
// columns. The header is a drag handle (DESIGN.md "Direct manipulation and springs"): pull the panel to the right, or the
// sheet down, to close it; pulled the other way it resists and springs back. The Close button and Escape do the same.
import { X } from "lucide-react";
import { useEffect, useRef, useSyncExternalStore, type ReactElement, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { ALLOWANCE, SPRINGS, useDragToClose } from "@/lib/motion";
import { cn } from "@/lib/utils";

export interface SidePanelProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
  testId?: string;
  className?: string;
}

/** Below the lg breakpoint the panel is a full-screen sheet (matches the lg: classes below). */
const SHEET_QUERY = "(max-width: 1023.98px)";

function subscribeSheet(cb: () => void): () => void {
  const mql = window.matchMedia?.(SHEET_QUERY);
  mql?.addEventListener?.("change", cb);
  return () => mql?.removeEventListener?.("change", cb);
}
const isSheet = () => Boolean(window.matchMedia?.(SHEET_QUERY).matches);

export function SidePanel({ title, onClose, children, testId, className }: SidePanelProps): ReactElement {
  const closeRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLElement>(null);
  const handleRef = useRef<HTMLElement>(null);
  const sheet = useSyncExternalStore(subscribeSheet, isSheet, () => false);

  useDragToClose(panelRef, handleRef, sheet
    ? { axis: "y", onClose, spring: SPRINGS.sheet, allowance: ALLOWANCE.sheet, fraction: 0.25, speed: 800 }
    : { axis: "x", onClose, spring: SPRINGS.panel, allowance: ALLOWANCE.panel, fraction: 0.5, speed: 500 });

  // As a full-screen sheet the panel covers the page: move focus into it, and let Escape close it from anywhere.
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia?.(SHEET_QUERY).matches) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !e.defaultPrevented && !document.querySelector("[role=dialog][data-state=open]")) onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <aside
      ref={panelRef}
      aria-label={title}
      data-testid={testId}
      data-panel-mode={sheet ? "sheet" : "panel"}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.preventDefault(); // handled here; the sheet-mode document listener skips prevented events
          onClose();
        }
      }}
      className={cn(
        "fixed inset-0 z-drawer flex min-h-0 flex-col bg-cream animate-slide-in-up will-change-transform",
        "lg:static lg:inset-auto lg:z-auto lg:w-[28rem] lg:shrink-0 lg:animate-none lg:border-l lg:border-line xl:w-[32rem]",
        className,
      )}
    >
      <header
        ref={handleRef}
        data-testid="panel-handle"
        title="Drag to close, or press Escape"
        className={cn(
          "relative flex h-12 shrink-0 cursor-grab select-none items-center justify-between gap-2 border-b border-line pl-4 pr-2 active:cursor-grabbing",
          sheet ? "touch-none" : "touch-pan-y",
        )}
      >
        {/* The grabber says the sheet can be pulled down; it is not a control (the Close button is). */}
        <span aria-hidden className="absolute left-1/2 top-1.5 h-1 w-9 -translate-x-1/2 rounded-sm bg-line-strong/50 lg:hidden" />
        <h2 className="min-w-0 truncate font-display text-lg font-semibold text-ink">{title}</h2>
        <Button ref={closeRef} variant="ghost" size="icon-sm" onClick={onClose} aria-label={`Close ${title.toLowerCase()}`}>
          <X aria-hidden />
        </Button>
      </header>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
    </aside>
  );
}

export default SidePanel;
