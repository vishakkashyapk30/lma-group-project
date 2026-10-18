"use client";
// Vakeel: the brief inks itself line by line inside an illuminated border; the full version settles citations as gold
// marginalia and gives NEEDS_REVIEW lines a maroon underline (plan §13.4). Own border, no emblem or court artwork.
import { useRef, type ReactElement } from "react";
import { registerMotion, useGSAP } from "@/lib/motion/register";
import {
  AgentFrame, PALETTE, hasPlayed, markPlayed, useIsStatic, useReplay, type AgentArtProps,
} from "./shared";

export type VakeelManuscriptProps = AgentArtProps;

const LINES = [168, 176, 150, 172, 124, 170, 158, 96] as const;
const LINE_Y = (i: number) => 52 + i * 14;
const CITED = [{ line: 1, label: "[1]" }, { line: 3, label: "[2]" }, { line: 6, label: "[3]" }] as const;
const REVIEW = [4, 7] as const;
const LEFT = 32;

/** One corner ornament at (cx, cy), mirrored by (sx, sy) in {1, -1}. */
function Corner({ cx, cy, sx, sy, color }: { cx: number; cy: number; sx: number; sy: number; color: string }): ReactElement {
  return (
    <g transform={`translate(${cx} ${cy}) scale(${sx} ${sy})`} stroke={color} strokeLinecap="round" strokeLinejoin="round">
      <path d="M0 22C0 8 8 0 22 0" strokeWidth={1.2} />
      <path d="M6 22C6 12 12 6 22 6" strokeWidth={0.8} />
      <path d="M8 8l5 5-5 5-5-5z" strokeWidth={0.9} fill={color} fillOpacity={0.25} />
      <circle cx={22} cy={0} r={1.6} fill={color} stroke="none" />
      <circle cx={0} cy={22} r={1.6} fill={color} stroke="none" />
    </g>
  );
}

export function VakeelManuscript({ mode, active, statusText, className, surface = "light" }: VakeelManuscriptProps): ReactElement {
  const rootRef = useRef<HTMLDivElement>(null);
  const isStatic = useIsStatic(mode);
  const [replay, onReplay] = useReplay();
  const p = PALETTE[surface];
  const full = mode === "full";

  useGSAP(
    () => {
      if (isStatic) return;
      const gsap = registerMotion();
      const ORIGIN = "0% 50%";

      if (full) {
        const tl = gsap.timeline({ paused: true });
        tl.fromTo("[data-title]", { scaleX: 0 }, { scaleX: 1, duration: 0.3, ease: "power2.inOut", transformOrigin: ORIGIN }, 0)
          .fromTo("[data-ink]", { scaleX: 0 }, { scaleX: 1, duration: 0.26, stagger: 0.2, ease: "power2.inOut", transformOrigin: ORIGIN }, 0.25);
        CITED.forEach((c, k) => {
          tl.fromTo(`[data-margin="${k}"]`, { opacity: 0, x: 16, scale: 0.8, transformOrigin: "0% 50%" }, { opacity: 1, x: 0, scale: 1, duration: 0.45, ease: "back.out(1.7)", transformOrigin: "0% 50%" }, 1.9 + k * 0.22);
        });
        REVIEW.forEach((_, k) => {
          tl.fromTo(`[data-review="${k}"]`, { scaleX: 0 }, { scaleX: 1, duration: 0.35, ease: "power2.out", transformOrigin: ORIGIN }, 2.7 + k * 0.2)
            .fromTo(`[data-flag="${k}"]`, { opacity: 0, scale: 0.4, transformOrigin: "50% 50%" }, { opacity: 1, scale: 1, duration: 0.3, ease: "back.out(2)", transformOrigin: "50% 50%" }, 2.8 + k * 0.2);
        });
        if (hasPlayed("VAKEEL") && replay === 0) {
          tl.progress(1).pause();
        } else {
          tl.eventCallback("onComplete", () => markPlayed("VAKEEL")).play(0);
        }
        return;
      }

      if (!active) return;
      const tl = gsap.timeline({ repeat: -1 });
      tl.fromTo("[data-title]", { scaleX: 0 }, { scaleX: 1, duration: 0.2, ease: "power2.inOut", transformOrigin: ORIGIN }, 0)
        .fromTo("[data-ink]", { scaleX: 0 }, { scaleX: 1, duration: 0.2, stagger: 0.15, ease: "power2.inOut", transformOrigin: ORIGIN }, 0.15)
        .to("[data-title], [data-ink]", { opacity: 0, duration: 0.25, ease: "power1.in" }, 1.55);
    },
    { scope: rootRef, dependencies: [mode, active, isStatic, replay, full], revertOnUpdate: true },
  );

  return (
    <AgentFrame
      agent="VAKEEL" mode={mode} active={active} statusText={statusText} className={className} surface={surface}
      isStatic={isStatic} viewBox="0 0 260 190" rootRef={rootRef} onReplay={onReplay}
    >
      <rect x={4} y={4} width={252} height={182} rx={3} fill={p.card} stroke={p.gold} strokeWidth={1.6} />
      <rect x={10} y={10} width={240} height={170} rx={2} stroke={p.gold} strokeWidth={0.7} />
      <Corner cx={12} cy={12} sx={1} sy={1} color={p.gold} />
      <Corner cx={248} cy={12} sx={-1} sy={1} color={p.gold} />
      <Corner cx={12} cy={178} sx={1} sy={-1} color={p.gold} />
      <Corner cx={248} cy={178} sx={-1} sy={-1} color={p.gold} />

      <rect data-title x={LEFT} y={30} width={96} height={5} rx={2.5} fill={p.maroon} />
      <path d={`M${LEFT} 40H${LEFT + 180}`} stroke={p.gold} strokeWidth={0.8} strokeOpacity={0.7} />
      {LINES.map((w, i) => (
        <rect key={i} data-ink x={LEFT} y={LINE_Y(i)} width={w} height={3.4} rx={1.7} fill={p.ink} fillOpacity={0.78} />
      ))}

      {full ? (
        <>
          {CITED.map((c, k) => (
            <g key={c.label} data-margin={k}>
              <path d={`M${LEFT + LINES[c.line] + 4} ${LINE_Y(c.line) + 1.7}H214`} stroke={p.gold} strokeWidth={0.9} strokeDasharray="1.5 2" />
              <rect x={214} y={LINE_Y(c.line) - 5} width={24} height={13} rx={2} fill={p.gold} fillOpacity={0.22} stroke={p.gold} strokeWidth={0.9} />
              <text x={226} y={LINE_Y(c.line) + 4.2} textAnchor="middle" fontSize={7.4} fontWeight={600} className="font-mono" fill={p.ink}>{c.label}</text>
            </g>
          ))}
          {REVIEW.map((line, k) => (
            <g key={line}>
              <rect data-review={k} x={LEFT} y={LINE_Y(line) + 5.5} width={LINES[line]} height={1.8} rx={0.9} fill={p.maroon} />
              <g data-flag={k}>
                <circle cx={LEFT - 10} cy={LINE_Y(line) + 1.7} r={4.4} fill={p.haldi} />
                <text x={LEFT - 10} y={LINE_Y(line) + 4.3} textAnchor="middle" fontSize={7} fontWeight={700} fill="var(--color-cream)">?</text>
              </g>
            </g>
          ))}
        </>
      ) : null}
    </AgentFrame>
  );
}

export default VakeelManuscript;
