// Card: a white panel with a hairline border. No shadow; use sparingly, prefer dividers inside a page.
import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const Card = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement> & { tone?: "cream" | "parchment" | "oxblood" }>(
  function Card({ className, tone = "cream", ...props }, ref) {
    return (
      <div
        ref={ref}
        data-surface={tone === "oxblood" ? "dark" : undefined}
        className={cn(
          "rounded-lg border",
          tone === "cream" && "border-line bg-cream text-ink",
          tone === "parchment" && "border-line bg-parchment-deep text-ink",
          tone === "oxblood" && "border-oxblood bg-oxblood text-cream",
          className,
        )}
        {...props}
      />
    );
  },
);

export const CardHeader = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(function CardHeader({ className, ...props }, ref) {
  return <div ref={ref} className={cn("flex flex-col gap-1 p-4 pb-2", className)} {...props} />;
});

export const CardTitle = forwardRef<HTMLHeadingElement, HTMLAttributes<HTMLHeadingElement> & { as?: "h2" | "h3" | "h4" }>(
  function CardTitle({ className, as: Tag = "h3", ...props }, ref) {
    return <Tag ref={ref} className={cn("font-display text-lg font-semibold leading-snug text-ink", className)} {...props} />;
  },
);

export const CardDescription = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(function CardDescription(
  { className, ...props },
  ref,
) {
  return <p ref={ref} className={cn("text-sm text-ink-soft", className)} {...props} />;
});

export const CardContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(function CardContent({ className, ...props }, ref) {
  return <div ref={ref} className={cn("p-4 pt-2", className)} {...props} />;
});

export const CardFooter = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(function CardFooter({ className, ...props }, ref) {
  return <div ref={ref} className={cn("flex items-center gap-2 border-t border-line p-4 pt-3", className)} {...props} />;
});

export default Card;
