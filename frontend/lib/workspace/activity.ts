// Which agent is doing what, derived from the event log (plan §3.3 use 4, §13.4): drives the signature animations,
// the chat header wheel and the live trace. Pure functions; the workspace provider recomputes them as events arrive.
import { AGENTS, isAgentName } from "../agents";
import { spokeForEvent, storeForEvent } from "../stores";
import type { AgentEvent, AgentName, StoreName } from "../types";
import { AGENT_NAMES } from "../types";

export type AgentPhase = "idle" | "working" | "done";

export interface AgentActivity {
  agent: AgentName;
  phase: AgentPhase;
  /** The agent's latest event, if any. */
  lastEvent: AgentEvent | null;
  /** Its latest message text, or the static status text for reduced motion. */
  text: string;
  /** Tool of its latest TOOL_CALL, if any. */
  tool: string | null;
}

export interface ActivityState {
  byAgent: Record<AgentName, AgentActivity>;
  /** Agents working right now, in the plan's order. */
  working: AgentName[];
  /** Wheel spokes (0-23) queried in the current run, most recent last (plan §13.4: each spoke lights as queried). */
  litSpokes: number[];
  /** Stores touched in the current run. */
  activeStores: StoreName[];
  /** BUDGET_HIT events of the current run. */
  budgetHits: AgentEvent[];
  /** Index in the log where the current run started (the last counsel action), or 0. */
  runStart: number;
}

/** An agent counts as working if its latest event is not a "done" message and is at most this old. */
export const WORKING_WINDOW_MS = 20_000;

function isDone(e: AgentEvent): boolean {
  return e.kind === "AGENT_MESSAGE" && (e.outputs?.status === "done" || e.outputs?.refused === true);
}

function messageText(e: AgentEvent | null): string | null {
  if (!e) return null;
  const t = e.outputs?.text;
  return typeof t === "string" ? t : null;
}

/** Derive per-agent activity from the event log. `now` is injectable for tests; defaults to Date.now(). */
export function deriveActivity(events: readonly AgentEvent[], now: number = Date.now()): ActivityState {
  const last: Partial<Record<AgentName, AgentEvent>> = {};
  const lastMessage: Partial<Record<AgentName, AgentEvent>> = {};
  const lastCall: Partial<Record<AgentName, AgentEvent>> = {};
  let runStart = 0;
  events.forEach((e, i) => {
    if (e.actor === "counsel" && (e.kind === "USER_ACTION" || e.kind === "GATE_APPROVED" || e.kind === "CHANGE_SET_APPROVED")) runStart = i;
    const actor = typeof e.actor === "string" ? e.actor.toUpperCase() : "";
    if (!isAgentName(actor)) return;
    last[actor] = e;
    if (e.kind === "AGENT_MESSAGE") lastMessage[actor] = e;
    if (e.kind === "TOOL_CALL") lastCall[actor] = e;
  });

  const byAgent = {} as Record<AgentName, AgentActivity>;
  const working: AgentName[] = [];
  for (const agent of AGENT_NAMES) {
    const e = last[agent] ?? null;
    let phase: AgentPhase = "idle";
    if (e) {
      const age = now - new Date(e.ts).getTime();
      phase = isDone(e) || !(age <= WORKING_WINDOW_MS) ? "done" : "working";
    }
    if (phase === "working") working.push(agent);
    const meta = AGENTS[agent];
    byAgent[agent] = {
      agent,
      phase,
      lastEvent: e,
      text: messageText(lastMessage[agent] ?? null) ?? (phase === "working" ? meta.workingText : e ? meta.idleText : `${meta.name}: waiting`),
      tool: lastCall[agent]?.tool ?? null,
    };
  }

  const run = events.slice(runStart);
  const litSpokes: number[] = [];
  const activeStores = new Set<StoreName>();
  const budgetHits: AgentEvent[] = [];
  for (const e of run) {
    if (e.kind === "TOOL_CALL" || e.kind === "TOOL_RESULT" || e.kind === "STORE_WRITE") {
      const spoke = spokeForEvent(e);
      if (spoke !== null) {
        const at = litSpokes.indexOf(spoke);
        if (at >= 0) litSpokes.splice(at, 1);
        litSpokes.push(spoke);
      }
      const store = storeForEvent(e);
      if (store) activeStores.add(store);
    }
    if (e.kind === "BUDGET_HIT") budgetHits.push(e);
  }

  return { byAgent, working, litSpokes, activeStores: [...activeStores], budgetHits, runStart };
}

/** True if any event in the log is newer than `ms` (used to keep the activity clock ticking only while needed). */
export function hasRecentEvents(events: readonly AgentEvent[], ms = WORKING_WINDOW_MS, now: number = Date.now()): boolean {
  const e = events[events.length - 1];
  return Boolean(e && now - new Date(e.ts).getTime() <= ms);
}
