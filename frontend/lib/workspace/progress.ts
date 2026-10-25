// One line of progress for long-running agent work: "Reading your documents: page 3 of 14". Pure, so it can be tested.
import type { AgentEvent, AgentName } from "../types";
import type { ActivityState } from "./activity";

const PHRASE: Partial<Record<AgentName, string>> = {
  MUNSHI: "Reading your documents",
  PESHKAR: "Checking the facts and dates",
  VAKEEL: "Drafting the grounds",
  ABHIYOJAK: "Testing the draft against likely objections",
};

export interface ProgressLine {
  agent: AgentName;
  text: string;
}

function asNumber(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/** The last page a pages value like 6, "6-10" or "4-5" reaches. */
function lastPage(inputs: Record<string, unknown> | undefined, outputs: Record<string, unknown> | undefined): number | null {
  const single = asNumber(inputs?.page) ?? asNumber(outputs?.page);
  if (single !== null) return single;
  const range = typeof inputs?.pages === "string" ? inputs.pages : typeof outputs?.pages === "string" ? outputs.pages : null;
  const m = range ? /(\d+)\s*$/.exec(range) : null;
  return m ? Number(m[1]) : null;
}

/** How far Munshi has got through the pages of the current run: the highest page it touched, of the total it surveyed. */
export function readingProgress(events: readonly AgentEvent[], from: number): { page: number; total: number } | null {
  let total: number | null = null;
  let page = 0;
  for (const e of events.slice(from)) {
    if (String(e.actor).toUpperCase() !== "MUNSHI") continue;
    const surveyed = asNumber(e.outputs?.pages);
    if (surveyed !== null) total = surveyed;
    const text = typeof e.outputs?.text === "string" ? /(\d+)\s+pages/.exec(e.outputs.text) : null;
    if (text && total === null) total = Number(text[1]);
    const at = lastPage(e.inputs, e.outputs);
    if (at !== null) page = Math.max(page, at);
  }
  return total && page > 0 ? { page: Math.min(page, total), total } : null;
}

/** What to say while an agent works, or null when nothing is running. Sutradhar's lookups belong to the chat, not here. */
export function progressLine(activity: ActivityState, events: readonly AgentEvent[], busy: { uploading: boolean; drafting: boolean }): ProgressLine | null {
  const agent: AgentName | undefined = activity.working.find((a) => PHRASE[a]) ?? (busy.uploading ? "MUNSHI" : busy.drafting ? "VAKEEL" : undefined);
  if (!agent) return null;
  const base = PHRASE[agent] ?? "Working";
  if (agent === "MUNSHI") {
    const p = readingProgress(events, activity.runStart);
    if (p) return { agent, text: `${base}: page ${p.page} of ${p.total}` };
  }
  return { agent, text: base };
}
