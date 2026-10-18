"use client";
// Landing page (plan §13.3, §13.7): scenes 0-6 with the two geometry transitions, the scene indicator and the footer.
// Scene 0 and the first transition are in the main chunk; everything below the fold is lazy-loaded (still server-rendered,
// so the markup is there on first paint). Lenis smooth scrolling is wired into ScrollTrigger for this page only and is
// destroyed on unmount. Under prefers-reduced-motion the static storyboard replaces the whole animated stack; the
// [data-motion-only] / [data-static-only] CSS gates cover the frame before hydration.
import dynamic from "next/dynamic";
import { useEffect, useLayoutEffect, useState, type ReactElement } from "react";
import { cn } from "@/lib/utils";
import { registerMotion, ScrollTrigger, useLenis } from "@/lib/motion/register";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { Scene0Hero } from "./scenes/Scene0Hero";
import { TransitionScalesToDots } from "./transitions/TransitionScalesToDots";
import { SceneIndicator, useActiveScene } from "./SceneIndicator";
import { StaticStoryboard } from "./StaticStoryboard";
import { Footer } from "./Footer";

export interface LandingProps {
  className?: string;
}

const placeholder = () => <div aria-hidden className="min-h-[100svh] bg-parchment" />;

const Scene1WeThePeople = dynamic(() => import("./scenes/Scene1WeThePeople"), { loading: placeholder });
const TransitionWheelToBars = dynamic(() => import("./transitions/TransitionWheelToBars"), { loading: placeholder });
const Scene2Arrest = dynamic(() => import("./scenes/Scene2Arrest"), { loading: placeholder });
const Scene3Wait = dynamic(() => import("./scenes/Scene3Wait"), { loading: placeholder });
const Scene4PaperStorm = dynamic(() => import("./scenes/Scene4PaperStorm"), { loading: placeholder });
const Scene5Argument = dynamic(() => import("./scenes/Scene5Argument"), { loading: placeholder });
const Scene6Liberty = dynamic(() => import("./scenes/Scene6Liberty"), { loading: placeholder });

const SCENE_COUNT = 7;

/**
 * Scroll anchoring for the pins. A pin inserts a spacer above everything after it, so when a pin is created the scene counsel
 * is reading would jump away (a reload, a deep link or a fast scroll before the pins exist). This remembers which scene is at the
 * top of the screen and puts it back when a pin-spacer appears. It is mounted before the scenes so that it has measured first.
 */
function ScrollAnchor(): null {
  useLayoutEffect(() => {
    const root = document.querySelector<HTMLElement>("[data-landing]");
    const scene = (i: number) => document.querySelector<HTMLElement>(`[data-scene="${i}"]`);
    let anchor: { index: number; offset: number } | null = null;
    const capture = () => {
      anchor = null;
      if (window.scrollY < 8) return;
      for (let i = SCENE_COUNT - 1; i >= 0; i -= 1) {
        const el = scene(i);
        if (el && el.getBoundingClientRect().top <= 24) {
          anchor = { index: i, offset: el.getBoundingClientRect().top };
          return;
        }
      }
    };
    const restore = () => {
      const el = anchor ? scene(anchor.index) : null;
      if (!anchor || !el) return;
      const top = window.scrollY + el.getBoundingClientRect().top - anchor.offset;
      if (Math.abs(top - window.scrollY) > 2) window.scrollTo({ top, behavior: "instant" });
    };
    capture();
    window.addEventListener("scroll", capture, { passive: true });
    const observer = new MutationObserver((records) => {
      const spacerAdded = records.some((r) => Array.from(r.addedNodes).some((n) => n instanceof HTMLElement && n.classList.contains("pin-spacer")));
      if (spacerAdded) restore();
    });
    if (root) observer.observe(root, { childList: true, subtree: true });
    return () => {
      window.removeEventListener("scroll", capture);
      observer.disconnect();
    };
  }, []);
  return null;
}

export function Landing({ className }: LandingProps): ReactElement {
  const reduced = useReducedMotion();
  // The static storyboard rides along in the server markup (CSS-gated by [data-static-only]) so reduced-motion visitors get
  // it before hydration; once hydrated with motion allowed it is dropped so only one set of scenes exists.
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => setHydrated(true), []);
  useLenis(!reduced);
  const active = useActiveScene(SCENE_COUNT, !reduced);

  // Pinned sections add spacers and lazy chunks change heights: re-measure once things have settled.
  useEffect(() => {
    if (reduced) return;
    registerMotion();
    const refresh = () => ScrollTrigger.refresh();
    const timers = [window.setTimeout(refresh, 500), window.setTimeout(refresh, 1800)];
    window.addEventListener("load", refresh);
    void document.fonts?.ready.then(refresh);
    return () => {
      timers.forEach((t) => window.clearTimeout(t));
      window.removeEventListener("load", refresh);
    };
  }, [reduced]);

  return (
    <div data-landing className={cn("relative", className)}>
      {reduced ? (
        <StaticStoryboard />
      ) : (
        <>
          <div data-motion-only>
            <ScrollAnchor />
            <Scene0Hero />
            <TransitionScalesToDots />
            <Scene1WeThePeople />
            <TransitionWheelToBars />
            <Scene2Arrest />
            <Scene3Wait />
            <Scene4PaperStorm />
            <Scene5Argument />
            <Scene6Liberty />
            <SceneIndicator total={SCENE_COUNT} active={active} />
          </div>
          {hydrated ? null : (
            <div data-static-only>
              <StaticStoryboard bare />
            </div>
          )}
        </>
      )}
      <Footer />
    </div>
  );
}

export default Landing;
