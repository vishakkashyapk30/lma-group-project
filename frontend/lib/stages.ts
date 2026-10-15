// Workspace stages (plan §13.5): numbered like the Parts of the Constitution. Gate 1 follows II Dossier and Gate 2
// precedes VII File. Counsel can jump to any open stage; later stages unlock after Gate 1; File needs Gate 2.
import type { AgentName, GateId, Stage } from "./types";
import { STAGE_IDS } from "./types";

/** Right-pane tabs (plan §13.5): Dossier · Dates · Rights · Brief · Spar · Prep. */
export const WORKSPACE_TABS = ["dossier", "dates", "rights", "brief", "spar", "prep"] as const;
export type WorkspaceTab = (typeof WORKSPACE_TABS)[number];

export const TAB_LABELS: Record<WorkspaceTab, string> = {
  dossier: "Dossier",
  dates: "Dates",
  rights: "Rights",
  brief: "Brief",
  spar: "Spar",
  prep: "Prep",
};

export interface StageMeta {
  id: Stage;
  /** Roman numeral, Constitution-style. */
  numeral: string;
  label: string;
  /** Gate drawn as a diamond right after this stage (Gate 1) or right before it (Gate 2). */
  gate?: GateId;
  gatePosition?: "after" | "before";
  /** Right-pane tab shown for this stage. */
  tab: WorkspaceTab;
  /** Agent mainly at work in this stage. */
  agent: AgentName | null;
  description: string;
}

export const STAGES: readonly StageMeta[] = [
  { id: "INTAKE", numeral: "I", label: "Intake", tab: "dossier", agent: "MUNSHI", description: "Munshi reads, splits, labels and files every page." },
  { id: "DOSSIER", numeral: "II", label: "Dossier", gate: "GATE_1_DOSSIER", gatePosition: "after", tab: "dossier", agent: "PESHKAR", description: "Peshkar builds the source-checked dossier and the List of Dates." },
  { id: "RIGHTS", numeral: "III", label: "Rights", tab: "rights", agent: "PESHKAR", description: "The Rights Radar checks procedural rights from the timeline." },
  { id: "BRIEF", numeral: "IV", label: "Brief", tab: "brief", agent: "VAKEEL", description: "Sutradhar plans retrieval; Vakeel drafts and checks every ground." },
  { id: "SPAR", numeral: "V", label: "Spar", tab: "spar", agent: "ABHIYOJAK", description: "Abhiyojak attacks the draft the way the prosecution would." },
  { id: "HEARING_PREP", numeral: "VI", label: "Hearing prep", tab: "prep", agent: "VAKEEL", description: "The one-page hearing-prep card." },
  { id: "FILE", numeral: "VII", label: "File", gate: "GATE_2_EXPORT", gatePosition: "before", tab: "prep", agent: null, description: "Export the application after counsel's approval." },
];

export const STAGE_BY_ID: Record<Stage, StageMeta> = Object.fromEntries(STAGES.map((s) => [s.id, s])) as Record<Stage, StageMeta>;

export const GATE_LABELS: Record<GateId, { short: string; label: string; description: string }> = {
  GATE_1_DOSSIER: {
    short: "Gate 1",
    label: "Gate 1: approve the dossier",
    description: "Counsel approves the dossier before anything goes to the drafting agents.",
  },
  GATE_2_EXPORT: {
    short: "Gate 2",
    label: "Gate 2: approve the final draft",
    description: "Counsel approves the draft. Nothing is exported without this approval.",
  },
};

/** Position of a stage in I-VII (0-based). */
export function stageIndex(stage: Stage): number {
  return STAGE_IDS.indexOf(stage);
}

export function compareStages(a: Stage, b: Stage): number {
  return stageIndex(a) - stageIndex(b);
}

/** Stage for a right-pane tab (Dates belongs to the Dossier stage; Prep to Hearing prep). */
export const TAB_STAGE: Record<WorkspaceTab, Stage> = {
  dossier: "DOSSIER",
  dates: "DOSSIER",
  rights: "RIGHTS",
  brief: "BRIEF",
  spar: "SPAR",
  prep: "HEARING_PREP",
};

export function tabForStage(stage: Stage): WorkspaceTab {
  return STAGE_BY_ID[stage].tab;
}

export function stageForTab(tab: WorkspaceTab): Stage {
  return TAB_STAGE[tab];
}

/** What the unlock rules look at. */
export interface StageContext {
  gate1Approved: boolean;
  gate2Approved: boolean;
  hasIngestion?: boolean;
  hasDossier?: boolean;
  hasRights?: boolean;
  hasBrief?: boolean;
  hasSpar?: boolean;
}

/**
 * Unlock rules (plan §13.5):
 * - I Intake and II Dossier are always open.
 * - III Rights opens as soon as the Rights Radar has run (its flags are part of the Gate 1 review, flow 1) or after Gate 1.
 * - IV Brief, V Spar and VI Hearing prep unlock after Gate 1.
 * - VII File unlocks only after Gate 2: export is impossible before it.
 */
export function isStageUnlocked(stage: Stage, ctx: StageContext): boolean {
  switch (stage) {
    case "INTAKE":
    case "DOSSIER":
      return true;
    case "RIGHTS":
      return ctx.gate1Approved || Boolean(ctx.hasRights);
    case "BRIEF":
    case "SPAR":
    case "HEARING_PREP":
      return ctx.gate1Approved;
    case "FILE":
      return ctx.gate1Approved && ctx.gate2Approved;
  }
}

/** Why a stage is locked, for tooltips and aria-descriptions; null when it is open. */
export function lockReason(stage: Stage, ctx: StageContext): string | null {
  if (isStageUnlocked(stage, ctx)) return null;
  if (stage === "FILE") {
    return ctx.gate1Approved
      ? "Unlocks after Gate 2: counsel approves the final draft."
      : "Unlocks after Gate 1 and Gate 2.";
  }
  if (stage === "RIGHTS") return "Opens when the Rights Radar has run, or after Gate 1.";
  return "Unlocks after Gate 1: counsel approves the dossier.";
}

/** Can the right-pane tab be opened? Dates follows the Dossier stage. */
export function isTabUnlocked(tab: WorkspaceTab, ctx: StageContext): boolean {
  return isStageUnlocked(stageForTab(tab), ctx);
}

export type StageState = "done" | "current" | "open" | "locked";

/**
 * Visual state of a stage on the rail, given the case's progress stage (CaseSummary.stage):
 * done = before the progress stage; current = the progress stage; open = after it but unlocked; locked otherwise.
 */
export function stageState(stage: Stage, progress: Stage, ctx: StageContext): StageState {
  if (!isStageUnlocked(stage, ctx)) return "locked";
  const d = compareStages(stage, progress);
  if (d < 0) return "done";
  if (d === 0) return "current";
  return "open";
}

/** Can a gate be acted on now? Gate 2 needs Gate 1 first. */
export function isGateReachable(gate: GateId, ctx: StageContext): boolean {
  return gate === "GATE_1_DOSSIER" ? true : ctx.gate1Approved;
}

/** Whether a gate is approved in the context. */
export function isGateApproved(gate: GateId, ctx: StageContext): boolean {
  return gate === "GATE_1_DOSSIER" ? ctx.gate1Approved : ctx.gate2Approved;
}
