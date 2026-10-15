"use client";
// SSE hook for agent events (plan §3.3 use 4, §13.1; GET /api/cases/{case_id}/events). It drives the live trace and
// the agent animations. Live mode: an EventSource with reconnect (exponential backoff, resuming after the last event
// id). Demo mode: the demo backend replays the case's scripted event log, then streams new events as scripts play.
// If the live stream never opens after a few tries, the hook falls back to demo mode like lib/api does.
import { useCallback, useEffect, useRef, useState } from "react";
import { enterDemoMode, eventsUrl, getApiMode, onApiModeChange, type ApiMode } from "./api";
import { subscribeDemoEvents } from "./mock/server";
import type { AgentEvent } from "./types";
import { EVENT_KINDS } from "./types";

export type StreamStatus = "idle" | "connecting" | "open" | "reconnecting" | "closed";

export interface UseEventStreamOptions {
  /** Keep at most this many events in memory (oldest dropped). Default 2000. */
  max?: number;
  /** Called for every new event (after de-duplication). */
  onEvent?: (event: AgentEvent) => void;
  /** Start disabled (no connection) when false. Default true. */
  enabled?: boolean;
}

export interface UseEventStreamResult {
  events: AgentEvent[];
  /** True while the stream is open (demo streams are always open). */
  connected: boolean;
  status: StreamStatus;
  error: Error | null;
  mode: ApiMode;
  lastEvent: AgentEvent | null;
  /** Drop the events held in memory (the log on the server is untouched). */
  clear: () => void;
}

const MAX_BACKOFF_MS = 15_000;
const FAILURES_BEFORE_DEMO = 3;

function parseEvent(data: string): AgentEvent | null {
  try {
    const e = JSON.parse(data) as AgentEvent;
    return e && typeof e === "object" && typeof e.kind === "string" ? e : null;
  } catch {
    return null;
  }
}

export function useEventStream(caseId: string | null, options: UseEventStreamOptions = {}): UseEventStreamResult {
  const { max = 2000, enabled = true } = options;
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [status, setStatus] = useState<StreamStatus>("idle");
  const [error, setError] = useState<Error | null>(null);
  // The mode comes from the build-time env on both server and client, so this initial value cannot mismatch.
  const [mode, setMode] = useState<ApiMode>(getApiMode);
  const seen = useRef<Set<string>>(new Set());
  const lastId = useRef<string | null>(null);
  const onEventRef = useRef(options.onEvent);
  onEventRef.current = options.onEvent;

  useEffect(() => {
    setMode(getApiMode());
    return onApiModeChange(setMode);
  }, []);

  // A new case starts a new log.
  useEffect(() => {
    seen.current = new Set();
    lastId.current = null;
    setEvents([]);
  }, [caseId]);

  const push = useCallback(
    (e: AgentEvent) => {
      if (e.event_id && seen.current.has(e.event_id)) return;
      if (e.event_id) {
        seen.current.add(e.event_id);
        lastId.current = e.event_id;
      }
      setEvents((prev) => {
        const next = prev.length >= max ? prev.slice(prev.length - max + 1) : prev.slice();
        next.push(e);
        return next;
      });
      onEventRef.current?.(e);
    },
    [max],
  );

  useEffect(() => {
    if (!caseId || !enabled) {
      setStatus("idle");
      return;
    }
    if (mode === "demo") {
      setStatus("open");
      setError(null);
      const unsubscribe = subscribeDemoEvents(caseId, lastId.current, push);
      return () => {
        unsubscribe();
        setStatus("closed");
      };
    }

    let source: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;
    let everOpened = false;
    let stopped = false;

    const handle = (msg: MessageEvent<string>) => {
      const e = parseEvent(msg.data);
      if (e) push(e);
    };

    const connect = () => {
      if (stopped) return;
      const url = eventsUrl(caseId, lastId.current);
      if (!url) return;
      setStatus(attempt === 0 ? "connecting" : "reconnecting");
      source = new EventSource(url);
      source.onopen = () => {
        everOpened = true;
        attempt = 0;
        setStatus("open");
        setError(null);
      };
      source.onmessage = handle;
      // The backend may name events by kind (event: TOOL_CALL); listen for those too.
      for (const kind of EVENT_KINDS) source.addEventListener(kind, handle as EventListener);
      source.onerror = () => {
        source?.close();
        source = null;
        attempt += 1;
        if (!everOpened && attempt >= FAILURES_BEFORE_DEMO) {
          enterDemoMode("the event stream could not be opened");
          return;
        }
        setStatus("reconnecting");
        setError(new Error("Event stream interrupted; reconnecting."));
        const delay = Math.min(MAX_BACKOFF_MS, 500 * 2 ** Math.min(attempt, 5));
        timer = setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      source?.close();
      setStatus("closed");
    };
  }, [caseId, enabled, mode, push]);

  const clear = useCallback(() => setEvents([]), []);

  return {
    events,
    connected: status === "open",
    status,
    error,
    mode,
    lastEvent: events.length ? events[events.length - 1] : null,
    clear,
  };
}

export default useEventStream;
