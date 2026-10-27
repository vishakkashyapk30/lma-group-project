// Brand: a V whose arms meet a balance beam with two short hangers and pans, so the letter and the scales are one figure,
// on a maroon square. Below 24 px the hangers and pans would blur, so the mark drops them and keeps the V and the beam.
// Source of truth for the artwork is public/brand/*.svg; this component draws the same geometry inline.
import type { ReactElement } from "react";
import { cn } from "@/lib/utils";

export interface BandsMarkProps {
  size?: number;
  className?: string;
  /** "solid": cream glyph on maroon (default). "reversed": maroon glyph on cream, for dark backgrounds. */
  tone?: "solid" | "reversed";
}

export function BandsMark({ size = 28, className, tone = "solid" }: BandsMarkProps): ReactElement {
  const tile = tone === "solid" ? "var(--color-maroon)" : "var(--color-cream)";
  const glyph = tone === "solid" ? "var(--color-cream)" : "var(--color-maroon)";
  const small = size < 24;
  return (
    <svg viewBox="0 0 32 32" width={size} height={size} aria-hidden focusable="false" data-mark={small ? "small" : "full"} className={cn("shrink-0", className)}>
      <rect width="32" height="32" rx="6" fill={tile} />
      {small ? (
        <>
          <path d="M10 9.5 16 25l6-15.5" fill="none" stroke={glyph} strokeWidth="3.4" strokeLinejoin="miter" />
          <path d="M6 9.5h20" fill="none" stroke={glyph} strokeWidth="2.6" />
        </>
      ) : (
        <>
          <path d="M10.4 9.5 16 24.5 21.6 9.5" fill="none" stroke={glyph} strokeWidth="3" strokeLinejoin="miter" />
          <path d="M5.2 9.5h21.6" fill="none" stroke={glyph} strokeWidth="2.2" />
          <path d="M7.2 9.5v3.6M24.8 9.5v3.6" fill="none" stroke={glyph} strokeWidth="1.4" />
          <path d="M4.3 13.1h5.8a2.9 2.4 0 0 1-5.8 0ZM21.9 13.1h5.8a2.9 2.4 0 0 1-5.8 0Z" fill={glyph} />
        </>
      )}
    </svg>
  );
}

export function Logo({ className, markOnly = false, tone = "solid" }: { className?: string; markOnly?: boolean; tone?: "solid" | "reversed" }): ReactElement {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <BandsMark tone={tone} />
      {markOnly ? (
        <span className="sr-only">Vakeel-Sahayak</span>
      ) : (
        <span className={cn("font-display text-[18px] font-semibold leading-none", tone === "solid" ? "text-ink" : "text-cream")}>Vakeel-Sahayak</span>
      )}
    </span>
  );
}

export default Logo;
