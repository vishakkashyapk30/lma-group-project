"use client";
// Scene 2, Arrest (Art. 22) (plan §13.3). The bars become a cell around a simple citizen figure (a circle and a rounded
// block); a 24-hour dial runs beside the real text of Art. 22(1)-(2). Pinned timeline. Reduced motion shows the final frame.
import { useRef, type ReactElement } from "react";
import { cn } from "@/lib/utils";
import { registerMotion, useGSAP } from "@/lib/motion/register";
import { CitizenFigure } from "../art/CitizenFigure";
import { useSceneReduced } from "../art/useSceneMotion";

export interface Scene2ArrestProps {
  className?: string;
  reducedMotion?: boolean;
}

const BARS = 9;
const HOUR_TICKS = Array.from({ length: 24 }, (_, h) => {
  const a = ((h * 15 - 90) * Math.PI) / 180;
  const r1 = h % 6 === 0 ? 86 : 91;
  return { h, x1: 120 + r1 * Math.cos(a), y1: 120 + r1 * Math.sin(a), x2: 120 + 97 * Math.cos(a), y2: 120 + 97 * Math.sin(a), major: h % 6 === 0 };
});
const NUMERALS = [
  { t: "0", x: 120, y: 74 },
  { t: "6", x: 166, y: 124 },
  { t: "12", x: 120, y: 178 },
  { t: "18", x: 74, y: 124 },
] as const;

export function Scene2Arrest({ className, reducedMotion }: Scene2ArrestProps): ReactElement {
  const reduced = useSceneReduced(reducedMotion);
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      if (reduced) return;
      const gsap = registerMotion();
      const el = root.current;
      if (!el) return;
      const q = <T extends Element>(s: string) => Array.from(el.querySelectorAll<T>(s));
      const bars = q<HTMLElement>("[data-cell-bar]");
      const rails = q<HTMLElement>("[data-cell-rail]");
      const figure = el.querySelector<HTMLElement>("[data-figure]");
      const head = el.querySelector<SVGElement>("[data-figure] [data-part='head']");
      const clauses = q<HTMLElement>("[data-clause]");
      const intro = q<HTMLElement>("[data-intro]");
      const hand = el.querySelector<SVGLineElement>("[data-hand]");
      const arc = el.querySelector<SVGCircleElement>("[data-arc]");
      const ticks = q<SVGLineElement>("[data-tick]");
      const label = q<SVGElement>("[data-dial-label]");
      const chip = el.querySelector<HTMLElement>("[data-chip]");
      if (!figure || !hand || !arc) return;

      gsap.set(intro, { opacity: 0, y: 16 });
      gsap.set(figure, { opacity: 0, y: 24 });
      gsap.set(bars, { opacity: 0, x: (i: number) => (i - (BARS - 1) / 2) * 90, scaleY: 1.15 });
      gsap.set(rails, { scaleX: 0, transformOrigin: "50% 50%" });
      gsap.set(clauses, { opacity: 0, y: 18 });
      gsap.set(ticks, { opacity: 0 });
      gsap.set(label, { opacity: 0 });
      gsap.set(hand, { rotation: 0, svgOrigin: "120 120" });
      if (chip) gsap.set(chip, { opacity: 0, scale: 0.9 });

      const tl = gsap.timeline({
        defaults: { ease: "none" },
        scrollTrigger: { trigger: el, start: "top top+=56", end: "+=240%", pin: true, scrub: 0.7, anticipatePin: 1 },
      });
      tl.to(intro, { opacity: 1, y: 0, duration: 0.5, stagger: 0.15, ease: "power2.out" }, 0)
        .to(figure, { opacity: 1, y: 0, duration: 0.7, ease: "power2.out" }, 0.3)
        // the bars become a cell
        .to(bars, { opacity: 1, x: 0, scaleY: 1, duration: 1.2, stagger: { each: 0.08, from: "center" }, ease: "power3.inOut" }, 1.0)
        .to(rails, { scaleX: 1, duration: 0.6, ease: "power2.out" }, 2.1)
        .to(head ?? [], { y: 5, duration: 0.5, ease: "power1.inOut" }, 2.3)
        // Art. 22(1)
        .to(clauses[0] ?? [], { opacity: 1, y: 0, duration: 0.5, ease: "power2.out" }, 2.6)
        // the dial and Art. 22(2)
        .to(clauses[1] ?? [], { opacity: 1, y: 0, duration: 0.5, ease: "power2.out" }, 3.1)
        .to(ticks, { opacity: 1, duration: 0.3, stagger: 0.03 }, 3.1)
        .to(label, { opacity: 1, duration: 0.3 }, 3.2)
        .fromTo(arc, { drawSVG: "0%" }, { drawSVG: "100%", duration: 2.2 }, 3.4)
        .to(hand, { rotation: 360, svgOrigin: "120 120", duration: 2.2 }, 3.4)
        .to(chip ?? [], { opacity: 1, scale: 1, duration: 0.3, ease: "back.out(2)" }, 5.5)
        .to({}, { duration: 0.5 }, 5.8);
    },
    { scope: root, dependencies: [reduced], revertOnUpdate: true },
  );

  return (
    <section
      ref={root}
      data-scene="2"
      data-testid="scene-2"
      data-motion={reduced ? "static" : "animated"}
      aria-labelledby="scene2-heading"
      className={cn("relative flex min-h-[100svh] items-center overflow-hidden bg-parchment text-ink", className)}
    >
      <div aria-hidden className="bg-jaali jaali-fade-r pointer-events-none absolute inset-0 opacity-60" />
      <div className="relative z-10 mx-auto grid w-full max-w-[1280px] items-center gap-10 px-6 py-16 sm:px-10 lg:grid-cols-12 lg:gap-14">
        {/* The cell */}
        <div className="lg:col-span-5">
          <div className="relative mx-auto aspect-[4/5] w-full max-w-[440px] rounded-2xl border border-gold-leaf/60 bg-cream shadow-[0_24px_60px_-30px_rgba(74,14,23,0.45)]">
            <div aria-hidden className="bg-jaali absolute inset-0 rounded-2xl opacity-60" />
            <div aria-hidden className="absolute inset-x-[10%] bottom-[8%] h-3 rounded-full bg-oxblood/10" />
            <div data-figure className="absolute inset-x-0 bottom-[11%] flex justify-center">
              <CitizenFigure tone="ink" className="h-[58%] min-h-[200px] w-auto" title="A citizen, held in a cell" />
            </div>
            <div aria-hidden className="absolute inset-x-[10%] top-[8%] bottom-[8%]">
              <span data-cell-rail className="absolute inset-x-0 top-0 block h-3 rounded-sm bg-maroon" />
              <span data-cell-rail className="absolute inset-x-0 bottom-0 block h-3 rounded-sm bg-maroon" />
              <div className="absolute inset-x-[3%] bottom-0 top-0 flex justify-between">
                {Array.from({ length: BARS }, (_, i) => (
                  <span key={i} data-cell-bar className="block h-full w-2 rounded-sm bg-maroon" />
                ))}
              </div>
            </div>
            <p className="absolute left-5 top-4 z-10 rounded-pill bg-cream/90 px-3 py-1 font-mono text-2xs uppercase tracking-[0.16em] text-maroon">
              Hour 0 · Arrested
            </p>
          </div>
        </div>

        {/* Dial and Article 22 */}
        <div className="flex flex-col gap-6 lg:col-span-7">
          <div className="flex flex-col gap-2">
            <p data-intro className="font-mono text-xs uppercase tracking-[0.2em] text-maroon">
              Scene 2 · Article 22 <span lang="hi" className="font-devanagari normal-case tracking-normal">· गिरफ़्तारी</span>
            </p>
            <h2 data-intro id="scene2-heading" className="font-display text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl">
              Arrested. <em className="italic text-maroon">The clock starts.</em>
            </h2>
          </div>

          <blockquote data-clause className="border-l-2 border-gold-leaf bg-cream/70 py-3 pl-5 pr-4">
            <p className="font-mono text-xs font-semibold uppercase tracking-wider text-maroon">Art. 22(1)</p>
            <p className="mt-1 font-display text-lg leading-relaxed text-ink">
              No person who is arrested shall be detained in custody without being informed, as soon as may be, of the grounds for such
              arrest nor shall he be denied the right to consult, and to be defended by, a legal practitioner of his choice.
            </p>
          </blockquote>

          <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-center">
            <div className="relative w-52 shrink-0">
              <svg viewBox="0 0 240 240" role="img" aria-label="A 24-hour dial: an arrested person must be produced before a magistrate within twenty-four hours" className="h-auto w-full" fill="none">
                <circle data-dial-ring cx="120" cy="120" r="108" stroke="var(--color-gold-leaf)" strokeWidth="1.5" />
                <circle data-dial-ring cx="120" cy="120" r="102" stroke="var(--color-line-strong)" strokeWidth="0.75" opacity="0.5" />
                {HOUR_TICKS.map((t) => (
                  <line key={t.h} data-tick x1={t.x1} y1={t.y1} x2={t.x2} y2={t.y2} stroke="var(--color-ink-soft)" strokeWidth={t.major ? 2.2 : 1.1} strokeLinecap="round" />
                ))}
                {NUMERALS.map((n) => (
                  <text key={n.t} data-dial-label x={n.x} y={n.y} textAnchor="middle" dominantBaseline="middle" fontFamily="var(--font-mono)" fontSize="13" fill="var(--color-ink-soft)" aria-hidden>
                    {n.t}
                  </text>
                ))}
                <circle data-arc cx="120" cy="120" r="104" stroke="var(--color-maroon)" strokeWidth="3.5" strokeLinecap="round" transform="rotate(-90 120 120)" />
                <text data-dial-label x="120" y="116" textAnchor="middle" fontFamily="var(--font-display)" fontSize="34" fontWeight="600" fill="var(--color-maroon)" aria-hidden>24</text>
                <text data-dial-label x="120" y="138" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="10" letterSpacing="2" fill="var(--color-ink-soft)" aria-hidden>HOURS</text>
                <line data-hand x1="120" y1="120" x2="120" y2="44" stroke="var(--color-maroon)" strokeWidth="2.5" strokeLinecap="round" />
                <circle cx="120" cy="120" r="5" fill="var(--color-maroon)" />
              </svg>
              <div className="absolute inset-x-0 -top-2 flex justify-center">
                <p data-chip className="whitespace-nowrap rounded-pill bg-maroon px-3 py-1 font-mono text-2xs uppercase tracking-wider text-cream">
                  Before a magistrate
                </p>
              </div>
            </div>
            <blockquote data-clause className="border-l-2 border-gold-leaf bg-cream/70 py-3 pl-5 pr-4">
              <p className="font-mono text-xs font-semibold uppercase tracking-wider text-maroon">Art. 22(2)</p>
              <p className="mt-1 font-display text-lg leading-relaxed text-ink">
                Every person who is arrested and detained in custody shall be produced before the nearest magistrate within a period of{" "}
                <strong className="font-semibold text-maroon">twenty-four hours</strong> of such arrest excluding the time necessary for the
                journey from the place of arrest to the court of the magistrate and no such person shall be detained in custody beyond the
                said period without the authority of a magistrate.
              </p>
            </blockquote>
          </div>
        </div>
      </div>
    </section>
  );
}

export default Scene2Arrest;
