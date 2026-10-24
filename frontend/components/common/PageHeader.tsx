// Page header for the app pages: a plain title, one line of description, optional actions. Hairline underneath.
import type { ReactElement, ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface PageHeaderProps {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export function PageHeader({ title, description, actions, className }: PageHeaderProps): ReactElement {
  return (
    <header className={cn("flex flex-wrap items-end justify-between gap-4 border-b border-line pb-4", className)}>
      <div className="min-w-0">
        <h1 className="font-display text-[1.75rem] font-semibold leading-tight">{title}</h1>
        {description ? <p className="mt-1 max-w-prose text-sm text-ink-soft">{description}</p> : null}
      </div>
      {actions}
    </header>
  );
}
