// Badge: small label chip. For statuses use components/common/StatusBadge (icon + label + colour, plan §13.2).
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const badgeVariants = cva(
  "inline-flex max-w-full items-center gap-1 whitespace-nowrap rounded-sm border font-sans font-semibold leading-none [&_svg]:size-3 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "border-maroon/40 bg-maroon/[0.06] text-maroon",
        solid: "border-maroon bg-maroon text-cream",
        outline: "border-line-strong/70 bg-transparent text-ink-soft",
        muted: "border-line bg-parchment-deep text-ink-soft",
        /** Route badges and IDs in IBM Plex Mono. */
        mono: "border-line-strong/60 bg-cream font-mono font-medium tracking-tight text-ink",
        /** Gold text on oxblood only (plan §13.2). */
        gold: "border-gold/60 bg-oxblood text-gold-pale",
        neem: "border-neem/50 bg-neem/[0.07] text-neem",
        indigo: "border-indigo/45 bg-indigo/[0.06] text-indigo",
        sindoor: "border-sindoor/50 bg-sindoor/[0.06] text-sindoor",
        haldi: "border-haldi/50 bg-haldi/[0.07] text-haldi",
        clay: "border-clay/50 bg-clay/[0.07] text-clay",
      },
      size: {
        sm: "h-5 px-1.5 text-2xs",
        md: "h-6 px-2 text-xs",
        lg: "h-7 px-2.5 text-sm",
      },
      shape: {
        default: "",
        pill: "rounded-pill",
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
