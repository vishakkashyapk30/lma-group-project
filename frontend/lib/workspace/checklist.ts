// Gate checklist computation (plan §13.5, §16). Pure functions, shared by the workspace UI and the demo backend.
// Gate 1 (dossier): every UNSUPPORTED field resolved (edited or stated) or acknowledged by counsel.
// Gate 2 (export): the same, plus every NEEDS_REVIEW item (grounds and open issues) and every UNANSWERED objection
// resolved. Gate 2 also needs Gate 1. Mirrors src/vakeel_sahayak/record/gates.py, which counts the same items.
import { fieldLabel } from "../fields";
import { FACTOR_SHORT_LABELS } from "../labels";
import type { GateUiStatus } from "../status";
import type { WorkspaceTab } from "../stages";
import type { BailBrief, CaseDossier, GateId, GateStatus, SparringRecord } from "../types";
import { DOSSIER_FIELD_NAMES } from "../types";

export type ChecklistKind = "UNSUPPORTED" | "NEEDS_REVIEW" | "UNANSWERED";

export interface ChecklistItem {
  /** Stable key, e.g. "UNSUPPORTED:antecedents", "NEEDS_REVIEW:G5", "NEEDS_REVIEW:issue-0", "UNANSWERED:O2". */
  key: string;
  kind: ChecklistKind;
  /** Field name, ground id, "issue-<n>" or objection id. */
  ref: string;
  label: string;
  detail?: string;
  /** Where counsel resolves it. */
  target: { tab: WorkspaceTab; id: string };
  /** UNSUPPORTED fields may be acknowledged instead of fixed; NEEDS_REVIEW and UNANSWERED must be resolved. */
  canAcknowledge: boolean;
  resolved: boolean;
  resolution: "acknowledged" | "resolved" | null;
  note?: string | null;
}

export interface GateChecklist {
  gate: GateId;
  items: ChecklistItem[];
  /** Unresolved items. Approval is impossible while any remain. */
  blocking: ChecklistItem[];
  approved: boolean;
  /** Gate 2 needs Gate 1 first. */
  reachable: boolean;
  canApprove: boolean;
  uiStatus: GateUiStatus;
  /** One line for the rail tooltip and the modal header. */
  summary: string;
}

/** Counsel's decisions on checklist items (persisted per case in the workspace). */
export interface ResolutionState {
  /** Checklist keys acknowledged (UNSUPPORTED only). */
  acknowledged: string[];
  /** Checklist keys resolved, with counsel's note. */
  resolved: Record<string, { note?: string | null; at: string }>;
}

export const EMPTY_RESOLUTIONS: ResolutionState = { acknowledged: [], resolved: {} };

export interface ChecklistInput {
  dossier: CaseDossier | null;
  brief: BailBrief | null;
  spar: SparringRecord | null;
}

export interface GateApprovals {
  gate1: boolean;
  gate2: boolean;
}

export function checklistKey(kind: ChecklistKind, ref: string): string {
  return `${kind}:${ref}`;
}

/** Parse "NEEDS_REVIEW:G5" -> {kind, ref}. */
export function parseChecklistKey(key: string): { kind: ChecklistKind; ref: string } | null {
  const m = /^(UNSUPPORTED|NEEDS_REVIEW|UNANSWERED):(.+)$/.exec(key);
  return m ? { kind: m[1] as ChecklistKind, ref: m[2] } : null;
}

function decorate(item: Omit<ChecklistItem, "resolved" | "resolution" | "note">, res: ResolutionState): ChecklistItem {
  const resolvedEntry = res.resolved[item.key];
  if (resolvedEntry) return { ...item, resolved: true, resolution: "resolved", note: resolvedEntry.note ?? null };
  if (item.canAcknowledge && (res.acknowledged.includes(item.key) || res.acknowledged.includes(item.ref))) {
    return { ...item, resolved: true, resolution: "acknowledged", note: null };
  }
  return { ...item, resolved: false, resolution: null, note: null };
}

/** All checklist items for a gate, before resolutions are applied. */
export function rawChecklistItems(gate: GateId, input: ChecklistInput): Omit<ChecklistItem, "resolved" | "resolution" | "note">[] {
  const items: Omit<ChecklistItem, "resolved" | "resolution" | "note">[] = [];
  const { dossier, brief, spar } = input;
  if (dossier) {
    for (const name of DOSSIER_FIELD_NAMES) {
      if (dossier.fields[name]?.status === "UNSUPPORTED") {
        items.push({
          key: checklistKey("UNSUPPORTED", name),
          kind: "UNSUPPORTED",
          ref: name,
          label: `${fieldLabel(name)}: not found in the file`,
          detail: "Edit the field, state it from your instructions, or acknowledge that it stays unsupported.",
          target: { tab: "dossier", id: name },
          canAcknowledge: true,
        });
      }
    }
  }
  if (gate === "GATE_2_EXPORT") {
    for (const g of brief?.grounds ?? []) {
      if (g.check === "NEEDS_REVIEW") {
        items.push({
          key: checklistKey("NEEDS_REVIEW", g.id),
          kind: "NEEDS_REVIEW",
          ref: g.id,
          label: `${g.id} ${FACTOR_SHORT_LABELS[g.factor] ?? g.factor}: claim failed its check`,
          detail: "Review the ground: reword it, accept it with your note, or remove it from the draft.",
          target: { tab: "brief", id: g.id },
          canAcknowledge: false,
        });
      }
    }
    (brief?.open_issues ?? []).forEach((issue, i) => {
      if (issue.type === "NEEDS_REVIEW") {
        items.push({
          key: checklistKey("NEEDS_REVIEW", `issue-${i}`),
          kind: "NEEDS_REVIEW",
          ref: `issue-${i}`,
          label: issue.item,
          target: { tab: "brief", id: `issue-${i}` },
          canAcknowledge: false,
        });
      }
    });
    for (const o of spar?.objections ?? []) {
      if (o.verdict === "UNANSWERED") {
        items.push({
          key: checklistKey("UNANSWERED", o.id),
          kind: "UNANSWERED",
          ref: o.id,
          label: `${o.id}: ${o.objection}`,
          detail: o.reason ?? undefined,
          target: { tab: "spar", id: o.id },
          canAcknowledge: false,
        });
      }
    }
  }
  return items;
}

/** The checklist for a gate with counsel's resolutions applied. */
export function computeChecklist(
  gate: GateId,
  input: ChecklistInput,
  resolutions: ResolutionState = EMPTY_RESOLUTIONS,
  approvals: GateApprovals = { gate1: false, gate2: false },
  server: GateStatus | null = null,
): GateChecklist {
  // The backend's GateStatus (record/gates.py) is the authority on what is still unresolved: it counts UNSUPPORTED fields,
  // NEEDS_REVIEW grounds and UNANSWERED objections. The client list adds the labels, targets and counsel's local resolutions,
  // and drops anything the server no longer lists (for example a field counsel just edited).
  const listed = (item: Omit<ChecklistItem, "resolved" | "resolution" | "note">): boolean => {
    if (!server) return true;
    const list =
      item.kind === "UNSUPPORTED" ? server.unresolved_unsupported : item.kind === "NEEDS_REVIEW" ? server.unresolved_needs_review : server.unresolved_unanswered;
    return list.includes(item.ref);
  };
  const items = rawChecklistItems(gate, input).filter(listed).map((i) => decorate(i, resolutions));
  const blocking = items.filter((i) => !i.resolved);
  const approved = gate === "GATE_1_DOSSIER" ? approvals.gate1 : approvals.gate2;
  const reachable = gate === "GATE_1_DOSSIER" ? true : approvals.gate1;
  const hasData = gate === "GATE_1_DOSSIER" ? Boolean(input.dossier) : Boolean(input.brief);
  const canApprove = !approved && reachable && hasData && blocking.length === 0;
  const uiStatus: GateUiStatus = approved ? "APPROVED" : !reachable || !hasData ? "LOCKED" : blocking.length ? "BLOCKED" : "READY";
  const summary = approved
    ? "Approved by counsel."
    : !reachable
      ? "Unlocks after Gate 1."
      : !hasData
        ? gate === "GATE_1_DOSSIER" ? "Waiting for the dossier." : "Waiting for the draft."
        : blocking.length
          ? `${blocking.length} item${blocking.length === 1 ? "" : "s"} to resolve before approval.`
          : "Checklist clear: ready for counsel's approval.";
  return { gate, items, blocking, approved, reachable, canApprove, uiStatus, summary };
}

/**
 * What to send as ApproveRequest.acknowledged_fields: the field names counsel acknowledged (what the backend reads),
 * plus the keys of resolved NEEDS_REVIEW / UNANSWERED items so the backend can record them.
 */
export function acknowledgedForApproval(checklist: GateChecklist): string[] {
  const out: string[] = [];
  for (const item of checklist.items) {
    if (!item.resolved) continue;
    out.push(item.kind === "UNSUPPORTED" ? item.ref : item.key);
  }
  return out;
}

/** Number of unresolved items for the next gate counsel has to pass (cause-list "needs attention"). */
export function attentionCount(input: ChecklistInput, resolutions: ResolutionState, approvals: GateApprovals): number {
  if (!approvals.gate1) return computeChecklist("GATE_1_DOSSIER", input, resolutions, approvals).blocking.length;
  if (!approvals.gate2) return computeChecklist("GATE_2_EXPORT", input, resolutions, approvals).blocking.length;
  return 0;
}
