"use client";
// Abhiyojak: objection cards drop on one pan, replies on the other; the scales stay tipped while anything is
// unanswered (plan §13.4). The beam angle is tweened as a number and written to the SVG transform attributes, so the
// hanging pans stay upright. Our own scales line art.
import { useRef, type ReactElement } from "react";
import { registerMotion, useGSAP } from "@/lib/motion/register";
import {
  AgentFrame, PALETTE, type Palette, type TL, hasPlayed, markPlayed, useIsStatic, useReplay, type AgentArtProps,
} from "./shared";

export interface AbhiyojakScalesProps extends AgentArtProps {
  /** Objections still without a reply (default 1). 0 lets the scales settle level in full mode. */
  unanswered?: number;
}

const PX = 130;
const PY = 44;
const ARM = 84;
const OBJECTIONS = 3;
const WORKING_TILT = -8;

const beamTransform = (a: number) => `rotate(${a} ${PX} ${PY})`;
const panTransform = (a: number, side: -1 | 1) => {
  const r = (a * Math.PI) / 180;
  return `translate(${PX + side * ARM * Math.cos(r)} ${PY + side * ARM * Math.sin(r)})`;
};

function Card({ k, kind, p }: { k: number; kind: "objection" | "reply"; p: Palette }): ReactElement {
  const tab = kind === "objection" ? p.sindoor : p.neem;
  const y = 55 - 15 * (k + 1);
  const jitter = (k % 2 === 0 ? -1.5 : 1.5);
  return (
    <g data-card={kind} transform={`translate(${jitter} 0)`}>
      <g>
        <rect x={-13} y={y} width={26} height={13} rx={2} fill={p.card} stroke={p.cardLine} strokeWidth={0.8} />
        <rect x={-13} y={y} width={5} height={13} rx={2} fill={tab} />
        <text x={-10.5} y={y + 9} textAnchor="middle" fontSize={6.4} fontWeight={700} fill="var(--color-cream)">{kind === "objection" ? "?" : "✓"}</text>
        <rect x={-5} y={y + 4} width={14} height={1.8} rx={0.9} fill={p.inkFaint} />
        <rect x={-5} y={y + 8} width={9} height={1.8} rx={0.9} fill={p.inkFaint} />
      </g>
    </g>
  );
}

export function AbhiyojakScales({ mode, active, statusText, className, surface = "light", unanswered = 1 }: AbhiyojakScalesProps): ReactElement {
  const rootRef = useRef<HTMLDivElement>(null);
  const beamRef = useRef<SVGGElement>(null);
  const panLRef = useRef<SVGGElement>(null);
  const panRRef = useRef<SVGGElement>(null);
  const isStatic = useIsStatic(mode);
  const [replay, onReplay] = useReplay();
  const p = PALETTE[surface];
  const full = mode === "full";

  const open = Math.max(0, Math.min(OBJECTIONS, Math.round(unanswered)));
  const replies = OBJECTIONS - open;
  const fullTilt = open > 0 ? -Math.min(4 + open * 2, 10) : 0;
  const restTilt = full ? fullTilt : WORKING_TILT;

  useGSAP(
    () => {
      if (isStatic) return;
      const gsap = registerMotion();
      const render = (a: number) => {
        beamRef.current?.setAttribute("transform", beamTransform(a));
        panLRef.current?.setAttribute("transform", panTransform(a, -1));
        panRRef.current?.setAttribute("transform", panTransform(a, 1));
      };
      const proxy = { angle: 0 };
      const tip = (tl: TL, to: number, at: number, duration: number) =>
        tl.to(proxy, { angle: to, duration, ease: "power2.inOut", onUpdate: () => render(proxy.angle) }, at);
      const drop = (tl: TL, sel: string, at: number, stagger: number) =>
        tl.fromTo(sel, { y: -58, opacity: 0, transformOrigin: "50% 50%" }, { y: 0, opacity: 1, duration: 0.32, stagger, ease: "bounce.out", transformOrigin: "50% 50%" }, at);

      const cleanup = () => render(restTilt);

      if (full) {
        const tl = gsap.timeline({ paused: true });
        render(0);
        drop(tl, '[data-pan="L"] [data-card] > g', 0, 0.28);
        tip(tl, WORKING_TILT, 0.15, 0.8);
        if (replies > 0) {
          drop(tl, '[data-pan="R"] [data-card] > g', 1.2, 0.28);
          tip(tl, fullTilt, 1.4, 0.9);
        } else {
          tip(tl, fullTilt, 1.2, 0.9);
        }
        if (hasPlayed("ABHIYOJAK") && replay === 0) {
          tl.progress(1).pause();
        } else {
          tl.eventCallback("onComplete", () => markPlayed("ABHIYOJAK")).play(0);
        }
        return cleanup;
      }

      if (!active) return cleanup;
      render(0);
      const tl = gsap.timeline({ repeat: -1 });
      drop(tl, '[data-pan="L"] [data-card] > g', 0.05, 0.3);
      tip(tl, WORKING_TILT, 0.15, 0.9);
      tl.to('[data-card] > g', { opacity: 0, duration: 0.3, ease: "power1.in" }, 1.5);
      tip(tl, 0, 1.5, 0.3);
      return cleanup;
    },
    { scope: rootRef, dependencies: [mode, active, isStatic, replay, full, restTilt, replies], revertOnUpdate: true },
  );

  return (
    <AgentFrame
      agent="ABHIYOJAK" mode={mode} active={active} statusText={statusText} className={className} surface={surface}
      isStatic={isStatic} viewBox="0 0 260 190" rootRef={rootRef} onReplay={onReplay}
    >
      {/* stand */}
      <path d="M130 48V160" stroke={p.line} strokeWidth={4} strokeLinecap="round" />
      <path d="M96 176c0-10 14-16 34-16s34 6 34 16z" fill={p.gold} fillOpacity={0.3} stroke={p.gold} strokeWidth={1.4} strokeLinejoin="round" />
      <path d="M116 168h28" stroke={p.gold} strokeWidth={1} />

      {/* beam */}
      <g ref={beamRef} transform={beamTransform(restTilt)}>
        <path d={`M${PX - ARM} ${PY - 2.5}H${PX + ARM}`} stroke={p.line} strokeWidth={5} strokeLinecap="round" />
        <path d={`M${PX - ARM + 6} ${PY}H${PX + ARM - 6}`} stroke={p.gold} strokeWidth={1} />
        <circle cx={PX - ARM} cy={PY - 2.5} r={3.4} fill={p.gold} />
        <circle cx={PX + ARM} cy={PY - 2.5} r={3.4} fill={p.gold} />
      </g>
      <circle cx={PX} cy={PY - 2.5} r={7} fill={p.card} stroke={p.gold} strokeWidth={2} />
      <circle cx={PX} cy={PY - 2.5} r={2.4} fill={p.gold} />

      {/* pans: origin at the beam end, hanging down */}
      {([-1, 1] as const).map((side) => {
        const kind = side === -1 ? "objection" : "reply";
        const count = side === -1 ? OBJECTIONS : replies;
        return (
          <g
            key={side}
            ref={side === -1 ? panLRef : panRRef}
            data-pan={side === -1 ? "L" : "R"}
            transform={panTransform(restTilt, side)}
          >
            <path d="M0 -2L-30 56M0 -2L30 56" stroke={p.line} strokeWidth={0.9} strokeOpacity={0.8} />
            {Array.from({ length: kind === "reply" && mode !== "full" ? 0 : count }, (_, k) => (
              <Card key={k} k={k} kind={kind} p={p} />
            ))}
            <path d="M-34 56H34c0 11-8 17-17 17S-34 67-34 56z" fill={p.gold} fillOpacity={0.3} stroke={p.gold} strokeWidth={1.4} strokeLinejoin="round" />
          </g>
        );
      })}
    </AgentFrame>
  );
}

export default AbhiyojakScales;
