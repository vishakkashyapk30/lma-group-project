"use client";
// Reveal on scroll: children marked data-rv (with --i for the stagger) rise and fade in once, 40 ms apart, when the band
// scrolls into view. Bands that start on screen are left alone, and everything is visible without JavaScript and under
// reduced motion (styles/landing.css).
import { useEffect, useRef, type ElementType, type ReactElement, type ReactNode } from "react";

export function Reveal({ children, as: Tag = "div", className }: { children: ReactNode; as?: ElementType; className?: string }): ReactElement {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    if (el.getBoundingClientRect().top < window.innerHeight * 0.85) return; // already on screen: leave it alone
    el.dataset.rvState = "pending";
    const io = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        el.dataset.rvState = "shown";
        io.disconnect();
      },
      { rootMargin: "0px 0px -12% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return <Tag ref={ref} className={className}>{children}</Tag>;
}
