/**
 * useReducedMotion (plan §13.4, §13.7): "With prefers-reduced-motion, every animation becomes a static icon with a text
 * status." The hook subscribes to matchMedia("(prefers-reduced-motion: reduce)").
 */
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useReducedMotion } from "@/lib/useReducedMotion";

const QUERY = "(prefers-reduced-motion: reduce)";

/** Minimal controllable MediaQueryList. Tracks listeners registered through either the modern or the legacy API. */
function installMatchMedia(initial: Record<string, boolean>) {
  const state = { ...initial };
  const listeners = new Map<string, Set<(e: { matches: boolean; media: string }) => void>>();
  const queries: string[] = [];
  const matchMedia = vi.fn((query: string) => {
    queries.push(query);
    const set = listeners.get(query) ?? listeners.set(query, new Set()).get(query)!;
    return {
      get matches() { return state[query] ?? false; },
      media: query,
      onchange: null,
      addEventListener: (_t: string, cb: never) => set.add(cb),
      removeEventListener: (_t: string, cb: never) => set.delete(cb),
      addListener: (cb: never) => set.add(cb), // legacy
      removeListener: (cb: never) => set.delete(cb), // legacy
      dispatchEvent: () => true,
    };
  });
  vi.stubGlobal("matchMedia", matchMedia);
  Object.defineProperty(window, "matchMedia", { configurable: true, writable: true, value: matchMedia });
  return {
    matchMedia,
    queries,
    set(query: string, matches: boolean) {
      state[query] = matches;
      for (const cb of [...(listeners.get(query) ?? [])]) cb({ matches, media: query });
    },
    listenerCount: (query: string) => listeners.get(query)?.size ?? 0,
  };
}

describe("useReducedMotion (fails until implemented)", () => {
  beforeEach(() => { vi.useRealTimers(); });
  afterEach(() => { delete (window as { matchMedia?: unknown }).matchMedia; });

  it("returns true when (prefers-reduced-motion: reduce) matches", () => {
    installMatchMedia({ [QUERY]: true });
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(true);
  });

  it("returns false when the query does not match", () => {
    installMatchMedia({ [QUERY]: false });
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);
  });

  it("asks for exactly the reduce query", () => {
    const mm = installMatchMedia({ [QUERY]: false });
    renderHook(() => useReducedMotion());
    expect(mm.queries).toContain(QUERY);
    expect(mm.queries.every((q) => q === QUERY)).toBe(true);
  });

  it("updates when the media query changes, in both directions", () => {
    const mm = installMatchMedia({ [QUERY]: false });
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);
    act(() => mm.set(QUERY, true));
    expect(result.current).toBe(true);
    act(() => mm.set(QUERY, false));
    expect(result.current).toBe(false);
  });

  it("subscribes a listener and removes it on unmount", () => {
    const mm = installMatchMedia({ [QUERY]: false });
    const { unmount } = renderHook(() => useReducedMotion());
    expect(mm.listenerCount(QUERY)).toBe(1);
    unmount();
    expect(mm.listenerCount(QUERY)).toBe(0);
  });

  it("does not leak listeners across re-renders", () => {
    const mm = installMatchMedia({ [QUERY]: false });
    const { rerender, unmount } = renderHook(() => useReducedMotion());
    rerender(); rerender();
    expect(mm.listenerCount(QUERY)).toBe(1);
    unmount();
    expect(mm.listenerCount(QUERY)).toBe(0);
  });

  it("falls back to static mode (true) when matchMedia is unavailable (ASSUMPTION: safest default)", () => {
    expect((window as { matchMedia?: unknown }).matchMedia).toBeUndefined();
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(true);
  });
});
