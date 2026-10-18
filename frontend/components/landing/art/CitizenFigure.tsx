// A simple citizen: a circle and a rounded block (plan §13.3, scene 2). Deliberately anonymous: no face, no photo.
import type { ReactElement, Ref } from "react";
import { TONE_COLOR, type ArtTone } from "./tone";

export interface CitizenFigureProps {
  className?: string;
  svgRef?: Ref<SVGSVGElement>;
  tone?: ArtTone;
  /** Solid fill (default) or outline only. */
  outline?: boolean;
  title?: string;
}

export function CitizenFigure({ className, svgRef, tone = "maroon", outline = false, title }: CitizenFigureProps): ReactElement {
  return (
    <svg
      ref={svgRef}
      viewBox="0 0 120 200"
      className={className}
      style={{ color: TONE_COLOR[tone] }}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      focusable="false"
    >
      <circle data-part="head" cx="60" cy="42" r="26" fill={outline ? "none" : "currentColor"} />
      <rect data-part="body" x="22" y="78" width="76" height="116" rx="34" fill={outline ? "none" : "currentColor"} />
    </svg>
  );
}

export default CitizenFigure;
