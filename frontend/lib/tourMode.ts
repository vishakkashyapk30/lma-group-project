// Tour mode: the workspace is opened with ?tour=<slug> (the guided demo for an evaluator). The recorded case is shared by every
// evaluator, so while a tour runs the workspace is read-only: the controls are disabled (useTourMode) and the API client refuses
// every write except the two the tour itself makes (lib/api.ts, tourAllows). This module only knows whether a tour is running.
import { useSyncExternalStore } from "react";

export const TOUR_READ_ONLY_NOTE = "This is a recorded demo; fields are read-only.";
export const TOUR_REFUSED_MESSAGE = "This is a recorded demo, so this change was not made. Exit the demo to work on a case of your own.";

const listeners = new Set<() => void>();
let forced: boolean | null = null;

function fromLocation(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return (window.location.pathname ?? "").startsWith("/case/") && Boolean(new URLSearchParams(window.location.search).get("tour")?.trim());
  } catch {
    return false;
  }
}

/** True while a guided demo runs: the URL carries ?tour=<slug> on a case page (or a test or the workspace shell said so). */
export function isTourMode(): boolean {
  return forced ?? fromLocation();
}

/** The workspace shell keeps this in step with the URL; tests may force it (null returns to reading the URL). */
export function setTourMode(active: boolean | null): void {
  if (forced === active) return;
  forced = active;
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  if (typeof window !== "undefined") window.addEventListener("popstate", listener);
  return () => {
    listeners.delete(listener);
    if (typeof window !== "undefined") window.removeEventListener("popstate", listener);
  };
}

/** Whether the workspace is read-only because a tour runs. */
export function useTourMode(): boolean {
  return useSyncExternalStore(subscribe, isTourMode, () => false);
}

/**
 * The only writes a tour makes itself: the Gate 2 approval on the GATE_2 step (Next) and the export on the FILE step.
 * Everything else that writes (edit, answer, upload, dictation, chat, draft, Gate 1, desk, new case) is refused.
 */
export function tourAllows(method: string, path: string): boolean {
  const m = method.toUpperCase();
  if (m === "GET" || m === "HEAD" || m === "OPTIONS") return true;
  if (m !== "POST") return false;
  return /^\/api\/cases\/[^/]+\/gates\/GATE_2_EXPORT\/approve$/.test(path) || /^\/api\/cases\/[^/]+\/export$/.test(path);
}
