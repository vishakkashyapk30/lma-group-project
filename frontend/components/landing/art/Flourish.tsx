// Hand-authored calligraphy flourishes (plan §13.3, scene 1): paths meant to be drawn with DrawSVG. Decorative.
import type { ReactElement, Ref } from "react";
import { TONE_COLOR, type ArtTone } from "./tone";

export type FlourishVariant = "swash" | "divider" | "underline";

export interface CalligraphyFlourishProps {
  className?: string;
  svgRef?: Ref<SVGSVGElement>;
  variant?: FlourishVariant;
  tone?: ArtTone;
  strokeWidth?: number;
}

const PATHS: Record<FlourishVariant, { viewBox: string; d: string[] }> = {
  swash: {
    viewBox: "0 0 400 60",
    d: [
      "M8 38C60 38 90 12 130 14C158 16 160 40 138 42C118 44 112 26 134 22C170 16 200 40 240 38C290 36 330 10 392 22",
      "M240 38C262 48 292 50 316 40",
    ],
  },
  divider: {
    viewBox: "0 0 400 40",
    d: [
      "M6 20H170M230 20H394",
      "M170 20C178 8 190 8 200 20C210 32 222 32 230 20",
      "M200 12V28M192 20H208",
    ],
  },
  underline: {
    viewBox: "0 0 300 24",
    d: ["M4 16C60 6 110 6 150 12C200 19 250 18 296 6", "M60 21C110 15 190 16 240 20"],
  },
};

export function CalligraphyFlourish({ className, svgRef, variant = "swash", tone = "gold-pale", strokeWidth = 1.6 }: CalligraphyFlourishProps): ReactElement {
  const v = PATHS[variant];
  return (
    <svg
      ref={svgRef}
      viewBox={v.viewBox}
      className={className}
      style={{ color: TONE_COLOR[tone] }}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      focusable="false"
      preserveAspectRatio="xMidYMid meet"
    >
      {v.d.map((d, i) => (
        <path key={i} data-draw d={d} />
      ))}
    </svg>
  );
}

export default CalligraphyFlourish;
