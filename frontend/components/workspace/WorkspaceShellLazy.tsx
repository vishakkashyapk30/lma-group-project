"use client";
// The workspace is entirely client state (provider, event stream, panes), so it renders in the browser only: its buttons then
// exist only once React has hydrated, and a click can never land on markup that has no handlers yet.
import dynamic from "next/dynamic";
import type { ReactElement } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import type { WorkspaceShellProps } from "./WorkspaceShell";

const WorkspaceShell = dynamic(() => import("./WorkspaceShell"), {
  ssr: false,
  loading: () => (
    <div role="status" aria-label="Opening the case" className="mx-auto flex max-w-[1800px] flex-col gap-3 p-6">
      <Skeleton className="h-10 w-72" />
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-[60dvh] w-full" />
    </div>
  ),
});

export function WorkspaceShellLazy(props: WorkspaceShellProps): ReactElement {
  return <WorkspaceShell {...props} />;
}

export default WorkspaceShellLazy;
