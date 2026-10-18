// A stylised 24-spoke wheel (plan §13.2). Ours: ringed rim with bead tips, slim spokes, lotus hub. It is deliberately not
// the State Emblem's chakra and not the flag's. Spokes are addressable (data-spoke 0..23) for lighting and for the
// wheel-to-bars transition. Decorative: aria-hidden.
import type { ReactElement, Ref } from "react";
import { TONE_COLOR, type ArtTone } from "./tone";

export const WHEEL_SPOKES = 24;

export interface Wheel24Props {
  className?: string;
  svgRef?: Ref<SVGSVGElement>;
  /** Static rotation in degrees. */
  rotation?: number;
  /** Lit spokes: a count (first n, from the top, clockwise) or explicit indices. */
  lit?: number | readonly number[];
  /** Colour of lit spokes (default gold-pale). */
  litTone?: ArtTone;
  tone?: ArtTone;
  strokeWidth?: number;
  /** Draw the rim and hub only (the spokes are drawn elsewhere, e.g. falling bars). */
  hideSpokes?: boolean;
}

const spokes = Array.from({ length: WHEEL_SPOKES }, (_, i) => {
  const a = ((i * 360) / WHEEL_SPOKES - 90) * (Math.PI / 180);
  const p = (r: number) => [Number((r * Math.cos(a)).toFixed(2)), Number((r * Math.sin(a)).toFixed(2))] as const;
  const [x1, y1] = p(17);
  const [x2, y2] = p(83);
  const [bx, by] = p(89);
  return { i, x1, y1, x2, y2, bx, by };
});

export function Wheel24({
  className,
  svgRef,
  rotation = 0,
  lit,
  litTone = "gold-pale",
  tone = "gold",
  strokeWidth = 1,
  hideSpokes = false,
}: Wheel24Props): ReactElement {
  const litSet = new Set<number>(typeof lit === "number" ? Array.from({ length: Math.max(0, Math.min(WHEEL_SPOKES, lit)) }, (_, i) => i) : (lit ?? []));
  return (
    <svg
      ref={svgRef}
      viewBox="-102 -102 204 204"
      className={className}
      style={{ color: TONE_COLOR[tone], overflow: "visible" }}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      aria-hidden
      focusable="false"
    >
      <g data-wheel-rotor style={{ transform: `rotate(${rotation}deg)`, transformOrigin: "0 0" }}>
        <circle data-part="rim" r="100" />
        <circle data-part="rim-inner" r="94" strokeWidth={strokeWidth * 0.6} />
        {!hideSpokes &&
          spokes.map((s) => {
            const on = litSet.has(s.i);
            return (
              <g key={s.i} data-spoke={s.i} data-lit={on ? "true" : "false"} style={on ? { color: TONE_COLOR[litTone] } : undefined}>
                <line x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2} strokeWidth={on ? strokeWidth * 1.8 : strokeWidth} />
                <circle cx={s.bx} cy={s.by} r={on ? 2.6 : 1.7} fill="currentColor" stroke="none" />
              </g>
            );
          })}
        <circle data-part="hub" r="14" />
        <circle r="5" fill="currentColor" stroke="none" fillOpacity="0.8" />
        <path data-part="lotus" d="M0 -14C5 -9 5 -4 0 0C-5 -4 -5 -9 0 -14ZM14 0C9 5 4 5 0 0C4 -5 9 -5 14 0ZM0 14C-5 9 -5 4 0 0C5 4 5 9 0 14ZM-14 0C-9 -5 -4 -5 0 0C-4 5 -9 5 -14 0Z" strokeWidth={strokeWidth * 0.6} />
      </g>
    </svg>
  );
}

export default Wheel24;
