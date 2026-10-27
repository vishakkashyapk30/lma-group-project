"use client";
// What the top bar shows for the open case: pages publish it, the top bar reads it. A tiny external store, so the
// case workspace (which sits below the shell) can tell the shell its title and stage without prop drilling.
import { useEffect, useSyncExternalStore } from "react";
import { writeLastCase } from "@/lib/lastCase";

export interface CaseMeta {
  caseId: string;
  title: string | null;
  stageLabel: string | null;
}

let current: CaseMeta | null = null;
const listeners = new Set<() => void>();

function set(next: CaseMeta | null): void {
  if (current === next || (current && next && current.caseId === next.caseId && current.title === next.title && current.stageLabel === next.stageLabel)) return;
  current = next;
  listeners.forEach((l) => l());
}

function subscribe(l: () => void): () => void {
  listeners.add(l);
  return () => listeners.delete(l);
}

/** Read the published case meta (null outside a case). */
export function useCaseMeta(): CaseMeta | null {
  return useSyncExternalStore(subscribe, () => current, () => null);
}

/**
 * Tell the top bar which case is about to open, before navigating to it, so the breadcrumb shows its title in the same
 * render as the new page (the workspace renders in the browser a moment later). That lets the title morph from the
 * case card into the breadcrumb.
 */
export function primeCaseMeta(caseId: string, title: string): void {
  if (current?.caseId === caseId && current.title) return;
  set({ caseId, title, stageLabel: null });
}

/** Publish the open case to the top bar (cleared on unmount) and remember it for "Continue" on the landing page. */
export function usePublishCaseMeta(caseId: string, title: string | null, stageLabel: string | null): void {
  useEffect(() => {
    set({ caseId, title, stageLabel });
    writeLastCase(caseId, title, stageLabel);
  }, [caseId, title, stageLabel]);
  useEffect(() => () => set(null), []);
}
