// Input: white field with a 3:1 border and the maroon focus ring.
import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const fieldClasses =
  "w-full rounded-md border border-line-strong bg-cream px-3 text-sm text-ink placeholder:text-ink-muted transition-colors duration-fast focus-visible:border-maroon focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 disabled:cursor-not-allowed disabled:opacity-60 aria-[invalid=true]:border-sindoor";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, type = "text", ...props },
  ref,
) {
  return <input ref={ref} type={type} className={cn(fieldClasses, "h-9", className)} {...props} />;
});

export default Input;
