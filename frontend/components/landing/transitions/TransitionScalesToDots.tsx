"use client";
// Transition 0 to 1 (plan §13.3): the two pans of the scales fall away as gold dots, and the dots multiply into a row of
// six: the scene indicator. Scrubbed on a pin. Reduced motion shows the final frame: the row of six, one lit.
import { useRef, type ReactElement } from "react";
import { cn } from "@/lib/utils";
import { registerMotion, useGSAP } from "@/lib/motion/register";
import { useSceneReduced } from "../art/useSceneMotion";

export interface TransitionScalesToDotsProps {
  className?: string;
  reducedMotion?: boolean;
}

const DOT_X = [100, 140, 180, 220, 260, 300] as const;
const DOT_Y = 262;
const PAN_Y = 196;
const PAN_X = [92, 308] as const;

export function TransitionScalesToDots({ className, reducedMotion }: TransitionScalesToDotsProps): ReactElement {
  const reduced = useSceneReduced(reducedMotion);
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      if (reduced) return;
      const gsap = registerMotion();
      const el = root.current;
      if (!el) return;
      const q = <T extends Element>(s: string) => Array.from(el.querySelectorAll<T>(s));
      const dots = q<SVGCircleElement>("[data-dot]");
      const pans = q<SVGGElement>("[data-pan]");
      const rig = el.querySelector<SVGGElement>("[data-rig]");
      const ring = el.querySelector<SVGCircleElement>("[data-lit-ring]");
      const caption = el.querySelector<HTMLElement>("[data-caption]");
      if (!rig || !ring) return;

      gsap.set(rig, { opacity: 1 });
      gsap.set(dots, {
        opacity: 0,
        scale: 0,
        svgOrigin: (i: number) => `${DOT_X[i]} ${DOT_Y}`,
        x: (i: number) => PAN_X[i < 3 ? 0 : 1] - DOT_X[i],
        y: PAN_Y + 14 - DOT_Y,
      });
      gsap.set(ring, { opacity: 0 });
      if (caption) gsap.set(caption, { opacity: 0, y: 12 });

      const tl = gsap.timeline({
        defaults: { ease: "none" },
        scrollTrigger: { trigger: el, start: "top top+=56", end: "+=110%", pin: true, scrub: 0.6, anticipatePin: 1 },
      });
      tl.to(el.querySelector("[data-beam]"), { rotation: 5, svgOrigin: "200 84", duration: 0.2 }, 0)
        .to(pans, { y: 120, opacity: 0, duration: 0.45, ease: "power2.in", stagger: 0.08 }, 0.15)
        .to(dots, { opacity: 1, scale: 1, duration: 0.2, stagger: 0.05, ease: "power2.out" }, 0.25)
        .to(dots, { x: 0, y: 0, duration: 0.5, stagger: 0.06, ease: "power3.inOut" }, 0.5)
        .to(rig, { opacity: 0, y: -30, duration: 0.3 }, 0.7)
        .to(ring, { opacity: 1, duration: 0.15 }, 1.0)
        .to(caption ?? [], { opacity: 1, y: 0, duration: 0.2 }, 1.0);
    },
    { scope: root, dependencies: [reduced], revertOnUpdate: true },
  );

  return (
    <section
      ref={root}
      data-transition="scales-to-dots"
      aria-label="Six scenes, one citizen's journey"
      className={cn("relative flex min-h-[70svh] flex-col items-center justify-center overflow-hidden bg-oxblood text-cream", className)}
    >
      <div aria-hidden className="bg-jaali-dark pointer-events-none absolute inset-0 opacity-50" />
      <svg viewBox="0 0 400 300" aria-hidden focusable="false" className="relative w-[min(92vw,640px)]" fill="none" stroke="var(--color-gold-leaf)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <g data-rig style={{ opacity: reduced ? 0 : 1 }}>
          <path d="M200 84V236M168 236H232M176 244H224" />
          <circle cx="200" cy="76" r="7" />
          <g data-beam>
            <path d="M92 84H308" />
            <circle cx="92" cy="84" r="3.5" />
            <circle cx="308" cy="84" r="3.5" />
          </g>
          {PAN_X.map((x) => (
            <g key={x} data-pan>
              <path d={`M${x} 84L${x - 30} ${PAN_Y}M${x} 84L${x + 30} ${PAN_Y}M${x} 84V${PAN_Y}`} strokeWidth="1.1" />
              <path d={`M${x - 36} ${PAN_Y}H${x + 36}C${x + 34} ${PAN_Y + 22} ${x - 34} ${PAN_Y + 22} ${x - 36} ${PAN_Y}Z`} />
            </g>
          ))}
        </g>
        <g stroke="none" fill="var(--color-gold-leaf)">
          {DOT_X.map((x, i) => (
            <circle key={x} data-dot cx={x} cy={DOT_Y} r={i === 0 ? 6.5 : 4.5} fill={i === 0 ? "var(--color-gold-pale)" : "var(--color-gold-leaf)"} />
          ))}
        </g>
        <circle data-lit-ring cx={DOT_X[0]} cy={DOT_Y} r="12" stroke="var(--color-gold-pale)" strokeWidth="1.2" style={{ opacity: 1 }} />
      </svg>
      <p data-caption className="relative mt-4 px-6 text-center font-display text-xl italic text-gold-pale">
        One citizen. Six scenes. Follow the lit dot.
      </p>
    </section>
  );
}

export default TransitionScalesToDots;
