/**
 * useEventStream (plan §13.1; GET /api/cases/{id}/events): SSE hook that drives the live trace and agent animations.
 * ASSUMPTIONs: events are unnamed SSE "message" frames whose data is a JSON AgentEvent and whose id is the event_id;
 * EventSource cannot set headers, so on a CLOSED connection the hook reconnects (after a backoff) with the last seen id in a
 * `last_event_id` query parameter (src/vakeel_sahayak/api/sse.py takes last_event_id); malformed frames are ignored.
 */
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useEventStream } from "@/lib/useEventStream";
import type { AgentEvent } from "@/lib/types";

type Handler = (e: unknown) => void;
class MockEventSource {
  static instances: MockEventSource[] = [];
  static CONNECTING = 0; static OPEN = 1; static CLOSED = 2;
  readyState = 0;
  onopen: Handler | null = null; onmessage: Handler | null = null; onerror: Handler | null = null;
  closed = false;
  private listeners = new Map<string, Set<Handler>>();
  constructor(public url: string | URL, public init?: EventSourceInit) { MockEventSource.instances.push(this); }
  addEventListener(type: string, cb: Handler) { (this.listeners.get(type) ?? this.listeners.set(type, new Set()).get(type)!).add(cb); }
  removeEventListener(type: string, cb: Handler) { this.listeners.get(type)?.delete(cb); }
  close() { this.closed = true; this.readyState = 2; }
  // --- test drivers
  private fire(type: string, ev: unknown) {
    (this as unknown as Record<string, Handler | null>)[`on${type}`]?.(ev);
    this.listeners.get(type)?.forEach((cb) => cb(ev));
  }
  open() { this.readyState = 1; this.fire("open", { type: "open" }); }
  emit(ev: AgentEvent | string) {
    const data = typeof ev === "string" ? ev : JSON.stringify(ev);
    this.fire("message", { type: "message", data, lastEventId: typeof ev === "string" ? "" : ev.event_id });
  }
  fail(readyState: 0 | 2) { this.readyState = readyState; this.fire("error", { type: "error" }); }
}

const ev = (id: string, over: Partial<AgentEvent> = {}): AgentEvent => ({
  event_id: id, case_id: "case-0007", ts: "2025-02-03T09:01:00Z", kind: "TOOL_CALL", actor: "SUTRADHAR",
  tool: "search_reasoning", inputs: {}, outputs: {}, sources: [], ...over,
});
const current = () => MockEventSource.instances.at(-1)!;

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal("EventSource", MockEventSource);
  vi.useFakeTimers();
});
afterEach(() => { vi.useRealTimers(); });

describe("useEventStream (fails until implemented)", () => {
  it("opens an EventSource at /api/cases/{id}/events", () => {
    renderHook(() => useEventStream("case-0007"));
    expect(MockEventSource.instances).toHaveLength(1);
    const url = new URL(String(current().url));
    expect(url.pathname).toBe("/api/cases/case-0007/events");
    expect(url.origin).toBe("http://localhost:8000");
  });

  it("starts disconnected with no events, then connected after open", () => {
    const { result } = renderHook(() => useEventStream("case-0007"));
    expect(result.current).toMatchObject({ events: [], connected: false, error: null });
    act(() => current().open());
    expect(result.current.connected).toBe(true);
  });

  it("appends parsed events in arrival order", () => {
    const { result } = renderHook(() => useEventStream("case-0007"));
    act(() => { current().open(); current().emit(ev("ev001")); current().emit(ev("ev002", { kind: "TOOL_RESULT" })); });
    expect(result.current.events.map((e) => e.event_id)).toEqual(["ev001", "ev002"]);
    expect(result.current.events[1].kind).toBe("TOOL_RESULT");
  });

  it("ignores malformed frames without crashing or dropping later events", () => {
    const { result } = renderHook(() => useEventStream("case-0007"));
    act(() => { current().open(); current().emit("{not json"); current().emit(ev("ev003")); });
    expect(result.current.events.map((e) => e.event_id)).toEqual(["ev003"]);
  });

  it("does not duplicate an event delivered twice (same event_id) (ASSUMPTION: reconnect replay is idempotent)", () => {
    const { result } = renderHook(() => useEventStream("case-0007"));
    act(() => { current().open(); current().emit(ev("ev001")); current().emit(ev("ev001")); });
    expect(result.current.events).toHaveLength(1);
  });

  it("while the browser is auto-retrying (CONNECTING) it reports disconnected but keeps the same source", () => {
    const { result } = renderHook(() => useEventStream("case-0007"));
    act(() => current().open());
    act(() => current().fail(0));
    expect(result.current.connected).toBe(false);
    expect(MockEventSource.instances).toHaveLength(1);
  });

  it("after a CLOSED error it reconnects with the last seen id (Last-Event-ID) and keeps earlier events", () => {
    const { result } = renderHook(() => useEventStream("case-0007"));
    act(() => { current().open(); current().emit(ev("ev001")); current().emit(ev("ev002")); });
    const first = current();
    act(() => first.fail(2));
    expect(result.current.connected).toBe(false);
    act(() => { vi.advanceTimersByTime(30_000); });
    expect(MockEventSource.instances).toHaveLength(2);
    const second = current();
    expect(second).not.toBe(first);
    expect(String(second.url)).toMatch(/[?&](last_event_id|lastEventId)=ev002(&|$)/);
    expect(new URL(String(second.url)).pathname).toBe("/api/cases/case-0007/events");
    act(() => { second.open(); second.emit(ev("ev003")); });
    expect(result.current.connected).toBe(true);
    expect(result.current.events.map((e) => e.event_id)).toEqual(["ev001", "ev002", "ev003"]);
  });

  it("closes the EventSource on unmount and does not reconnect afterwards", () => {
    const { unmount } = renderHook(() => useEventStream("case-0007"));
    const es = current();
    act(() => es.open());
    unmount();
    expect(es.closed).toBe(true);
    act(() => { es.fail(2); vi.advanceTimersByTime(60_000); });
    expect(MockEventSource.instances).toHaveLength(1);
  });

  it("opens nothing for a null caseId", () => {
    const { result } = renderHook(() => useEventStream(null));
    expect(MockEventSource.instances).toHaveLength(0);
    expect(result.current).toMatchObject({ events: [], connected: false });
  });

  it("switching case closes the old stream, opens the new one, and resets the events", () => {
    const { result, rerender } = renderHook(({ id }) => useEventStream(id), { initialProps: { id: "case-0007" as string | null } });
    const old = current();
    act(() => { old.open(); old.emit(ev("ev001")); });
    rerender({ id: "case-0008" });
    expect(old.closed).toBe(true);
    expect(new URL(String(current().url)).pathname).toBe("/api/cases/case-0008/events");
    expect(result.current.events).toEqual([]);
  });
});
