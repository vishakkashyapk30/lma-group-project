"use client";
// The one panel on the right: the source page, or the chat. On a wide screen it sits beside the reading column; on a narrow
// one it is a full-screen sheet. Opening one closes the other, so there are never more than two columns.
import { X } from "lucide-react";
import type { ReactElement, ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface SidePanelProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
  testId?: string;
  className?: string;
}

export function SidePanel({ title, onClose, children, testId, className }: SidePanelProps): ReactElement {
  return (
    <aside
      aria-label={title}
      data-testid={testId}
      onKeyDown={(e) => {
        if (e.key === "Escape") onClose();
      }}
      className={cn(
        "fixed inset-0 z-drawer flex min-h-0 flex-col bg-cream animate-slide-in-right",
        "lg:static lg:inset-auto lg:z-auto lg:w-[28rem] lg:shrink-0 lg:animate-none lg:border-l lg:border-line xl:w-[32rem]",
        className,
      )}
    >
      <header className="flex h-12 shrink-0 items-center justify-between gap-2 border-b border-line pl-4 pr-2">
        <h2 className="min-w-0 truncate font-display text-lg font-semibold text-ink">{title}</h2>
        <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label={`Close ${title.toLowerCase()}`}>
          <X aria-hidden />
        </Button>
      </header>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
    </aside>
  );
}

export default SidePanel;
