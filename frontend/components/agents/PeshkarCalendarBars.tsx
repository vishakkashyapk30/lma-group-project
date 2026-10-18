"use client";
// Peshkar: calendar pages tick and custody bars grow; the full version sweeps the Rights Radar over a timeline and
// flag chips pop out ("Default-bail window: 6 days") (plan §13.4).
import { useId, useRef, type ReactElement } from "react";
import { registerMotion, useGSAP } from "@/lib/motion/register";
import {
  AgentFrame, PALETTE, type TL, hasPlayed, markPlayed, useIsStatic, useReplay, type AgentArtProps,
} from "./shared";

export type PeshkarCalendarBarsProps = AgentArtProps;

const BARS = [
  { label: "Days in custody", w: 132 },
  { label: "Half-term limit", w: 96 },
  { label: "Default-bail clock", w: 60 },
] as const;
const MARKERS = [
  { x: 64, row: 0, text: "Default-bail window: 6 days", w: 128, tone: "sindoor", mark: "!" },
  { x: 150, row: 1, text: "Custody: 62 days", w: 86, tone: "indigo", mark: "ƒ" },
  { x: 236, row: 0, text: "s.479 limit: 41 days", w: 100, tone: "haldi", mark: "?" },
] as const;
const TL_Y = 166;
const SWEEP_FROM = 12;
const SWEEP_TO = 288;
const SWEEP_AT = 0.9;
const SWEEP_LEN = 1.8;

export function PeshkarCalendarBars({ mode, active, statusText, className, surface = "light" }: PeshkarCalendarBarsProps): ReactElement {
  const rootRef = useRef<HTMLDivElement>(null);
  const isStatic = useIsStatic(mode);
  const [replay, onReplay] = useReplay();
  const p = PALETTE[surface];
  const gradId = `peshkar-sweep-${useId().replace(/:/g, "")}`;
  const barFill = surface === "dark" ? p.gold : p.maroon;
  const full = mode === "full";

  useGSAP(
    () => {
      if (isStatic) return;
      const gsap = registerMotion();

      const build = (tl: TL) => {
        tl.fromTo('[data-leaf="0"]', { scaleY: 1 }, { scaleY: 0.04, duration: 0.22, ease: "power2.in", transformOrigin: "50% 0%" }, 0)
          .fromTo('[data-leaf="1"]', { scaleY: 1 }, { scaleY: 0.04, duration: 0.22, ease: "power2.in", transformOrigin: "50% 0%" }, 0.42)
          .fromTo("[data-tick]", { opacity: 0, scale: 0.4, transformOrigin: "50% 50%" }, { opacity: 1, scale: 1, duration: 0.18, stagger: 0.06, ease: "back.out(2)", transformOrigin: "50% 50%" }, 0.1)
          .fromTo("[data-bar]", { scaleX: 0.25 }, { scaleX: 1, duration: 0.6, stagger: 0.08, ease: "power2.out", transformOrigin: "0% 50%" }, 0);
      };

      if (full) {
        const tl = gsap.timeline({ paused: true });
        build(tl);
        tl.fromTo("[data-sweep]", { x: SWEEP_FROM, opacity: 0 }, { x: SWEEP_TO, opacity: 1, duration: SWEEP_LEN, ease: "none" }, SWEEP_AT)
          .to("[data-sweep]", { opacity: 0, duration: 0.25 }, SWEEP_AT + SWEEP_LEN);
        MARKERS.forEach((m, i) => {
          const at = SWEEP_AT + ((m.x - SWEEP_FROM) / (SWEEP_TO - SWEEP_FROM)) * SWEEP_LEN;
          tl.fromTo(`[data-marker="${i}"]`, { scale: 2, transformOrigin: "50% 50%" }, { scale: 1, duration: 0.4, ease: "power2.out", transformOrigin: "50% 50%" }, at)
            .fromTo(`[data-chip="${i}"]`, { opacity: 0, scale: 0.6, y: 8, transformOrigin: "50% 100%" }, { opacity: 1, scale: 1, y: 0, duration: 0.4, ease: "back.out(1.8)", transformOrigin: "50% 100%" }, at);
        });
        if (hasPlayed("PESHKAR") && replay === 0) {
          tl.progress(1).pause();
        } else {
          tl.eventCallback("onComplete", () => markPlayed("PESHKAR")).play(0);
        }
        return;
      }

      if (!active) return;
      const tl = gsap.timeline({ repeat: -1, yoyo: true, repeatDelay: 0.05 });
      build(tl);
    },
    { scope: rootRef, dependencies: [mode, active, isStatic, replay, full], revertOnUpdate: true },
  );

  const toneColor = (t: (typeof MARKERS)[number]["tone"]) => p[t];

  return (
    <AgentFrame
      agent="PESHKAR" mode={mode} active={active} statusText={statusText} className={className} surface={surface}
      isStatic={isStatic} viewBox="0 0 300 190" rootRef={rootRef} onReplay={onReplay}
    >
      <defs>
        <linearGradient id={gradId} x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor={p.gold} stopOpacity="0" />
          <stop offset="0.85" stopColor={p.gold} stopOpacity="0.5" />
          <stop offset="1" stopColor={p.gold} stopOpacity="0.95" />
        </linearGradient>
      </defs>

      {/* calendar */}
      <rect x={10} y={10} width={92} height={90} rx={4} fill={p.card} stroke={p.cardLine} strokeWidth={1} />
      <path d="M10 14a4 4 0 0 1 4-4h84a4 4 0 0 1 4 4v10H10z" fill={p.maroon} />
      {[30, 82].map((x) => (
        <rect key={x} x={x - 1.5} y={6} width={3} height={9} rx={1.5} fill={p.gold} />
      ))}
      {[0, 1, 2, 3].flatMap((r) =>
        [0, 1, 2, 3, 4].map((c) => {
          const x = 17 + c * 17;
          const y = 48 + r * 12.5;
          return <rect key={`${r}-${c}`} x={x} y={y} width={14} height={9.5} rx={1.5} fill={p.inkFaint} fillOpacity={0.7} />;
        }),
      )}
      {[[0, 0], [1, 1], [2, 2], [3, 0], [0, 3], [4, 2]].map(([c, r]) => {
        const x = 17 + c * 17;
        const y = 48 + r * 12.5;
        return (
          <path key={`${c}-${r}`} data-tick d={`M${x + 3.5} ${y + 5}l3 3 6-6.5`} stroke={p.neem} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
        );
      })}
      {[2, 1, 0].map((i) => (
        <g key={i} data-leaf={i === 2 ? undefined : i}>
          <rect x={12} y={25} width={88} height={17} rx={2} fill={p.card} stroke={p.cardLine} strokeWidth={0.8} />
          <text x={56} y={37.5} textAnchor="middle" fontSize={11} className="font-display" fill={p.ink}>
            {`Tareekh ${14 + i}`}
          </text>
        </g>
      ))}

      {/* custody bars */}
      {BARS.map((b, i) => {
        const y = 26 + i * 25;
        return (
          <g key={b.label}>
            <text x={124} y={y - 3} fontSize={7} className="font-mono" fill={p.line}>{b.label}</text>
            <rect x={124} y={y} width={166} height={11} rx={5.5} fill={p.faint} />
            <rect data-bar x={124} y={y} width={b.w} height={11} rx={5.5} fill={i === 2 ? p.sindoor : barFill} />
          </g>
        );
      })}

      {/* timeline */}
      <path d={`M${SWEEP_FROM} ${TL_Y}H${SWEEP_TO}`} stroke={p.line} strokeWidth={1.4} strokeLinecap="round" />
      {Array.from({ length: 12 }, (_, i) => (
        <path key={i} d={`M${SWEEP_FROM + i * 25} ${TL_Y - 3}v6`} stroke={p.line} strokeWidth={1} strokeOpacity={0.6} />
      ))}
      {MARKERS.map((m, i) => (
        <circle key={m.x} data-marker={i} cx={m.x} cy={TL_Y} r={4.2} fill={full ? toneColor(m.tone) : p.gold} stroke={p.card} strokeWidth={1.4} />
      ))}
      {full ? (
        <>
          {MARKERS.map((m, i) => {
            const y = m.row === 0 ? 106 : 126;
            const x = Math.min(Math.max(m.x - m.w / 2, 4), 296 - m.w);
            return (
              <g key={m.text} data-chip={i}>
                <path d={`M${m.x} ${y + 14}V${TL_Y - 5}`} stroke={toneColor(m.tone)} strokeWidth={1} strokeDasharray="2 2" />
                <rect x={x} y={y} width={m.w} height={14} rx={7} fill={p.card} stroke={toneColor(m.tone)} strokeWidth={1.2} />
                <circle cx={x + 8} cy={y + 7} r={4.2} fill={toneColor(m.tone)} />
                <text x={x + 8} y={y + 9.4} textAnchor="middle" fontSize={6.4} fontWeight={700} fill="var(--color-cream)">{m.mark}</text>
                <text x={x + 15} y={y + 9.6} fontSize={7} className="font-sans" fill={p.ink}>{m.text}</text>
              </g>
            );
          })}
          <g data-sweep opacity={0}>
            <rect x={-30} y={96} width={30} height={76} fill={`url(#${gradId})`} />
            <path d={`M0 96V172`} stroke={p.gold} strokeWidth={1.6} strokeLinecap="round" />
          </g>
        </>
      ) : null}
    </AgentFrame>
  );
}

export default PeshkarCalendarBars;
