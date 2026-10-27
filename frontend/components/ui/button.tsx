// Button: maroon is the one accent and is reserved for the primary action. Everything else is quiet. Pressing scales it to
// 0.97 in 100 ms and it springs back on release (`.press`, app/globals.css; DESIGN.md "Press feedback").
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "press inline-flex select-none items-center justify-center gap-2 whitespace-nowrap rounded-md font-sans font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none aria-disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        /** The primary action (New case, Approve). One per view. */
        primary: "bg-maroon text-cream hover:bg-maroon-deep",
        /** Bordered, neutral. */
        secondary: "border border-line-strong/70 bg-cream text-ink hover:bg-parchment-deep",
        /** Bordered, neutral; kept for older call sites. */
        pill: "border border-line-strong/70 bg-cream text-ink hover:bg-parchment-deep",
        /** Quiet text button. */
        ghost: "text-ink-soft hover:bg-ink/[0.06] hover:text-ink",
        /** Link look. */
        link: "rounded-sm text-maroon underline-offset-4 hover:underline",
        /** Destructive or blocking actions. */
        danger: "bg-sindoor text-cream hover:opacity-90",
      },
      size: {
        sm: "h-8 px-3 text-sm",
        md: "h-9 px-3.5 text-sm",
        lg: "h-11 px-5 text-base",
        icon: "size-9 p-0",
        "icon-sm": "size-8 p-0",
      },
    },
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

export default Button;
