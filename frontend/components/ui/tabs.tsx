"use client";
// Tabs (Radix): keyboard arrows move between tabs. The active tab is marked by one maroon bar under the list that slides
// to the chosen tab (transform only, 275 ms, the spring curve; instant under reduced motion). Until the bar is measured,
// and without JavaScript, the active tab carries its own underline, so the state is never hidden.
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { forwardRef, useCallback, useEffect, useLayoutEffect, useRef, type ComponentPropsWithoutRef, type ElementRef, type ForwardedRef } from "react";
import { cn } from "@/lib/utils";

export const Tabs = TabsPrimitive.Root;

const useIsoLayoutEffect = typeof window === "undefined" ? useEffect : useLayoutEffect;

function assignRef<T>(ref: ForwardedRef<T>, value: T | null): void {
  if (typeof ref === "function") ref(value);
  else if (ref) ref.current = value;
}

export const TabsList = forwardRef<ElementRef<typeof TabsPrimitive.List>, ComponentPropsWithoutRef<typeof TabsPrimitive.List>>(
  function TabsList({ className, children, ...props }, ref) {
    const listRef = useRef<HTMLDivElement | null>(null);
    const barRef = useRef<HTMLSpanElement>(null);
    const placed = useRef(false);

    const place = useCallback(() => {
      const list = listRef.current;
      const bar = barRef.current;
      if (!list || !bar) return;
      const active = list.querySelector<HTMLElement>('[role="tab"][data-state="active"]');
      if (!active) {
        bar.style.opacity = "0";
        return;
      }
      // The first placement does not animate (no slide in from the left edge on page load).
      bar.style.transition = placed.current ? "" : "none";
      bar.style.opacity = "1";
      bar.style.transform = `translateX(${active.offsetLeft}px) scaleX(${active.offsetWidth / 100})`;
      if (!placed.current) {
        placed.current = true;
        list.dataset.indicator = "ready";
        void bar.offsetWidth; // commit the un-animated position before transitions come back
        bar.style.transition = "";
      }
    }, []);

    useIsoLayoutEffect(() => {
      place();
      const list = listRef.current;
      if (!list) return;
      const mo = new MutationObserver(place);
      mo.observe(list, { subtree: true, attributes: true, attributeFilter: ["data-state"] });
      const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(place) : null;
      ro?.observe(list);
      list.querySelectorAll('[role="tab"]').forEach((t) => ro?.observe(t));
      return () => {
        mo.disconnect();
        ro?.disconnect();
      };
    }, [place]);

    return (
      <TabsPrimitive.List
        ref={(el) => {
          listRef.current = el;
          assignRef(ref, el);
        }}
        className={cn("group/tabs relative flex items-end gap-0.5 overflow-x-auto border-b border-line", className)}
        {...props}
      >
        {children}
        <span
          ref={barRef}
          aria-hidden
          data-testid="tab-indicator"
          className="pointer-events-none absolute bottom-0 left-0 h-0.5 w-[100px] origin-left bg-maroon opacity-0 transition-transform duration-[275ms] [transition-timing-function:var(--ease-spring)]"
        />
      </TabsPrimitive.List>
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
        // Once the sliding bar is placed, it marks the active tab instead of the tab's own underline.
        "group-data-[indicator=ready]/tabs:data-[state=active]:border-transparent",
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
