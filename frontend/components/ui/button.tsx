// Button (shadcn-style, themed with the Manuscript tokens, plan §13.2). Variants include the Hugh James pairing:
// a pill button ("Watch the journey") and a round play button. Every variant keeps a visible focus ring.
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { Play } from "lucide-react";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex select-none items-center justify-center gap-2 whitespace-nowrap font-sans font-semibold transition-[transform,opacity,background-color,color,border-color] duration-fast ease-standard focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-offset-2 disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none aria-disabled:opacity-50 active:translate-y-px [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        /** Maroon fill: the primary action (Open a case, Approve). */
        primary: "rounded-md bg-maroon text-cream hover:bg-maroon-deep",
        /** Outline on parchment. */
        secondary: "rounded-md border border-maroon/70 bg-cream text-maroon hover:bg-parchment-deep",
        /** Quiet text button. */
        ghost: "rounded-md text-ink hover:bg-ink/[0.06]",
        /** Link look. */
        link: "rounded-sm text-maroon underline-offset-4 hover:underline",
        /** Destructive or blocking actions. */
        danger: "rounded-md bg-sindoor text-cream hover:opacity-90",
        /** The Hugh James pill (e.g. "Watch the journey"). */
        pill: "rounded-pill border border-maroon bg-cream text-maroon hover:bg-maroon hover:text-cream",
        /** Pill on oxblood / maroon blocks. */
        "pill-dark": "rounded-pill border border-gold-pale/80 bg-transparent text-cream hover:bg-cream hover:text-oxblood",
        /** The round play button that pairs with the pill. */
        play: "rounded-full bg-maroon text-cream hover:bg-maroon-deep",
        /** Gold-on-oxblood for dark bands (gold text only on oxblood, plan §13.2). */
        gold: "rounded-md bg-oxblood text-gold-pale ring-1 ring-gold/60 hover:bg-maroon-deep",
      },
      size: {
        sm: "h-8 px-3 text-sm",
        md: "h-10 px-4 text-sm",
        lg: "h-12 px-6 text-base",
        icon: "size-10 p-0",
        "icon-sm": "size-8 p-0",
        round: "size-12 p-0 [&_svg]:size-5",
      },
    },
    compoundVariants: [
      { variant: "play", size: ["sm", "md", "lg"], className: "aspect-square px-0" },
      { variant: "pill", size: "lg", className: "px-7" },
    ],
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  /** Render the child element (e.g. a Next <Link>) with the button styles. */
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, asChild = false, type, ...props },
  ref,
) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      {...(asChild ? {} : { type: type ?? "button" })}
      {...props}
    />
  );
});

export interface PlayButtonProps extends Omit<ButtonProps, "variant" | "children"> {
  /** Accessible name, e.g. "Watch the journey". */
  label: string;
}

/** The round play button (Hugh James), with an accessible name. */
export const PlayButton = forwardRef<HTMLButtonElement, PlayButtonProps>(function PlayButton(
  { label, size = "round", className, ...props },
  ref,
) {
  return (
    <Button ref={ref} variant="play" size={size} aria-label={label} title={label} className={className} {...props}>
      <Play aria-hidden="true" className="translate-x-[1px] fill-current" />
    </Button>
  );
});

export default Button;
