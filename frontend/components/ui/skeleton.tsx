// Skeleton: loading placeholder. Opacity pulse only (transform/opacity rule), static under reduced motion.
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden="true" className={cn("animate-breathe rounded-md bg-parchment-deep", className)} {...props} />;
}

/** A few lines of skeleton text with an accessible "Loading" status. */
export function SkeletonText({ lines = 3, label = "Loading", className }: { lines?: number; label?: string; className?: string }) {
  return (
    <div role="status" className={cn("flex flex-col gap-2", className)}>
      <span className="sr-only">{label}</span>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={cn("h-3.5", i === lines - 1 ? "w-2/3" : "w-full")} />
      ))}
    </div>
  );
}

export default Skeleton;
