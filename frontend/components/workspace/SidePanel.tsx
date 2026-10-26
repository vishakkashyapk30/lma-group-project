"use client";
// The one panel on the right: the source page, or the chat. On a wide screen it sits beside the reading column; on a narrow
// one it is a full-screen sheet. Opening one closes the other, so there are never more than two columns.
import { X } from "lucide-react";
import { useEffect, useRef, type ReactElement, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
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

export function SidePanel({ title, onClose, children, testId, className }: SidePanelProps): ReactElement {
  const closeRef = useRef<HTMLButtonElement>(null);
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
      aria-label={title}
      data-testid={testId}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.preventDefault(); // handled here; the sheet-mode document listener skips prevented events
          onClose();
        }
      }}
      className={cn(
        "fixed inset-0 z-drawer flex min-h-0 flex-col bg-cream animate-slide-in-right",
        "lg:static lg:inset-auto lg:z-auto lg:w-[28rem] lg:shrink-0 lg:animate-none lg:border-l lg:border-line xl:w-[32rem]",
        className,
      )}
    >
      <header className="flex h-12 shrink-0 items-center justify-between gap-2 border-b border-line pl-4 pr-2">
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
