// Brand: a V whose arms carry a balance beam (scales and the letter in one stroke), on a maroon square.
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
  return (
    <svg viewBox="0 0 32 32" width={size} height={size} aria-hidden focusable="false" className={cn("shrink-0", className)}>
      <rect width="32" height="32" rx="6" fill={tile} />
      <path d="M9 13.5 16 25l7-11.5" fill="none" stroke={glyph} strokeWidth="3.2" strokeLinejoin="miter" />
      <path d="M7.5 8.25h17" fill="none" stroke={glyph} strokeWidth="2.6" />
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
