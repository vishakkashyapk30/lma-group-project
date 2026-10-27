"use client";
// The workspace is entirely client state (provider, event stream, panes), so it renders in the browser only: its buttons then
// exist only once React has hydrated, and a click can never land on markup that has no handlers yet.
import dynamic from "next/dynamic";
import type { ReactElement } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import type { WorkspaceShellProps } from "./WorkspaceShell";

const WorkspaceShell = dynamic(() => import("./WorkspaceShell"), {
  ssr: false,
  // Matches the real layout: the stepper row (3 rem, its own row below xl), then the step's centred 48 rem column.
  loading: () => (
    <div role="status" aria-label="Opening the case" data-testid="workspace-skeleton" className="skeleton-delayed flex h-[calc(100dvh-var(--nav-h))] min-h-[34rem] flex-col">
      <div className="flex flex-wrap items-center gap-x-3 border-b border-line px-3 sm:px-4">
        <div className="flex min-h-[var(--rail-h)] basis-full items-center gap-4 py-2 xl:basis-0 xl:flex-1">
          {[0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-5 w-24 shrink-0" />)}
        </div>
        <div className="ml-auto flex items-center gap-2 pb-2 xl:pb-0">
          <Skeleton className="h-8 w-16" />
          <Skeleton className="h-8 w-16" />
          <Skeleton className="h-8 w-16" />
        </div>
      </div>
      <div className="mx-auto w-full max-w-[48rem] px-5 pt-8 sm:px-8">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="mt-3 h-4 w-full max-w-prose" />
        <div className="mt-8 flex flex-col gap-3">
          {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      </div>
    </div>
  ),
});

export function WorkspaceShellLazy(props: WorkspaceShellProps): ReactElement {
  return <WorkspaceShell {...props} />;
}

export default WorkspaceShellLazy;
