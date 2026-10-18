// What changed since counsel last approved the dossier (plan §7.4, §10), derived from the event log: a change set arrives as
// a STORE_WRITE (or tool result) carrying `change_set`, stays pending until CHANGE_SET_APPROVED, then CLAIM_STALED marks the
// grounds that depended on it and a STORE_WRITE with `redrafted` lists the grounds Vakeel rewrote. Pure, so it is unit-testable.
import type { AgentEvent, ChangeSet } from "../types";

export interface ChangeState {
  /** The change set waiting for counsel's re-approval, if any. */
  pending: ChangeSet | null;
  /** Dossier field names in the pending change set. */
  changedFields: string[];
  /** Rights Radar checks in the pending change set. */
  changedRights: string[];
  /** Claims (ground ids) marked STALE and not yet redrafted. */
  staleClaims: string[];
  /** Grounds redrafted since the last change set. */
  redrafted: string[];
  /** Why a claim went stale or was redrafted, by ground id (for example "depends on charge sheet, which changed"). */
  reasons: Record<string, string>;
}

export const NO_CHANGES: ChangeState = { pending: null, changedFields: [], changedRights: [], staleClaims: [], redrafted: [], reasons: {} };

function isChangeSet(v: unknown): v is ChangeSet {
  return typeof v === "object" && v !== null && Array.isArray((v as ChangeSet).fields);
}

function strings(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
}

/** The change set an event announces (not the approval event, which only names the fields it approved). */
export function changeSetOf(e: AgentEvent): ChangeSet | null {
  if (e.kind === "CHANGE_SET_APPROVED") return null;
  const candidate = e.outputs?.change_set ?? e.inputs?.change_set;
  return isChangeSet(candidate) ? candidate : null;
}

export function deriveChanges(events: readonly AgentEvent[]): ChangeState {
  let pending: ChangeSet | null = null;
  let stale: string[] = [];
  let redrafted: string[] = [];
  let reasons: Record<string, string> = {};
  for (const e of events) {
    const cs = changeSetOf(e);
    if (cs && (cs.fields.length > 0 || (cs.rights_changed ?? []).length > 0)) {
      pending = cs;
      stale = [];
      redrafted = [];
      reasons = {};
      continue;
    }
    if (e.kind === "CHANGE_SET_APPROVED") {
      pending = null;
    } else if (e.kind === "CLAIM_STALED") {
      const ids = [...strings(e.outputs?.claim_ids), ...(typeof e.inputs?.claim === "string" ? [e.inputs.claim] : [])];
      const reason = typeof e.outputs?.reason === "string" ? e.outputs.reason : "a fact it depends on changed";
      for (const id of ids) {
        if (!stale.includes(id)) stale.push(id);
        reasons[id] = reason;
      }
    } else if (e.kind === "STORE_WRITE" && e.outputs?.view === "brief") {
      const done = strings(e.outputs.redrafted);
      if (done.length > 0) {
        stale = stale.filter((id) => !done.includes(id));
        redrafted = Array.from(new Set([...redrafted, ...done]));
      }
    }
  }
  return {
    pending,
    changedFields: pending ? pending.fields.map((f) => f.field) : [],
    changedRights: pending ? [...(pending.rights_changed ?? [])] : [],
    staleClaims: stale,
    redrafted,
    reasons,
  };
}
