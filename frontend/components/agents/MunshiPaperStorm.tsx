"use client";
// Munshi: page cards flip and gain route badges (TEXT, LAYOUT, OCR, VISION) and a document-type stamp; the full version
// flies the pages onto the four shelves (plan §13.4). Own SVG, GSAP in useGSAP only, transform and opacity only.
import { useRef, type ReactElement } from "react";
import { SHELF_META, SHELF_ORDER } from "@/lib/stores";
import { registerMotion, useGSAP } from "@/lib/motion/register";
import {
  AgentFrame, PALETTE, type TL, hasPlayed, markPlayed, useIsStatic, useReplay, type AgentArtProps,
} from "./shared";

export type MunshiPaperStormProps = AgentArtProps;

const ROUTES = ["TEXT", "LAYOUT", "OCR", "VISION"] as const;
const STAMPS = ["FIR", "ORDER", "MEMO", "AFFD."] as const;
const PAGE_X = [14, 82, 150, 218] as const;
const ORIGIN = "50% 50%";

export function MunshiPaperStorm({ mode, active, statusText, className, surface = "light" }: MunshiPaperStormProps): ReactElement {
  const rootRef = useRef<HTMLDivElement>(null);
  const isStatic = useIsStatic(mode);
  const [replay, onReplay] = useReplay();
  const p = PALETTE[surface];

  useGSAP(
    () => {
      if (isStatic) return;
      const gsap = registerMotion();
      const page = (i: number) => `[data-page="${i}"]`;
      const tag = (i: number) => `[data-page="${i}"] [data-tag]`;
      const stamp = (i: number) => `[data-page="${i}"] [data-stamp]`;

      /** Flip a page edge-on, show its badge and stamp, flip back. */
      const flip = (tl: TL, i: number, at: number) => {
        tl.fromTo(page(i), { scaleX: 1 }, { scaleX: 0.06, duration: 0.14, ease: "power1.in", transformOrigin: ORIGIN }, at)
          .fromTo(tag(i), { opacity: 0 }, { opacity: 1, duration: 0.01 }, at + 0.14)
          .to(page(i), { scaleX: 1, duration: 0.16, ease: "power1.out", transformOrigin: ORIGIN }, at + 0.14)
          .fromTo(
            stamp(i),
            { scale: 1.7, opacity: 0, transformOrigin: ORIGIN },
            { scale: 1, opacity: 1, duration: 0.18, ease: "back.out(2)", transformOrigin: ORIGIN },
            at + 0.3,
          );
      };

      if (mode === "full") {
        const tl = gsap.timeline({ paused: true });
        const tilt = [-24, 18, -12, 26];
        PAGE_X.forEach((_, i) => {
          tl.from(page(i), { y: -70, x: (i - 1.5) * -26, rotation: tilt[i], opacity: 0, duration: 0.5, ease: "power3.out", transformOrigin: ORIGIN }, i * 0.08);
        });
        PAGE_X.forEach((_, i) => flip(tl, i, 0.7 + i * 0.12));
        PAGE_X.forEach((_, i) => {
          const at = 1.7 + i * 0.1;
          tl.to(page(i), { y: 93, scale: 0.55, duration: 0.55, ease: "power2.inOut", transformOrigin: ORIGIN }, at)
            .fromTo(`[data-glow="${i}"]`, { opacity: 0 }, { opacity: 0.8, duration: 0.15 }, at + 0.5)
            .to(`[data-glow="${i}"]`, { opacity: 0, duration: 0.4 }, at + 0.65);
        });
        if (hasPlayed("MUNSHI") && replay === 0) {
          tl.progress(1).pause();
        } else {
          tl.eventCallback("onComplete", () => markPlayed("MUNSHI")).play(0);
        }
        return;
      }

      if (!active) return;
      const tl = gsap.timeline({ repeat: -1, repeatDelay: 0.1 });
      PAGE_X.forEach((_, i) => flip(tl, i, i * 0.3));
      tl.to("[data-tag]", { opacity: 0, duration: 0.25, ease: "power1.in" }, 1.5);
    },
    { scope: rootRef, dependencies: [mode, active, isStatic, replay], revertOnUpdate: true },
  );

  return (
    <AgentFrame
      agent="MUNSHI" mode={mode} active={active} statusText={statusText} className={className} surface={surface}
      isStatic={isStatic} viewBox="0 0 280 178" rootRef={rootRef} onReplay={onReplay}
    >
      {SHELF_ORDER.map((shelf, i) => {
        const x = PAGE_X[i];
        return (
          <g key={shelf}>
            <rect x={x} y={112} width={52} height={46} rx={2} fill={p.faint} fillOpacity={0.35} />
            <rect data-glow={i} x={x - 2} y={110} width={56} height={50} rx={3} stroke={p.gold} strokeWidth={2} opacity={0} />
            <path d={`M${x} 112V158H${x + 52}V112`} stroke={p.line} strokeWidth={1.4} strokeLinecap="round" strokeLinejoin="round" />
            <path d={`M${x - 3} 158H${x + 55}`} stroke={p.gold} strokeWidth={2.4} strokeLinecap="round" />
            <text x={x + 26} y={172} textAnchor="middle" fontSize={8} className="font-mono" fill={p.line}>
              {SHELF_META[shelf].label}
            </text>
          </g>
        );
      })}
      {PAGE_X.map((x, i) => (
        <g key={x} data-page={i}>
          <rect x={x} y={10} width={52} height={64} rx={2.5} fill={p.card} stroke={p.cardLine} strokeWidth={1} />
          <path d={`M${x + 40} 10v10h12`} stroke={p.cardLine} strokeWidth={0.8} />
          {[0, 1, 2, 3].map((k) => (
            <rect key={k} x={x + 8} y={30 + k * 7} width={36 - (k % 2) * 9} height={2} rx={1} fill={p.inkFaint} />
          ))}
          <g data-tag>
            <rect x={x + 5} y={13} width={ROUTES[i].length * 4.2 + 8} height={10} rx={5} fill={p.maroon} />
            <text x={x + 5 + (ROUTES[i].length * 4.2 + 8) / 2} y={20.2} textAnchor="middle" fontSize={6.2} className="font-mono" fill="var(--color-cream)">
              {ROUTES[i]}
            </text>
            <g data-stamp>
              <g transform={`rotate(-11 ${x + 34} 62)`}>
                <rect x={x + 20} y={55} width={28} height={13} rx={2} stroke={p.maroon} strokeWidth={1.2} />
                <text x={x + 34} y={64} textAnchor="middle" fontSize={6.4} fontWeight={700} className="font-mono" fill={p.maroon}>
                  {STAMPS[i]}
                </text>
              </g>
            </g>
          </g>
        </g>
      ))}
    </AgentFrame>
  );
}

export default MunshiPaperStorm;
