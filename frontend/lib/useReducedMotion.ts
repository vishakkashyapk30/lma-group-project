// prefers-reduced-motion hook (plan §13.4, §13.7): with reduced motion every animation becomes a static icon with a text
// status and the landing becomes a static storyboard. A manual override (localStorage) lets the demo switch it too.
import { useSyncExternalStore } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";
const STORAGE_KEY = "vs:reduced-motion";
const listeners = new Set<() => void>();

type Override = "reduce" | "no-preference" | null;

function readOverride(): Override {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    return v === "reduce" || v === "no-preference" ? v : null;
  } catch {
    return null;
  }
}

function applyOverrideAttr(o: Override): void {
  if (typeof document === "undefined") return;
  if (o === "reduce") document.documentElement.dataset.motion = "reduce";
  else delete document.documentElement.dataset.motion;
}

/** Current preference, read synchronously (client only; false on the server). */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  const o = readOverride();
  if (o) return o === "reduce";
  // Without matchMedia the preference cannot be read, so take the safe default: static mode.
  return typeof window.matchMedia !== "function" || window.matchMedia(QUERY).matches;
}

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  const mql = typeof window.matchMedia === "function" ? window.matchMedia(QUERY) : null;
  mql?.addEventListener?.("change", onChange);
  const onStorage = (e: StorageEvent) => {
    if (e.key === STORAGE_KEY) {
      applyOverrideAttr(readOverride());
      onChange();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(onChange);
    mql?.removeEventListener?.("change", onChange);
    window.removeEventListener("storage", onStorage);
  };
}

/**
 * Force reduced motion on ("reduce"), off ("no-preference") or back to the OS setting (null). Sets
 * <html data-motion="reduce"> so the CSS reduced-motion base applies as well.
 */
export function setReducedMotionOverride(value: Override): void {
  try {
    if (value) window.localStorage.setItem(STORAGE_KEY, value);
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage unavailable: the OS setting still applies */
  }
  applyOverrideAttr(value);
  listeners.forEach((l) => l());
}

/** The active override, if any. */
export function getReducedMotionOverride(): Override {
  return typeof window === "undefined" ? null : readOverride();
}

/**
 * True when motion should be reduced. Server render and hydration use `false`, then the real value is applied, so
 * there is no hydration mismatch. Components that must avoid a flash of animation should also respect the CSS
 * `[data-motion-only]` / `[data-static-only]` attributes (app/globals.css), which apply before hydration.
 */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, prefersReducedMotion, () => false);
}

export default useReducedMotion;

/** Flip reduced motion on or off (the override wins over the OS setting). Returns true when motion is now reduced. */
export function toggleReducedMotion(): boolean {
  const o = getReducedMotionOverride();
  const reduced = o ? o === "reduce" : prefersReducedMotion();
  setReducedMotionOverride(reduced ? "no-preference" : "reduce");
  return !reduced;
}
