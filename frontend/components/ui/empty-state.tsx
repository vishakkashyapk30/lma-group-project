// EmptyState: what is missing, what to do next. A faint lattice sits behind it, nothing more.
import type { ReactElement, ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface EmptyStateProps {
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ title, description, action, className }: EmptyStateProps): ReactElement {
  return (
    <div className={cn("relative isolate overflow-hidden px-6 py-12 text-center", className)}>
      <div aria-hidden className="bg-jaali jaali-fade-b absolute inset-0 -z-10 opacity-60" />
      <h2 className="font-display text-lg font-semibold text-ink">{title}</h2>
      {description ? <p className="mx-auto mt-1 max-w-sm text-sm text-ink-soft">{description}</p> : null}
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </div>
  );
}
