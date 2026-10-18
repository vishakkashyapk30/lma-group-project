"use client";
// Pairokar: cause-list bars slide as cases are scored; the full version re-ranks the board by urgency (plan §13.4).
import { useRef, type ReactElement } from "react";
import { registerMotion, useGSAP } from "@/lib/motion/register";
import {
  AgentFrame, PALETTE, type TL, hasPlayed, markPlayed, useIsStatic, useReplay, type AgentArtProps,
} from "./shared";

export type PairokarCauseListBarsProps = AgentArtProps;

const CASES = [
  { id: "A-07", score: 42 },
  { id: "B-12", score: 91 },
  { id: "C-03", score: 28 },
  { id: "D-21", score: 76 },
  { id: "E-09", score: 58 },
] as const;
const ROW = 31;
const TOP = 12;
const TRACK_X = 76;
const TRACK_W = 132;

const rank = CASES.map((c, i) => ({ i, score: c.score }))
  .sort((a, b) => b.score - a.score)
  .map((r) => r.i);
const slotOf = (i: number) => rank.indexOf(i);
const level = (score: number) => (score >= 70 ? "HIGH" : score >= 40 ? "MED" : "LOW");

export function PairokarCauseListBars({ mode, active, statusText, className, surface = "light" }: PairokarCauseListBarsProps): ReactElement {
  const rootRef = useRef<HTMLDivElement>(null);
  const isStatic = useIsStatic(mode);
  const [replay, onReplay] = useReplay();
  const p = PALETTE[surface];

  const tone = (score: number) => (score >= 70 ? p.sindoor : score >= 40 ? p.haldi : p.indigo);

  useGSAP(
    () => {
      if (isStatic) return;
      const gsap = registerMotion();
      const ORIGIN = "0% 50%";
      const score = (tl: TL, stagger: number, duration: number) => {
        tl.fromTo("[data-fill]", { scaleX: 0.15 }, { scaleX: 1, duration, stagger, ease: "power2.out", transformOrigin: ORIGIN }, 0)
          .fromTo("[data-score]", { opacity: 0 }, { opacity: 1, duration: 0.25, stagger }, duration * 0.5);
      };

      if (mode === "full") {
        const tl = gsap.timeline({ paused: true });
        score(tl, 0.14, 0.6);
        CASES.forEach((_, i) => {
          tl.to(`[data-row="${i}"]`, { y: (slotOf(i) - i) * ROW, duration: 0.7, ease: "power3.inOut" }, 1.5 + i * 0.07);
        });
        tl.fromTo("[data-top]", { opacity: 0 }, { opacity: 1, duration: 0.4 }, 2.1);
        if (hasPlayed("PAIROKAR") && replay === 0) {
          tl.progress(1).pause();
        } else {
          tl.eventCallback("onComplete", () => markPlayed("PAIROKAR")).play(0);
        }
        return;
      }

      if (!active) return;
      const tl = gsap.timeline({ repeat: -1, yoyo: true, repeatDelay: 0.05 });
      score(tl, 0.1, 0.5);
    },
    { scope: rootRef, dependencies: [mode, active, isStatic, replay], revertOnUpdate: true },
  );

  return (
    <AgentFrame
      agent="PAIROKAR" mode={mode} active={active} statusText={statusText} className={className} surface={surface}
      isStatic={isStatic} viewBox="0 0 260 172" rootRef={rootRef} onReplay={onReplay}
    >
      {CASES.map((_, slot) => (
        <text key={slot} x={12} y={TOP + slot * ROW + 17} textAnchor="middle" fontSize={11} className="font-display" fill={p.line}>
          {slot + 1}
        </text>
      ))}
      {mode === "full" ? (
        <rect data-top x={24} y={TOP - 2} width={232} height={ROW - 3} rx={5} stroke={p.gold} strokeWidth={1.6} opacity={0} />
      ) : null}
      {CASES.map((c, i) => {
        const y = TOP + i * ROW;
        return (
          <g key={c.id} data-row={i}>
            <rect x={26} y={y} width={228} height={ROW - 7} rx={4} fill={p.card} stroke={p.cardLine} strokeWidth={0.9} />
            <text x={34} y={y + 15.5} fontSize={8} fontWeight={600} className="font-mono" fill={p.ink}>{c.id}</text>
            <rect x={TRACK_X} y={y + 7} width={TRACK_W} height={10} rx={5} fill={p.inkFaint} />
            <rect data-fill x={TRACK_X} y={y + 7} width={(TRACK_W * c.score) / 100} height={10} rx={5} fill={tone(c.score)} />
            <text data-score x={TRACK_X + TRACK_W + 8} y={y + 15} fontSize={7} fontWeight={600} className="font-mono" fill={tone(c.score)}>
              {`${level(c.score)} ${c.score}`}
            </text>
          </g>
        );
      })}
    </AgentFrame>
  );
}

export default PairokarCauseListBars;
