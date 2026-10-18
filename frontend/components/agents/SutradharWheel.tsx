"use client";
// Sutradhar: a 24-spoke wheel whose spokes light as each store or tool is queried; the full version reveals a
// "Show the plan" affordance (plan §13.4). Our own wheel, deliberately not the State Emblem's chakra.
import { useRef, useState, type ReactElement } from "react";
import { WHEEL_SPOKES, spokeForEvent } from "@/lib/stores";
import type { StoreName } from "@/lib/types";
import { registerMotion, useGSAP } from "@/lib/motion/register";
import { cn } from "@/lib/utils";
import {
  AgentFrame, PALETTE, hasPlayed, markPlayed, useIsStatic, useReplay, type AgentArtProps,
} from "./shared";

export interface SutradharWheelProps extends AgentArtProps {
  /** Stores queried so far: every spoke whose tool reads one of them stays lit. */
  litStores?: readonly StoreName[];
  /** Tool being called right now: its spoke pulses. */
  activeTool?: string | null;
  /** Called by the "Show the plan" button (full mode); the button is not shown without a handler. */
  onShowPlan?: () => void;
}

const COUNT = WHEEL_SPOKES.length;
const geometry = WHEEL_SPOKES.map((s) => {
  const a = ((s.index * 360) / COUNT - 90) * (Math.PI / 180);
  const at = (r: number) => ({ x: Number((r * Math.cos(a)).toFixed(2)), y: Number((r * Math.sin(a)).toFixed(2)) });
  return { index: s.index, inner: at(19), outer: at(80), bead: at(88) };
});

export function SutradharWheel({
  mode, active, statusText, className, surface = "light", litStores, activeTool, onShowPlan,
}: SutradharWheelProps): ReactElement {
  const rootRef = useRef<HTMLDivElement>(null);
  const isStatic = useIsStatic(mode);
  const [replay, onReplay] = useReplay();
  const [revealed, setRevealed] = useState(false);
  const p = PALETTE[surface];

  const lit = new Set<number>();
  for (const s of WHEEL_SPOKES) if (s.store && litStores?.includes(s.store)) lit.add(s.index);
  const activeIndex = activeTool ? spokeForEvent({ tool: activeTool, inputs: {} }) : null;
  if (activeIndex !== null) lit.add(activeIndex);
  const controlled = litStores !== undefined || activeTool !== undefined;
  const litKey = [...lit].join(",");

  useGSAP(
    () => {
      if (isStatic) return;
      const gsap = registerMotion();

      if (mode === "full") {
        const tl = gsap.timeline({ paused: true });
        tl.fromTo("[data-glow]", { opacity: 0 }, { opacity: 1, duration: 0.2, stagger: 0.045, ease: "power1.out" }, 0)
          .fromTo("[data-hubglow]", { opacity: 0 }, { opacity: 1, duration: 0.3 }, 0.9)
          .to("[data-glow]", { opacity: (i: number) => (lit.has(i) ? 1 : 0), duration: 0.5, stagger: 0.02 }, 1.5)
          .to("[data-hubglow]", { opacity: 0, duration: 0.5 }, 1.5);
        if (hasPlayed("SUTRADHAR") && replay === 0) {
          tl.progress(1).pause();
          setRevealed(true);
        } else {
          setRevealed(false);
          tl.eventCallback("onComplete", () => {
            markPlayed("SUTRADHAR");
            setRevealed(true);
          }).play(0);
        }
        return;
      }

      if (!active) return;
      if (controlled) {
        if (activeIndex === null) return;
        gsap.fromTo(`[data-glow="${activeIndex}"]`, { opacity: 1 }, { opacity: 0.45, duration: 0.5, repeat: -1, yoyo: true, ease: "sine.inOut" });
        gsap.fromTo(`[data-bead="${activeIndex}"]`, { scale: 1, transformOrigin: "50% 50%" }, { scale: 1.6, duration: 0.5, repeat: -1, yoyo: true, ease: "sine.inOut", transformOrigin: "50% 50%" });
        return;
      }
      const tl = gsap.timeline({ repeat: -1 });
      tl.fromTo("[data-glow]", { opacity: 0 }, { opacity: 1, duration: 0.16, stagger: 0.07, ease: "power1.out" }, 0)
        .fromTo("[data-bead]", { scale: 1, transformOrigin: "50% 50%" }, { scale: 1.5, duration: 0.16, stagger: 0.07, transformOrigin: "50% 50%" }, 0)
        .to("[data-glow]", { opacity: 0, duration: 0.2, stagger: 0.005 }, 1.62)
        .to("[data-bead]", { scale: 1, duration: 0.2, stagger: 0.005, transformOrigin: "50% 50%" }, 1.62);
    },
    { scope: rootRef, dependencies: [mode, active, isStatic, replay, litKey, controlled, activeIndex], revertOnUpdate: true },
  );

  const planButton =
    mode === "full" && onShowPlan ? (
      <button
        type="button"
        onClick={onShowPlan}
        tabIndex={revealed ? 0 : -1}
        aria-hidden={revealed ? undefined : true}
        className={cn(
          "rounded-pill px-3 py-0.5 text-xs font-medium transition-opacity duration-slow",
          surface === "dark" ? "bg-gold-pale text-oxblood" : "bg-maroon text-cream",
          revealed ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      >
        Show the plan
      </button>
    ) : null;

  return (
    <AgentFrame
      agent="SUTRADHAR" mode={mode} active={active} statusText={statusText} className={className} surface={surface}
      isStatic={isStatic} viewBox="-104 -104 208 208" rootRef={rootRef} onReplay={onReplay} controls={planButton}
    >
      <circle r={100} stroke={p.gold} strokeWidth={1.4} />
      <circle r={94} stroke={p.gold} strokeWidth={0.8} strokeOpacity={0.6} />
      {geometry.map((g) => {
        const on = lit.has(g.index);
        return (
          <g key={g.index}>
            <line x1={g.inner.x} y1={g.inner.y} x2={g.outer.x} y2={g.outer.y} stroke={p.line} strokeWidth={1} strokeOpacity={0.6} strokeLinecap="round" />
            <circle cx={g.bead.x} cy={g.bead.y} r={1.8} fill={p.line} fillOpacity={0.7} />
            <g data-glow={g.index} opacity={on ? 1 : 0}>
              <line x1={g.inner.x} y1={g.inner.y} x2={g.outer.x} y2={g.outer.y} stroke={p.gold} strokeWidth={2.6} strokeLinecap="round" />
              <circle data-bead={g.index} cx={g.bead.x} cy={g.bead.y} r={2.6} fill={p.gold} />
            </g>
          </g>
        );
      })}
      <circle r={15} stroke={p.gold} strokeWidth={1.2} />
      <circle data-hubglow r={17} stroke={p.gold} strokeWidth={2.4} opacity={0} />
      <circle r={5} fill={p.gold} fillOpacity={0.85} />
      <path
        d="M0 -14C5 -9 5 -4 0 0C-5 -4 -5 -9 0 -14ZM14 0C9 5 4 5 0 0C4 -5 9 -5 14 0ZM0 14C-5 9 -5 4 0 0C5 4 5 9 0 14ZM-14 0C-9 -5 -4 -5 0 0C-4 5 -9 5 -14 0Z"
        stroke={p.gold} strokeWidth={0.7}
      />
    </AgentFrame>
  );
}

export default SutradharWheel;
