"use client";
// Scene 3, The wait (plan §13.3). Calendar pages flip ("tareekh pe tareekh"), custody bars grow like a chart past the
// half-sentence line (BNSS s.479), and the 75.8% counter runs (NCRB, Prison Statistics India 2022). Everything is scrubbed
// with the scroll on a pin. The bars chart is an illustration, labelled as such. Reduced motion shows the final frame.
import { useRef, type ReactElement } from "react";
import { cn } from "@/lib/utils";
import { registerMotion, useGSAP } from "@/lib/motion/register";
import { useSceneReduced } from "../art/useSceneMotion";

export interface Scene3WaitProps {
  className?: string;
  reducedMotion?: boolean;
}

const PAGES = [
  { month: "MAR", day: "03" },
  { month: "MAR", day: "17" },
  { month: "APR", day: "09" },
  { month: "APR", day: "28" },
  { month: "MAY", day: "14" },
  { month: "JUN", day: "02" },
] as const;
const MONTHS = 12;
const HALF = 0.5;
const UNDERTRIAL_PCT = 75.8;

export function Scene3Wait({ className, reducedMotion }: Scene3WaitProps): ReactElement {
  const reduced = useSceneReduced(reducedMotion);
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      if (reduced) return;
      const gsap = registerMotion();
      const el = root.current;
      if (!el) return;
      const q = <T extends Element>(s: string) => Array.from(el.querySelectorAll<T>(s));
      const pages = q<HTMLElement>("[data-page]");
      const bars = q<HTMLElement>("[data-bar]");
      const line = el.querySelector<HTMLElement>("[data-half]");
      const fill = el.querySelector<HTMLElement>("[data-fill]");
      const count = el.querySelector<HTMLElement>("[data-count]");
      const intro = q<HTMLElement>("[data-intro]");
      const caption = q<HTMLElement>("[data-after]");
      if (!fill || !count) return;

      const stack = el.querySelector<HTMLElement>("[data-stack]");
      gsap.set(pages, { transformPerspective: 900, transformOrigin: "50% 0%" });
      if (stack) gsap.set(stack, { opacity: 1 });
      gsap.set(intro, { opacity: 0, y: 16 });
      gsap.set(bars, { scaleY: 0, transformOrigin: "50% 100%" });
      if (line) gsap.set(line, { opacity: 0 });
      gsap.set(fill, { scaleX: 0, transformOrigin: "0% 50%" });
      gsap.set(caption, { opacity: 0, y: 12 });
      count.textContent = "0.0%";

      const counter = { v: 0 };
      const tl = gsap.timeline({
        defaults: { ease: "none" },
        scrollTrigger: { trigger: el, start: "top top+=56", end: "+=260%", pin: true, scrub: 0.7, anticipatePin: 1 },
      });
      tl.to(intro, { opacity: 1, y: 0, duration: 0.5, stagger: 0.15, ease: "power2.out" }, 0)
        // calendar pages flip, one after another
        .to(pages.slice(0, -1), { rotationX: -165, opacity: 0, duration: 0.55, stagger: 0.6, ease: "power2.in" }, 0.5)
        // custody bars grow like a chart
        .to(bars, { scaleY: 1, duration: 0.5, stagger: 0.28, ease: "power2.out" }, 1.0)
        .to(line ?? [], { opacity: 1, duration: 0.4 }, 3.0)
        // the counter runs
        .to(fill, { scaleX: 1, duration: 2.4, ease: "power1.inOut" }, 3.4)
        .to(counter, { v: UNDERTRIAL_PCT, duration: 2.4, ease: "power1.inOut", onUpdate: () => { count.textContent = `${counter.v.toFixed(1)}%`; } }, 3.4)
        .to(caption, { opacity: 1, y: 0, duration: 0.4, stagger: 0.15, ease: "power2.out" }, 5.4)
        .to({}, { duration: 0.6 }, 6.0);

      return () => {
        count.textContent = `${UNDERTRIAL_PCT}%`;
      };
    },
    { scope: root, dependencies: [reduced], revertOnUpdate: true },
  );

  const pages = reduced ? PAGES.slice(-1) : PAGES;

  return (
    <section
      ref={root}
      data-scene="3"
      data-testid="scene-3"
      data-motion={reduced ? "static" : "animated"}
      aria-labelledby="scene3-heading"
      className={cn("relative flex min-h-[100svh] items-center overflow-hidden bg-oxblood text-cream", className)}
    >
      <div aria-hidden className="bg-jaali-dark pointer-events-none absolute inset-0 opacity-50" />
      <div className="relative z-10 mx-auto flex w-full max-w-[1280px] flex-col gap-8 px-6 py-14 sm:px-10">
        <div className="flex flex-col gap-2">
          <p data-intro className="font-mono text-xs uppercase tracking-[0.2em] text-gold-pale">Scene 3 · The wait</p>
          <h2 data-intro id="scene3-heading" className="font-display text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl">
            Date after date, <em className="italic text-gold-pale">after date.</em>
          </h2>
          <p data-intro lang="hi" className="font-devanagari text-2xl leading-devanagari text-gold-pale">तारीख़ पे तारीख़</p>
        </div>

        <div className="grid items-end gap-10 lg:grid-cols-12 lg:gap-14">
          {/* Calendar pages */}
          <div className="flex flex-col items-center gap-4 lg:col-span-4">
            <div data-stack className="relative h-60 w-52" style={{ perspective: 900 }}>
              {pages.map((p, i) => (
                <div
                  key={`${p.month}${p.day}`}
                  data-page
                  className="absolute inset-0 flex flex-col overflow-hidden rounded-lg bg-cream text-ink shadow-[0_14px_30px_-12px_rgba(0,0,0,0.6)] [backface-visibility:hidden]"
                  style={{ zIndex: pages.length - i }}
                >
                  <div className="flex items-center justify-between bg-maroon px-4 py-2 font-mono text-xs tracking-[0.2em] text-cream">
                    <span>{p.month}</span>
                    <span aria-hidden className="flex gap-1.5">
                      <i className="block size-2 rounded-full bg-cream/70" />
                      <i className="block size-2 rounded-full bg-cream/70" />
                    </span>
                  </div>
                  <div className="flex flex-1 flex-col items-center justify-center">
                    <span className="font-display text-8xl font-semibold leading-none text-maroon">{p.day}</span>
                    <span className="mt-2 font-mono text-2xs uppercase tracking-[0.18em] text-ink-muted">Next date of hearing</span>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-center text-sm text-cream/85">Adjourned. Again.</p>
          </div>

          {/* Custody bars */}
          <figure className="lg:col-span-8">
            <figcaption className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <span className="font-display text-xl text-cream">Time in custody, month by month</span>
              <span className="font-mono text-2xs uppercase tracking-wider text-gold-pale">Illustration, not data</span>
            </figcaption>
            <div className="relative h-56 border-b border-gold-leaf/70">
              <div
                data-half
                className="absolute inset-x-0 z-10 border-t border-dashed border-gold-pale"
                style={{ bottom: `${HALF * 100}%` }}
              >
                <span className="absolute -top-6 right-0 rounded bg-oxblood px-2 font-mono text-2xs uppercase tracking-wider text-gold-pale">
                  Half the maximum sentence: release on bond, BNSS s.479
                </span>
              </div>
              <div className="absolute inset-0 flex items-end justify-between gap-2 sm:gap-3">
                {Array.from({ length: MONTHS }, (_, i) => {
                  const h = (i + 1) / MONTHS;
                  const over = h > HALF;
                  return (
                    <div key={i} className="flex h-full flex-1 items-end">
                      <span
                        data-bar
                        aria-hidden
                        className={cn("block w-full rounded-t-sm", over ? "bg-gold-pale" : "bg-gold-leaf")}
                        style={{ height: `${h * 100}%` }}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
            <div aria-hidden className="mt-1 flex justify-between font-mono text-2xs text-gold-pale/80">
              <span>Month 1</span>
              <span>Month 12</span>
            </div>
          </figure>
        </div>

        {/* Counter */}
        <div className="flex flex-col items-start gap-4 border-t border-gold-leaf/40 pt-6 sm:flex-row sm:items-center sm:gap-8">
          <p className="font-display text-7xl font-semibold leading-none text-gold-pale sm:text-8xl">
            <span aria-hidden data-count>{UNDERTRIAL_PCT}%</span>
            <span className="sr-only">{UNDERTRIAL_PCT}%</span>
          </p>
          <div className="flex-1">
            <div aria-hidden className="h-3 w-full overflow-hidden rounded-full bg-cream/15">
              <div data-fill className="h-full w-[75.8%] rounded-full bg-gold-pale" />
            </div>
            <p data-after className="mt-3 max-w-2xl text-lg leading-snug text-cream/95">
              of people in Indian prisons are undertrials: waiting for a verdict, not serving one.
            </p>
            <p data-after className="mt-1 font-mono text-2xs uppercase tracking-wider text-gold-pale">NCRB, Prison Statistics India 2022</p>
          </div>
        </div>
      </div>
    </section>
  );
}

export default Scene3Wait;
