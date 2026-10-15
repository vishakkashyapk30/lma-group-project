// Counsel's local workspace state per case, kept in localStorage: checklist resolutions (plan §13.5), List of Dates
// edits (plan §7.2: counsel can edit any row) and reworded grounds. The backend has no routes for the last two yet,
// so they are applied on top of the fetched data and sent with the gate approval (listed as a shared change).
import type { ResolutionState } from "./checklist";
import { EMPTY_RESOLUTIONS } from "./checklist";
import type { TimelineEvent } from "../types";

export interface DateEdit {
  date?: string;
  label?: string;
  at: string;
}

export interface GroundEdit {
  argument: string;
  note?: string | null;
  at: string;
}

export interface LocalWorkspaceState {
  resolutions: ResolutionState;
  dateEdits: Record<string, DateEdit>;
  groundEdits: Record<string, GroundEdit>;
}

export const EMPTY_LOCAL_STATE: LocalWorkspaceState = { resolutions: EMPTY_RESOLUTIONS, dateEdits: {}, groundEdits: {} };

const key = (caseId: string) => `vs:workspace:${caseId}`;

/** Saved state for a case, or null if nothing is saved (or storage is unavailable). */
export function loadLocalState(caseId: string): LocalWorkspaceState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(key(caseId));
    if (!raw) return null;
    const s = JSON.parse(raw) as Partial<LocalWorkspaceState>;
    return {
      resolutions: {
        acknowledged: s.resolutions?.acknowledged ?? [],
        resolved: s.resolutions?.resolved ?? {},
      },
      dateEdits: s.dateEdits ?? {},
      groundEdits: s.groundEdits ?? {},
    };
  } catch {
    return null;
  }
}

export function saveLocalState(caseId: string, state: LocalWorkspaceState): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key(caseId), JSON.stringify(state));
  } catch {
    /* storage full or unavailable */
  }
}

export function clearLocalState(caseId: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(key(caseId));
  } catch {
    /* ignore */
  }
}

/** Apply counsel's row edits to the List of Dates; edited rows become USER_EDITED. Sorted by date. */
export function applyDateEdits(dates: TimelineEvent[] | null, edits: Record<string, DateEdit>): TimelineEvent[] | null {
  if (!dates) return null;
  return dates
    .map((e) => {
      const edit = edits[e.event_id];
      if (!edit) return e;
      return { ...e, date: edit.date ?? e.date, label: edit.label ?? e.label, status: "USER_EDITED" as const };
    })
    .sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
}
