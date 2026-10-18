"use client";
// Transition 1 to 2 (plan §13.3): the wheel's spokes come loose and fall into vertical bars. The 24 bars are overlaid on a
// rim-and-hub wheel at the exact position and angle of each spoke, then fly (scrubbed on a pin) into an evenly spaced row
// near the bottom, turning from gold to maroon as the background turns from oxblood to parchment.
// Reduced motion shows the final frame: the row of bars.
import { useRef, type ReactElement } from "react";
import { cn } from "@/lib/utils";
import { registerMotion, useGSAP } from "@/lib/motion/register";
import { Wheel24, WHEEL_SPOKES } from "../art/Wheel24";
import { useSceneReduced } from "../art/useSceneMotion";

export interface TransitionWheelToBarsProps {
  className?: string;
  reducedMotion?: boolean;
}

const BAR_PX = 100; // intrinsic bar height; GSAP scales it

export function TransitionWheelToBars({ className, reducedMotion }: TransitionWheelToBarsProps): ReactElement {
  const reduced = useSceneReduced(reducedMotion);
  const root = useRef<HTMLElement>(null);
  const stage = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      if (reduced) return;
      const gsap = registerMotion();
      const section = root.current;
      const st = stage.current;
      if (!section || !st) return;
      const bars = Array.from(section.querySelectorAll<HTMLElement>("[data-bar]"));
      const wheel = section.querySelector<HTMLElement>("[data-wheel]");
      const caption = section.querySelector<HTMLElement>("[data-caption]");
      if (!bars.length || !wheel) return;

      const size = () => st.getBoundingClientRect().width;
      const k = () => size() / 204; // wheel viewBox units to px
      const angle = (i: number) => ((i * 360) / WHEEL_SPOKES - 90) * (Math.PI / 180);
      const rowGap = () => Math.min(section.getBoundingClientRect().width * 0.8, 1150) / WHEEL_SPOKES;
      const rowY = () => {
        const s = section.getBoundingClientRect();
        const c = st.getBoundingClientRect();
        return s.top + s.height * 0.7 - (c.top + c.height / 2);
      };
      const barH = () => section.getBoundingClientRect().height * 0.42;

      gsap.set(bars, {
        opacity: 1,
        backgroundColor: "#D4B57E",
        x: (i: number) => 50 * k() * Math.cos(angle(i)),
        y: (i: number) => 50 * k() * Math.sin(angle(i)),
        rotation: (i: number) => i * 15,
        scaleY: () => (66 * k()) / BAR_PX,
      });
      if (caption) gsap.set(caption, { opacity: 0, y: 14 });

      const tl = gsap.timeline({
        defaults: { ease: "none" },
        scrollTrigger: { trigger: section, start: "top top+=56", end: "+=140%", pin: true, scrub: 0.6, anticipatePin: 1, invalidateOnRefresh: true },
      });
      // 1. the spokes come loose: drift outward, wobble
      tl.to(bars, {
        x: (i: number) => 62 * k() * Math.cos(angle(i)),
        y: (i: number) => 62 * k() * Math.sin(angle(i)),
        rotation: (i: number) => i * 15 + (i % 2 ? 9 : -9),
        duration: 0.3,
        ease: "power2.out",
        stagger: { each: 0.012, from: "start" },
      }, 0)
        // the rim and hub let go
        .to(wheel, { opacity: 0, scale: 0.92, duration: 0.45 }, 0.3)
        // 2. they fall into a row of vertical bars
        .to(bars, {
          x: (i: number) => (i - (WHEEL_SPOKES - 1) / 2) * rowGap(),
          y: () => rowY(),
          rotation: 0,
          scaleY: () => barH() / BAR_PX,
          duration: 0.7,
          ease: "power3.in",
          stagger: { each: 0.018, from: "random" },
        }, 0.35)
        .to(bars, { backgroundColor: "#7A1626", duration: 0.3, stagger: 0.01 }, 0.85)
        .to(caption ?? [], { opacity: 1, y: 0, duration: 0.25 }, 1.05);
    },
    { scope: root, dependencies: [reduced], revertOnUpdate: true },
  );

  return (
    <section
      ref={root}
      data-transition="wheel-to-bars"
      aria-label="The wheel becomes bars"
      className={cn(
        "relative flex min-h-[100svh] flex-col items-center justify-start overflow-hidden bg-gradient-to-b from-oxblood from-45% to-parchment pt-[10svh]",
        className,
      )}
    >
      <div aria-hidden className="bg-jaali-dark jaali-fade-b pointer-events-none absolute inset-0 opacity-40" />
      {reduced ? (
        <>
          <div aria-hidden className="relative z-10 mt-[12svh] flex w-[min(80vw,1150px)] items-end justify-between">
            {Array.from({ length: WHEEL_SPOKES }, (_, i) => (
              <span key={i} className="block h-[34svh] w-[3px] bg-maroon" />
            ))}
          </div>
        </>
      ) : (
        <div ref={stage} className="relative z-10 aspect-square w-[min(70vw,52svh,520px)]">
          <div data-wheel className="absolute inset-0">
            <Wheel24 className="h-full w-full" hideSpokes strokeWidth={1.2} />
          </div>
          <div aria-hidden className="absolute inset-0">
            {Array.from({ length: WHEEL_SPOKES }, (_, i) => (
              <span
                key={i}
                data-bar
                className="absolute left-1/2 top-1/2 block w-[3px] -ml-[1.5px] -mt-[50px] rounded-sm"
                style={{ height: BAR_PX, opacity: 0 }}
              />
            ))}
          </div>
        </div>
      )}
      <p data-caption className="absolute inset-x-0 bottom-[6svh] z-10 px-6 text-center font-display text-xl italic text-maroon">
        Twenty-four spokes. Twenty-four bars.
      </p>
    </section>
  );
}

export default TransitionWheelToBars;
