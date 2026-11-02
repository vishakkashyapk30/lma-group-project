// Route loading skeletons (app/*/loading.tsx). Each matches the page it stands in for (title block, the controls row, rows
// of the real height), so nothing shifts when the page arrives, and appears only after 150 ms so fast navigations show
// no flash (`.skeleton-delayed`, styles/transitions.css).
import type { ReactElement } from "react";
import { Skeleton } from "@/components/ui/skeleton";

function Header(): ReactElement {
  return (
    <div className="border-b border-line pb-4">
      <Skeleton className="h-[2.1rem] w-48" />
      <Skeleton className="mt-2 h-4 w-full max-w-[34rem]" />
    </div>
  );
}

export function PageSkeleton({ kind, label }: { kind: "list" | "board" | "library"; label: string }): ReactElement {
  return (
    <div role="status" aria-label={label} data-testid="page-skeleton" className="skeleton-delayed mx-auto max-w-content px-4 py-8 sm:px-6 sm:py-10">
      <Header />
      {kind === "list" ? (
        <>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Skeleton className="h-10 min-w-[14rem] flex-1" />
            <Skeleton className="h-9 w-56" />
            <Skeleton className="h-4 w-32" />
          </div>
          <div className="mt-4 overflow-hidden rounded-lg border border-line bg-cream">
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="border-b border-line px-4 py-3.5 last:border-b-0 sm:px-5">
                <Skeleton className="h-5 w-2/3" />
                <Skeleton className="mt-2 h-3.5 w-1/3" />
                <Skeleton className="mt-2 h-3.5 w-1/2" />
              </div>
            ))}
          </div>
        </>
      ) : kind === "board" ? (
        <>
          <Skeleton className="mt-6 h-[10.5rem] w-full rounded-lg" />
          <div className="mt-6 grid gap-3">
            {[0, 1, 2].map((i) => <Skeleton key={i} className="h-28 w-full rounded-lg" />)}
          </div>
        </>
      ) : (
        <>
          <div className="mt-5 flex gap-2 border-b border-line pb-2">
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-6 w-28" />
          </div>
          <Skeleton className="mt-5 h-10 w-full" />
          <div className="mt-4 grid gap-3">
            {[0, 1, 2].map((i) => <Skeleton key={i} className="h-24 w-full" />)}
          </div>
        </>
      )}
    </div>
  );
}
