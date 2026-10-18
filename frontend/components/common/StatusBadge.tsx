// Status chip: icon + label + colour from lib/status.ts, never colour alone (plan §13.2).
import type { ReactElement } from "react";
import { cn } from "@/lib/utils";
import { getStatusMeta, TONE_CLASSES, type StatusKind } from "@/lib/status";

export interface StatusIconProps {
  /** The text icon from StatusMeta.icon (✔ ƒ ✖ ? ✎ ...). */
  icon: string;
  className?: string;
}

/** The status icon: a text glyph (plan §13.2), decorative because the label always sits beside it. */
export function StatusIcon({ icon, className }: StatusIconProps): ReactElement {
  return (
    <span aria-hidden className={cn("inline-block min-w-3.5 shrink-0 text-center font-sans text-xs leading-none", className)}>
      {icon}
    </span>
  );
}

export interface StatusBadgeProps {
  status: string;
  /** Disambiguates shared names (OK, UNKNOWN, NEW ...). */
  kind?: StatusKind;
  /** Override the visible label. */
  label?: string;
  /** Optional extra text after the label (for example "3 days"). */
  detail?: string;
  size?: "sm" | "md";
  /** Solid fill for emphasis. */
  solid?: boolean;
  /** data-testid; secondary badges next to a primary status pass another id so "the" status badge stays unique. */
  testId?: string;
  className?: string;
}

export function StatusBadge({ status, kind, label, detail, size = "md", solid = false, testId = "status-badge", className }: StatusBadgeProps): ReactElement {
  const meta = getStatusMeta(status, kind);
  const tone = TONE_CLASSES[meta.tone];
  return (
    <span
      data-testid={testId}
      title={meta.description}
      data-status={status}
      className={cn(
        "inline-flex items-center gap-1 rounded-pill border font-sans font-semibold leading-none whitespace-nowrap",
        size === "sm" ? "px-1.5 py-[3px] text-[11px]" : "px-2 py-1 text-xs",
        solid ? cn(tone.solid, "border-transparent") : cn(tone.text, tone.border, tone.bg),
        className,
      )}
    >
      <StatusIcon icon={meta.icon} />
      {" "}
      <span>{label ?? meta.label}</span>
      {detail ? <span className="font-normal">{detail}</span> : null}
    </span>
  );
}

export default StatusBadge;
