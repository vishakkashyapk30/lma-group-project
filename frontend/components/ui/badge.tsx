// Badge: a small label. Quiet by default: normal type, a hairline, no fill. Statuses use components/common/StatusBadge.
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const badgeVariants = cva(
  "inline-flex max-w-full items-center gap-1 whitespace-nowrap rounded-sm font-sans leading-none [&_svg]:size-3 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "border border-line-strong/50 text-ink-soft",
        solid: "bg-maroon text-cream",
        outline: "border border-line-strong/50 text-ink-soft",
        muted: "bg-parchment-deep text-ink-soft",
        /** Ids and citations in the mono face. */
        mono: "border border-line bg-cream font-mono text-ink-soft",
        gold: "bg-oxblood text-gold-pale",
        neem: "text-neem",
        indigo: "text-indigo",
        sindoor: "text-sindoor",
        haldi: "text-haldi",
        clay: "text-clay",
      },
      size: {
        sm: "h-5 px-1.5 text-2xs",
        md: "h-6 px-2 text-xs",
        lg: "h-7 px-2.5 text-sm",
      },
      shape: {
        default: "",
        pill: "",
      },
    },
    defaultVariants: { variant: "default", size: "md", shape: "default" },
  },
);

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(function Badge({ className, variant, size, shape, ...props }, ref) {
  return <span ref={ref} className={cn(badgeVariants({ variant, size, shape }), className)} {...props} />;
});

export default Badge;
