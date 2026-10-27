"use client";
// Focus after a navigation (docs/handoff/frontend-endeavours-ideation.md section 6): when the sidebar, the drawer, the
// command palette or the logo moves to another page, focus goes to that page's h1, so a keyboard or screen-reader user
// starts at the top of the new content instead of on a link that is no longer relevant. Next's route announcer still
// reads the title. Navigations from inside a page (a case card, a button) keep the browser's default.
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

let pending = false;

/** Call from a navigation control (sidebar link, palette entry, logo) just before it navigates. */
export function markRouteFocus(): void {
  pending = true;
}

function focusHeading(): boolean {
  const h1 = document.querySelector<HTMLElement>("#main h1");
  if (!h1) return false;
  if (!h1.hasAttribute("tabindex")) h1.setAttribute("tabindex", "-1");
  h1.dataset.routeFocus = "";
  h1.focus({ preventScroll: true });
  return document.activeElement === h1;
}

export function useRouteFocus(): void {
  const path = usePathname();
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (!pending) return;
    pending = false;
    if (focusHeading()) return;
    // The case workspace renders in the browser after a short load: wait for its heading (at most 3 s).
    const mo = new MutationObserver(() => {
      if (focusHeading()) mo.disconnect();
    });
    mo.observe(document.body, { childList: true, subtree: true });
    const t = window.setTimeout(() => mo.disconnect(), 3000);
    return () => {
      mo.disconnect();
      window.clearTimeout(t);
    };
  }, [path]);
}
