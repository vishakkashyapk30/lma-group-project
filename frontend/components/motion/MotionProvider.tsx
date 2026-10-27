"use client";
// The motion library, used where it is the cheapest correct tool: enter and exit of elements that come and go
// (AnimatePresence), with short time-based transitions. `m` components render at once and animate once the features
// arrive. Follows the app's reduced-motion switch (system or in-app), not only the system setting.
import { AnimatePresence, LazyMotion, m, MotionConfig } from "motion/react";
import type { ReactElement, ReactNode } from "react";
import { useReducedMotion } from "@/lib/useReducedMotion";

const loadFeatures = () => import("./features").then((r) => r.default);

export function MotionProvider({ children }: { children: ReactNode }): ReactElement {
  const reduced = useReducedMotion();
  return (
    <LazyMotion features={loadFeatures} strict>
      <MotionConfig reducedMotion={reduced ? "always" : "never"}>{children}</MotionConfig>
    </LazyMotion>
  );
}

/** Time-based presence (DESIGN.md: 150 to 300 ms, the spring curve sampled as a cubic). */
export const PRESENCE = { duration: 0.22, ease: [0.2, 0, 0, 1] as [number, number, number, number] };

/**
 * The presence transition, or none under reduced motion (the library's own reduced mode still fades opacity, and our
 * rule is an instant change). `tr(delay)` for a staggered item.
 */
export function usePresenceTransition(): (delay?: number) => { duration: number; ease?: [number, number, number, number]; delay?: number } {
  const reduced = useReducedMotion();
  return (delay = 0) => (reduced ? { duration: 0 } : { ...PRESENCE, delay });
}

export { AnimatePresence, m };
