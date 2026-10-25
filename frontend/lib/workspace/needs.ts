// "What needs you" (plan §13.5): the short list each step opens with. Pure selectors over the case data, so the steps, the
// gate dialog and tests read the same list. An item names what is wrong in plain words and where to go to fix it.
import { fieldLabel } from "../fields";
import { FACTOR_SHORT_LABELS } from "../labels";
import type { WorkspaceTab } from "../stages";
import type { BailBrief, CaseDossier, HearingPrepCard, IngestionReport, SparringRecord, Stage, TimelineEvent } from "../types";
import { DOSSIER_FIELD_NAMES } from "../types";
import type { GateChecklist, ResolutionState } from "./checklist";

export type NeedTarget =
  | { kind: "item"; tab: WorkspaceTab; id: string; intent?: "edit" }
  | { kind: "chat" }
  | { kind: "files" };

export interface NeedItem {
  key: string;
  text: string;
  detail?: string;
  /** Button label; the button jumps to the target. */
  label: string;
  target: NeedTarget | null;
}

export interface NeedsInput {
  dossier: CaseDossier | null;
  dates: TimelineEvent[] | null;
  ingestion: IngestionReport | null;
  brief: BailBrief | null;
  spar: SparringRecord | null;
  prep: HearingPrepCard | null;
  gate1: GateChecklist;
  gate2: GateChecklist;
  resolutions: ResolutionState;
}

function addDocuments(input: NeedsInput): NeedItem[] {
  const report = input.ingestion;
  if (!report) return [];
  const out: NeedItem[] = [];
  for (const d of report.documents) {
    const bad = d.page_routes.filter((p) => p.status === "UNREADABLE").length;
    if (bad > 0) {
      out.push({ key: `unreadable:${d.doc_id}`, text: `${bad === 1 ? "1 page" : `${bad} pages`} of ${d.doc_id} could not be read`, detail: "Add a clearer copy.", label: "Add files", target: { kind: "files" } });
    }
  }
  for (const g of report.gaps) out.push({ key: `gap:${g.item}`, text: `${g.item} is missing`, detail: g.action, label: "Add files", target: { kind: "files" } });
  for (const q of report.questions) out.push({ key: `question:${q}`, text: q, label: "Answer", target: { kind: "chat" } });
  return out;
}

function reviewFacts(input: NeedsInput): NeedItem[] {
  const out: NeedItem[] = [];
  const { dossier } = input;
  for (const item of input.gate1.items) {
    if (item.resolved || item.kind !== "UNSUPPORTED") continue;
    out.push({
      key: item.key,
      text: `${fieldLabel(item.ref)} not found`,
      detail: "Add a value or mark it unknown.",
      label: "Add value",
      target: { kind: "item", tab: "dossier", id: item.ref, intent: "edit" },
    });
  }
  if (dossier) {
    for (const name of DOSSIER_FIELD_NAMES) {
      if (dossier.fields[name]?.status !== "AMBIGUOUS") continue;
      out.push({ key: `ambiguous:${name}`, text: `${fieldLabel(name)}: the documents disagree`, label: "Check", target: { kind: "item", tab: "dossier", id: name } });
    }
    for (const q of dossier.open_questions) out.push({ key: `question:${q}`, text: q, label: "Answer", target: { kind: "chat" } });
  }
  const conflicting = (input.dates ?? []).filter((e) => e.conflicts_with.length > 0);
  if (conflicting.length > 0) {
    const first = [...conflicting].sort((a, b) => (a.date < b.date ? -1 : 1))[0];
    out.push({
      key: "dates:conflict",
      text: "The documents give different dates for the same event",
      label: "Check",
      target: { kind: "item", tab: "dates", id: first.event_id },
    });
  }
  return out;
}

function draftGrounds(input: NeedsInput): NeedItem[] {
  const out: NeedItem[] = [];
  for (const item of input.gate2.items) {
    if (item.resolved) continue;
    if (item.kind === "NEEDS_REVIEW" && item.ref.startsWith("issue-")) {
      out.push({ key: item.key, text: item.label, label: "Check", target: { kind: "item", tab: "brief", id: item.ref } });
    } else if (item.kind === "NEEDS_REVIEW") {
      const ground = input.brief?.grounds.find((g) => g.id === item.ref);
      const factor = ground ? (FACTOR_SHORT_LABELS[ground.factor] ?? ground.factor) : "";
      out.push({ key: item.key, text: `Ground ${item.ref}${factor ? ` (${factor})` : ""} needs your check`, label: "Review", target: { kind: "item", tab: "brief", id: item.ref } });
    } else if (item.kind === "UNANSWERED") {
      out.push({ key: item.key, text: `Objection ${item.ref} has no answer yet`, detail: input.spar?.objections.find((o) => o.id === item.ref)?.objection, label: "Answer", target: { kind: "item", tab: "spar", id: item.ref } });
    }
  }
  return out;
}

function hearing(input: NeedsInput): NeedItem[] {
  return (input.prep?.open_issues ?? []).map((text) => ({ key: `prep:${text}`, text, label: "", target: null }));
}

function exportDraft(input: NeedsInput): NeedItem[] {
  if (input.gate2.approved) return [];
  return input.gate2.blocking.map((item) => ({
    key: item.key,
    text: item.kind === "UNANSWERED" ? `Objection ${item.ref} has no answer yet` : item.label,
    label: "Go to it",
    target: { kind: "item", tab: item.target.tab, id: item.target.id },
  }));
}

/** What needs the lawyer in this step. Empty means nothing does. */
export function needsFor(stage: Stage, input: NeedsInput): NeedItem[] {
  switch (stage) {
    case "INTAKE":
      return addDocuments(input);
    case "DOSSIER":
      return reviewFacts(input);
    case "BRIEF":
    case "SPAR":
      return draftGrounds(input);
    case "HEARING_PREP":
      return hearing(input);
    case "FILE":
      return exportDraft(input);
    case "RIGHTS":
      return [];
  }
}
