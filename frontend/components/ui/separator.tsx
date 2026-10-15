// Separator: a hairline, or the gold ornament rule. Decorative by default (hidden from assistive tech).
import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export interface SeparatorProps extends HTMLAttributes<HTMLDivElement> {
  orientation?: "horizontal" | "vertical";
  decorative?: boolean;
  variant?: "line" | "gold";
}

export const Separator = forwardRef<HTMLDivElement, SeparatorProps>(function Separator(
  { className, orientation = "horizontal", decorative = true, variant = "line", ...props },
  ref,
) {
  return (
    <div
      ref={ref}
      role={decorative ? "none" : "separator"}
      aria-orientation={decorative ? undefined : orientation}
      className={cn(
        "shrink-0",
        orientation === "horizontal" ? "h-px w-full" : "h-full w-px",
        variant === "line" ? "bg-line" : orientation === "horizontal" ? "gold-rule" : "bg-gold/60",
        className,
      )}
      {...props}
    />
  );
});

export default Separator;
