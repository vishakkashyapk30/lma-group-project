"use client";
// Scene indicator (plan §13.3, Hugh James style): a row of dots with one lit. Each dot is a focusable button that jumps to
// its scene. Positions are read from the [data-scene] elements at the moment of the jump (pinned sections add spacers, so
// there are no fixed offsets). useActiveScene() derives the lit dot from those same elements.
import { useEffect, useState, type ReactElement } from "react";
import { cn } from "@/lib/utils";
import { registerMotion, scrollToTarget, ScrollTrigger } from "@/lib/motion/register";

export interface SceneIndicatorProps {
  total: number;
  active: number;
  className?: string;
  labels?: readonly string[];
  /** Override the default jump (scroll to the scene's [data-scene] element). */
  onSelect?: (index: number) => void;
}

export const SCENE_LABELS = [
  "Bail is the rule",
  "We, the People",
  "Arrest",
  "The wait",
  "The paper storm",
  "The argument",
  "Liberty",
] as const;

function sceneElement(index: number): HTMLElement | null {
  return document.querySelector<HTMLElement>(`[data-scene="${index}"]`);
}

/**
 * Scroll to a scene. A pinned scene lives inside a GSAP pin-spacer: aim at the spacer so the jump lands at the pin's start.
 * The scenes below the fold load lazily, so when the one asked for is not there yet the jump waits for it (up to 5 s).
 */
export function jumpToScene(index: number, waited = 0): void {
  if (index === 0) {
    scrollToTarget(0);
    return;
  }
  const el = sceneElement(index);
  if (!el) {
    if (waited < 5000) window.setTimeout(() => jumpToScene(index, waited + 100), 100);
    return;
  }
  const spacer = el.parentElement?.classList.contains("pin-spacer") ? el.parentElement : el;
  scrollToTarget(spacer, -56);
}

/** Index of the last scene whose top has passed the middle of the viewport. Reads live positions, no fixed offsets. */
export function useActiveScene(total: number, enabled = true): number {
  const [active, setActive] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    let raf = 0;
    const calc = () => {
      raf = 0;
      const mid = window.innerHeight * 0.5;
      let cur = 0;
      for (let i = 0; i < total; i += 1) {
        const el = sceneElement(i);
        if (el && el.getBoundingClientRect().top <= mid) cur = i;
      }
      setActive(cur);
    };
    const on = () => {
      if (!raf) raf = requestAnimationFrame(calc);
    };
    calc();
    window.addEventListener("scroll", on, { passive: true });
    window.addEventListener("resize", on);
    // Pins, lazy scenes and fonts move the scenes without any scroll event: recompute whenever the layout is re-measured.
    registerMotion();
    ScrollTrigger.addEventListener("refresh", on);
    const resizer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(on) : null;
    resizer?.observe(document.body);
    return () => {
      window.removeEventListener("scroll", on);
      window.removeEventListener("resize", on);
      ScrollTrigger.removeEventListener("refresh", on);
      resizer?.disconnect();
      if (raf) cancelAnimationFrame(raf);
    };
  }, [total, enabled]);
  return active;
}

export function SceneIndicator({ total, active, className, labels = SCENE_LABELS, onSelect }: SceneIndicatorProps): ReactElement {
  return (
    <nav
      aria-label="Story scenes"
      data-scene-indicator
      data-testid="scene-indicator"
      className={cn(
        "fixed bottom-4 left-1/2 z-30 -translate-x-1/2 rounded-full border border-gold-leaf/70 bg-cream/90 px-3 py-1 shadow-[0_8px_24px_-12px_rgba(74,14,23,0.6)] backdrop-blur",
        className,
      )}
    >
      <ol className="flex items-center">
        {/* Six dots for scenes 1-6: the hero (scene 0) lights none. */}
        {Array.from({ length: total - 1 }, (_, k) => {
          const i = k + 1;
          const on = i === active;
          const label = labels[i] ?? `Scene ${i}`;
          return (
            <li key={i}>
              <button
                type="button"
                onClick={() => (onSelect ? onSelect(i) : jumpToScene(i))}
                aria-label={`Scene ${i + 1} of ${total}: ${label}`}
                aria-current={on ? "true" : undefined}
                data-testid="scene-dot"
                title={label}
                className="group flex size-6 items-center justify-center rounded-full focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-offset-1 focus-visible:outline-maroon"
              >
                <span
                  aria-hidden
                  className={cn(
                    "block rounded-full transition-[transform,background-color] duration-base ease-standard",
                    on ? "size-3 scale-110 bg-maroon ring-2 ring-gold-leaf/70" : "size-2 bg-maroon/30 group-hover:bg-maroon/60",
                  )}
                />
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export default SceneIndicator;
