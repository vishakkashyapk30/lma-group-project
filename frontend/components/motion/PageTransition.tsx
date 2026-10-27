"use client";
// Route transitions (DESIGN.md "Route transitions"): the page content crossfades with a 6 px rise in at most 250 ms; the
// sidebar, the top bar and the case stepper do not move (the document root is not part of the transition, see
// styles/transitions.css). Uses React's <ViewTransition> (Next's experimental.viewTransition); where the browser has no
// View Transitions API, or the runtime does not export the component, pages swap instantly as before.
import * as React from "react";
import type { ReactElement, ReactNode } from "react";

type VTProps = { children: ReactNode; name?: string; enter?: string; exit?: string; update?: string; share?: string; default?: string };

const runtime = React as unknown as Record<string, unknown>;
/** React's ViewTransition (stable or unstable_ export), or a plain fragment when the runtime has none. */
export const ViewTransition: (p: VTProps) => ReactElement = ((runtime.ViewTransition ?? runtime.unstable_ViewTransition) as ((p: VTProps) => ReactElement) | undefined) ??
  (({ children }: VTProps) => <>{children}</>);

/** True when route transitions can run here. */
export const HAS_VIEW_TRANSITION = Boolean(runtime.ViewTransition ?? runtime.unstable_ViewTransition);

/** Wrap a route's content; `routeKey` (the pathname) makes a navigation an exit of the old page and an enter of the new. */
export function PageTransition({ routeKey, children }: { routeKey: string; children: ReactNode }): ReactElement {
  return (
    <ViewTransition key={routeKey} enter="vt-page-in" exit="vt-page-out" default="none">
      <div>{children}</div>
    </ViewTransition>
  );
}

/** A shared element: the same `name` on two routes morphs one into the other during a navigation. */
export function Shared({ name, children }: { name: string; children: ReactNode }): ReactElement {
  return (
    <ViewTransition name={name} share="vt-morph" default="none">
      {children}
    </ViewTransition>
  );
}
