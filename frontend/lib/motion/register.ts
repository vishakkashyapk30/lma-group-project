// GSAP plugin registration and the Lenis helper (plan §13.1, §13.4, §13.7).
// ScrollTrigger, SplitText, DrawSVG and MorphSVG ship free inside the gsap package since 3.13.
//
// Rules for every animation in the app:
// - call registerMotion() once (it is idempotent) before using a plugin; it is a no-op on the server;
// - create tweens inside useGSAP(() => {...}, { scope }) or gsap.context(); both revert tweens and kill the
//   ScrollTriggers they created on unmount;
// - animate transform and opacity only;
// - under reduced motion render the static version instead (useReducedMotion), do not just speed tweens up.
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import { DrawSVGPlugin } from "gsap/DrawSVGPlugin";
import { MorphSVGPlugin } from "gsap/MorphSVGPlugin";
import { useGSAP } from "@gsap/react";
import Lenis from "lenis";
import { useEffect, useState } from "react";
import { prefersReducedMotion } from "../useReducedMotion";

export { gsap, ScrollTrigger, SplitText, DrawSVGPlugin, MorphSVGPlugin, useGSAP, Lenis };

let registered = false;

/**
 * Register ScrollTrigger, SplitText, DrawSVGPlugin, MorphSVGPlugin and useGSAP with gsap, once. Client-only: returns
 * gsap untouched on the server. Safe to call from every component that animates.
 */
export function registerMotion(): typeof gsap {
  if (registered || typeof window === "undefined") return gsap;
  gsap.registerPlugin(ScrollTrigger, SplitText, DrawSVGPlugin, MorphSVGPlugin, useGSAP);
  gsap.defaults({ duration: MOTION.duration.slow, ease: MOTION.ease.enter });
  ScrollTrigger.config({ ignoreMobileResize: true });
  registered = true;
  return gsap;
}

/** True once registerMotion() has run in this browser session. */
export function isMotionRegistered(): boolean {
  return registered;
}

/** JS mirror of the motion tokens in styles/tokens.css (seconds, GSAP ease names). */
export const MOTION = {
  duration: {
    instant: 0.08,
    fast: 0.15,
    base: 0.22,
    slow: 0.36,
    deliberate: 0.6,
    scene: 1.2,
  },
  ease: {
    standard: "power2.out",
    enter: "expo.out",
    exit: "power3.in",
    ink: "power2.inOut",
    settle: "back.out(1.4)",
    linear: "none",
  },
  /** Working loops are low-amplitude and at most 2 s long (plan §13.4). */
  workingLoopMax: 2,
  /** Maximum translate offset (px) of a working loop. */
  workingAmplitude: 4,
  /** Default stagger between items in a sequence (s). */
  stagger: 0.06,
} as const;

/** Run `fn` only when motion is allowed (client, no reduced-motion preference). Returns fn's result or undefined. */
export function whenMotionAllowed<T>(fn: () => T): T | undefined {
  if (typeof window === "undefined" || prefersReducedMotion()) return undefined;
  return fn();
}

/** Kill every ScrollTrigger (use on route changes away from the landing page if a scene leaked one). */
export function killAllScrollTriggers(): void {
  if (typeof window === "undefined") return;
  ScrollTrigger.getAll().forEach((st) => st.kill());
}

/* ── Lenis (smooth scrolling for the landing page only; panes in the workspace scroll natively) ─────────────────── */

export type LenisOptions = ConstructorParameters<typeof Lenis>[0];

export interface LenisHandle {
  lenis: Lenis;
  destroy: () => void;
}

let active: { lenis: Lenis; refs: number; tick: (time: number) => void } | null = null;

/**
 * Start Lenis wired to GSAP's ticker and ScrollTrigger (one shared instance, reference counted). Returns null on the
 * server or under reduced motion: the page then scrolls natively. Call handle.destroy() on unmount.
 */
export function startLenis(options?: LenisOptions): LenisHandle | null {
  if (typeof window === "undefined" || prefersReducedMotion()) return null;
  registerMotion();
  if (!active) {
    const lenis = new Lenis({ lerp: 0.12, smoothWheel: true, ...options });
    const tick = (time: number) => lenis.raf(time * 1000);
    lenis.on("scroll", ScrollTrigger.update);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);
    active = { lenis, refs: 0, tick };
  }
  active.refs += 1;
  const current = active;
  let destroyed = false;
  return {
    lenis: current.lenis,
    destroy: () => {
      if (destroyed || !active || active !== current) return;
      destroyed = true;
      active.refs -= 1;
      if (active.refs <= 0) {
        gsap.ticker.remove(active.tick);
        gsap.ticker.lagSmoothing(500, 33);
        active.lenis.destroy();
        active = null;
      }
    },
  };
}

/** The running Lenis instance, if any (for scrollTo from "Watch the journey"). */
export function getLenis(): Lenis | null {
  return active?.lenis ?? null;
}

/**
 * React hook: smooth scrolling while the calling component is mounted (the landing page). No-op under reduced
 * motion. Returns the Lenis instance once started.
 */
export function useLenis(enabled = true, options?: LenisOptions): Lenis | null {
  const [lenis, setLenis] = useState<Lenis | null>(null);
  useEffect(() => {
    if (!enabled) return;
    const handle = startLenis(options);
    setLenis(handle?.lenis ?? null);
    return () => {
      handle?.destroy();
      setLenis(null);
    };
    // options are read once on start
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);
  return lenis;
}

/** Scroll to a target with Lenis when running, else natively (instant under reduced motion). */
export function scrollToTarget(target: string | HTMLElement | number, offset = 0): void {
  if (typeof window === "undefined") return;
  const lenis = getLenis();
  if (lenis) {
    lenis.scrollTo(target, { offset });
    return;
  }
  const behavior: ScrollBehavior = prefersReducedMotion() ? "auto" : "smooth";
  if (typeof target === "number") {
    window.scrollTo({ top: target + offset, behavior });
    return;
  }
  const el = typeof target === "string" ? document.querySelector<HTMLElement>(target) : target;
  if (!el) return;
  const top = el.getBoundingClientRect().top + window.scrollY + offset;
  window.scrollTo({ top, behavior });
}
