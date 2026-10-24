"use client";
// Tabs (Radix): keyboard arrows move between tabs; the active tab gets a maroon underline.
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { forwardRef, type ComponentPropsWithoutRef, type ElementRef } from "react";
import { cn } from "@/lib/utils";

export const Tabs = TabsPrimitive.Root;

export const TabsList = forwardRef<ElementRef<typeof TabsPrimitive.List>, ComponentPropsWithoutRef<typeof TabsPrimitive.List>>(
  function TabsList({ className, ...props }, ref) {
    return (
      <TabsPrimitive.List
        ref={ref}
        className={cn("flex items-end gap-0.5 overflow-x-auto border-b border-line", className)}
        {...props}
      />
    );
  },
);

export const TabsTrigger = forwardRef<
  ElementRef<typeof TabsPrimitive.Trigger>,
  ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(function TabsTrigger({ className, ...props }, ref) {
  return (
    <TabsPrimitive.Trigger
      ref={ref}
      className={cn(
        "relative -mb-px inline-flex h-10 items-center gap-1.5 whitespace-nowrap border-b-2 border-transparent px-3 font-sans text-sm font-medium text-ink-soft transition-colors duration-fast",
        "hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2",
        "data-[state=active]:border-maroon data-[state=active]:font-semibold data-[state=active]:text-maroon",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
});

export const TabsContent = forwardRef<
  ElementRef<typeof TabsPrimitive.Content>,
  ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(function TabsContent({ className, ...props }, ref) {
  return <TabsPrimitive.Content ref={ref} className={cn("focus-visible:outline-offset-[-2px]", className)} {...props} />;
});

export default Tabs;
