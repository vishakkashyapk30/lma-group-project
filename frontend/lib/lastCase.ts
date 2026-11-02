// The case that was open last, remembered in this browser (localStorage "vs:last-case") so the landing page can offer
// "Continue: <title>". Written by the workspace through usePublishCaseMeta; nothing is sent anywhere.
import { useSyncExternalStore } from "react";

export const LAST_CASE_KEY = "vs:last-case";

export interface LastCase {
  id: string;
  title: string;
  stageLabel: string | null;
  /** ISO time of the last visit. */
  at: string;
}

const listeners = new Set<() => void>();
let cachedRaw: string | null | undefined;
let cachedValue: LastCase | null = null;

function parse(raw: string | null): LastCase | null {
  if (!raw) return null;
  try {
    const v = JSON.parse(raw) as Partial<LastCase>;
    if (typeof v.id !== "string" || !v.id || typeof v.title !== "string" || !v.title) return null;
    if (!/^[\w.-]+$/.test(v.id)) return null; // ids go into a URL: keep them plain
    return { id: v.id, title: v.title, stageLabel: typeof v.stageLabel === "string" ? v.stageLabel : null, at: typeof v.at === "string" ? v.at : "" };
  } catch {
    return null;
  }
}

/** The remembered case, or null (no storage, nothing stored, or a malformed entry). */
export function readLastCase(): LastCase | null {
  if (typeof window === "undefined") return null;
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(LAST_CASE_KEY);
  } catch {
    return null;
  }
  if (raw !== cachedRaw) {
    cachedRaw = raw;
    cachedValue = parse(raw);
  }
  return cachedValue;
}

/** Remember a case. Ignores calls without a title (the workspace publishes null while it loads). */
export function writeLastCase(id: string, title: string | null, stageLabel: string | null, now: Date = new Date()): void {
  if (typeof window === "undefined" || !id || !title) return;
  const prev = readLastCase();
  if (prev && prev.id === id && prev.title === title && prev.stageLabel === stageLabel) return;
  try {
    window.localStorage.setItem(LAST_CASE_KEY, JSON.stringify({ id, title, stageLabel, at: now.toISOString() } satisfies LastCase));
  } catch {
    return;
  }
  listeners.forEach((l) => l());
}

export function clearLastCase(): void {
  try {
    window.localStorage.removeItem(LAST_CASE_KEY);
  } catch {
    /* ignore */
  }
  listeners.forEach((l) => l());
}

function subscribe(l: () => void): () => void {
  listeners.add(l);
  const onStorage = (e: StorageEvent) => {
    if (e.key === LAST_CASE_KEY || e.key === null) l();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(l);
    window.removeEventListener("storage", onStorage);
  };
}

/** The remembered case; null on the server and during hydration, so the first paint matches the server's. */
export function useLastCase(): LastCase | null {
  return useSyncExternalStore(subscribe, readLastCase, () => null);
}
