// SSE hook for agent events (plan §13.1; GET /api/cases/{id}/events). Drives the live trace and the agent animations.
import type { AgentEvent } from "./types";

export interface UseEventStreamResult { events: AgentEvent[]; connected: boolean; error: Error | null }

export function useEventStream(caseId: string | null): UseEventStreamResult {
  // TODO: open an EventSource, append events, reconnect with Last-Event-ID
  throw new Error("useEventStream: not implemented (skeleton)");
}
