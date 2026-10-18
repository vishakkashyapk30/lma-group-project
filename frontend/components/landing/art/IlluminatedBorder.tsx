// Own SVG illuminated border in the manuscript style (plan §13.2): a double gold rule, four corner ornaments and
// optional header/footer slots, over an optional jaali lattice. Content goes in the padded middle. Decorative parts
// are aria-hidden; children stay real text.
import type { ReactElement, ReactNode } from "react";
import { cn } from "@/lib/utils";
import { TONE_COLOR, type ArtTone } from "./tone";

export interface IlluminatedBorderProps {
  className?: string;
  /** Content inside the frame. */
  children?: ReactNode;
  /** Slot centred on the top rule (e.g. a small title). */
  header?: ReactNode;
  /** Slot centred on the bottom rule. */
  footer?: ReactNode;
  tone?: ArtTone;
  /** Corner ornament size in px. */
  ornamentSize?: number;
  /** Show the jaali lattice behind the content. */
  jaali?: boolean;
  /** Background colour class for the panel and the slots (so slots can cut the rule). */
  panelClassName?: string;
  /** Classes for the content wrapper. */
  contentClassName?: string;
}

/** One corner ornament (top-left); mirrored for the other corners. */
export function CornerOrnament({ size = 72, className }: { size?: number; className?: string }): ReactElement {
  return (
    <svg viewBox="0 0 72 72" width={size} height={size} className={className} fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" aria-hidden focusable="false">
      <path data-draw d="M4 68V16C4 9 9 4 16 4H68" strokeWidth="1.6" />
      <path data-draw d="M10 68V18C10 13.5 13.5 10 18 10H68" strokeWidth="0.8" />
      <path data-draw d="M14 14C26 14 34 22 34 34C34 22 42 14 54 14" strokeWidth="1" />
      <path data-draw d="M14 14C14 26 22 34 34 34C22 34 14 42 14 54" strokeWidth="1" />
      <circle data-draw cx="34" cy="34" r="4" strokeWidth="1" />
      <path data-draw d="M34 34L44 44M44 44C48 48 54 46 52 40C50 36 44 38 44 44" strokeWidth="1" />
      <circle cx="14" cy="14" r="2.4" fill="currentColor" stroke="none" />
      <path data-draw d="M22 4C22 12 16 14 10 14M4 22C12 22 14 16 14 10" strokeWidth="0.8" />
    </svg>
  );
}

export function IlluminatedBorder({
  className,
  children,
  header,
  footer,
  tone = "gold",
  ornamentSize = 72,
  jaali = false,
  panelClassName = "bg-cream",
  contentClassName,
}: IlluminatedBorderProps): ReactElement {
  const corner = "absolute";
  return (
    <div className={cn("relative", panelClassName, className)} style={{ ["--ib-pad" as string]: `${Math.round(ornamentSize * 0.55)}px` }}>
      <div aria-hidden className="pointer-events-none absolute inset-0" style={{ color: TONE_COLOR[tone] }}>
        <div className="absolute inset-2 border border-current" />
        <div className="absolute inset-[14px] border border-current opacity-60" />
        {jaali ? <div className="bg-jaali absolute inset-[18px] opacity-70" /> : null}
        <CornerOrnament size={ornamentSize} className={cn(corner, "left-1 top-1")} />
        <CornerOrnament size={ornamentSize} className={cn(corner, "right-1 top-1 -scale-x-100")} />
        <CornerOrnament size={ornamentSize} className={cn(corner, "bottom-1 left-1 -scale-y-100")} />
        <CornerOrnament size={ornamentSize} className={cn(corner, "bottom-1 right-1 -scale-100")} />
      </div>
      {header ? (
        <div className={cn("absolute left-1/2 top-2 z-10 -translate-x-1/2 -translate-y-1/2 px-4", panelClassName)}>{header}</div>
      ) : null}
      {footer ? (
        <div className={cn("absolute bottom-2 left-1/2 z-10 -translate-x-1/2 translate-y-1/2 px-4", panelClassName)}>{footer}</div>
      ) : null}
      <div className={cn("relative z-[1] p-[calc(var(--ib-pad)+1.25rem)]", contentClassName)}>{children}</div>
    </div>
  );
}

export default IlluminatedBorder;
