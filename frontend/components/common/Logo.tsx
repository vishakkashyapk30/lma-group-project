// Brand lockup: वकील सहायक above "Vakeel-Sahayak", with an advocate's-bands mark (two white bands on a black gown collar).
import type { ReactElement } from "react";
import { cn } from "@/lib/utils";

export function BandsMark({ size = 28, className }: { size?: number; className?: string }): ReactElement {
  return (
    <svg viewBox="0 0 32 32" width={size} height={size} aria-hidden focusable="false" className={cn("shrink-0", className)}>
      <rect x="1.5" y="1.5" width="29" height="29" rx="4" fill="var(--color-oxblood)" stroke="var(--color-gold-leaf)" />
      <path d="M8 6h6v20L11 23 8 26z" fill="var(--color-cream)" />
      <path d="M18 6h6v20l-3-3-3 3z" fill="var(--color-cream)" />
    </svg>
  );
}

export function Logo({ className }: { className?: string }): ReactElement {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <BandsMark />
      <span className="flex flex-col leading-none">
        <span lang="hi" className="font-devanagari text-[15px] leading-tight text-maroon">वकील सहायक</span>
        <span className="font-display text-[17px] font-semibold tracking-tight text-ink">Vakeel-Sahayak</span>
      </span>
    </span>
  );
}

export default Logo;
