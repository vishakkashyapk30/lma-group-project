"use client";
// "The case title carries over": when a case opens from a card (or from the landing page), its title moves from where
// it was clicked into the top bar's breadcrumb, so the user sees it is the same case. A measured FLIP: the source
// records its box before navigating (`startMorph`), the destination plays from that box to its own place on mount,
// 250 ms on the spring curve, transform only. Nothing happens under reduced motion, when the record is older than a
// second, or when the names do not match. Works with and without view transitions.
import { useLayoutEffect, useRef, type ReactElement, type ReactNode } from "react";
import { prefersReducedMotion } from "@/lib/useReducedMotion";

interface Pending {
  name: string;
  rect: DOMRect;
  fontSize: number;
  at: number;
}

let pending: Pending | null = null;

/** Remember where the element named `name` is now (call just before navigating). */
export function startMorph(name: string, el: Element | null): void {
  if (!el) return;
  pending = { name, rect: el.getBoundingClientRect(), fontSize: parseFloat(getComputedStyle(el).fontSize) || 16, at: performance.now() };
}

const EASE_SPRING = "linear(0, 0.114, 0.32, 0.515, 0.67, 0.782, 0.859, 0.911, 0.944, 0.965, 0.979, 0.987, 1)";

/** Wraps the destination; plays the move once when it mounts with a matching pending record. */
export function MorphTarget({ name, children, className }: { name: string; children: ReactNode; className?: string }): ReactElement {
  const ref = useRef<HTMLSpanElement>(null);
  useLayoutEffect(() => {
    const p = pending;
    const el = ref.current;
    if (!p || !el || p.name !== name) return;
    pending = null;
    if (performance.now() - p.at > 1000 || prefersReducedMotion() || typeof el.animate !== "function") return;
    const to = el.getBoundingClientRect();
    const toFont = parseFloat(getComputedStyle(el).fontSize) || 16;
    const s = p.fontSize / toFont;
    const dx = p.rect.left - to.left;
    const dy = p.rect.top + p.rect.height / 2 - (to.top + to.height / 2);
    el.dataset.morphing = "";
    const a = el.animate(
      [{ transform: `translate(${dx}px, ${dy}px) scale(${s})`, opacity: 0.6 }, { transform: "none", opacity: 1 }],
      { duration: 250, easing: EASE_SPRING },
    );
    a.onfinish = a.oncancel = () => delete el.dataset.morphing;
  }, [name]);
  return (
    <span ref={ref} data-morph={name} className={className} style={{ display: "inline-block", transformOrigin: "left center", maxWidth: "100%" }}>
      {children}
    </span>
  );
}
