// Status: an icon and a short word in the status colour, never colour alone. Plain type, no pill, no fill.
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
        "inline-flex items-center gap-1 font-sans font-medium leading-none whitespace-nowrap",
        size === "sm" ? "text-xs" : "text-[13px]",
        solid ? cn(tone.solid, "rounded-sm px-1.5 py-1") : tone.text,
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
