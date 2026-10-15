// ScrollArea: a native scrolling region with thin gold scrollbars. It is focusable when labelled so keyboard users
// can scroll it (WCAG 2.1.1), and it opts out of Lenis smooth scrolling.
import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export interface ScrollAreaProps extends HTMLAttributes<HTMLDivElement> {
  orientation?: "vertical" | "horizontal" | "both";
}

export const ScrollArea = forwardRef<HTMLDivElement, ScrollAreaProps>(function ScrollArea(
  { className, orientation = "vertical", tabIndex, ...props },
  ref,
) {
  const labelled = Boolean(props["aria-label"] || props["aria-labelledby"]);
  return (
    <div
      ref={ref}
      data-lenis-prevent=""
      role={labelled ? (props.role ?? "region") : props.role}
      tabIndex={tabIndex ?? (labelled ? 0 : undefined)}
      className={cn(
        "min-h-0 overscroll-contain",
        orientation === "vertical" && "overflow-y-auto overflow-x-hidden",
        orientation === "horizontal" && "overflow-x-auto overflow-y-hidden",
        orientation === "both" && "overflow-auto",
        className,
      )}
      {...props}
    />
  );
});

export default ScrollArea;
