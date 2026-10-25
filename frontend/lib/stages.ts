// Workspace stages (plan §13.5). The workspace shows one step at a time. Six steps appear in the stepper: Add documents,
// Review facts, Check rights, Draft grounds, Prepare for the hearing, Export. Sparring has its own stage id (the backend
// records it) but its results appear inside Draft grounds as "Likely objections". Gate 1 follows Review facts and Gate 2
// precedes Export. Later steps unlock after Gate 1; export stays disabled until Gate 2.
import type { AgentName, GateId, Stage } from "./types";
import { STAGE_IDS } from "./types";

/**
 * Sections of the workspace. A section is where an item lives (a fact, a date, a ground, an objection); a step shows one
 * or two of them. Checklist links point at a section and an id.
 */
export const WORKSPACE_TABS = ["dossier", "dates", "rights", "brief", "spar", "prep"] as const;
export type WorkspaceTab = (typeof WORKSPACE_TABS)[number];

export const TAB_LABELS: Record<WorkspaceTab, string> = {
  dossier: "Facts",
  dates: "List of dates",
  rights: "Rights",
  brief: "Grounds",
  spar: "Likely objections",
  prep: "Hearing notes",
};

export interface StageMeta {
  id: Stage;
  /**
   * Key of the stepper button's test id (`stage-<key>`). It is not shown anywhere; the labels are plain words.
   */
  key: string;
  label: string;
  /** What this step is for, in one short sentence. */
  description: string;
  /** Gate asked for right after this step (Gate 1) or right before it (Gate 2). */
  gate?: GateId;
  gatePosition?: "after" | "before";
  /** Section shown first for this stage. */
  tab: WorkspaceTab;
  /** Agent mainly at work in this stage. */
  agent: AgentName | null;
  /** False when the stage is shown inside another step (Likely objections inside Draft grounds). */
  inStepper?: boolean;
}

export const STAGES: readonly StageMeta[] = [
  { id: "INTAKE", key: "I", label: "Add documents", tab: "dossier", agent: "MUNSHI", description: "Add the case papers. They are read and filed page by page." },
  { id: "DOSSIER", key: "II", label: "Review facts", gate: "GATE_1_DOSSIER", gatePosition: "after", tab: "dossier", agent: "PESHKAR", description: "Check each fact against the page it came from, then confirm." },
  { id: "RIGHTS", key: "III", label: "Check rights", tab: "rights", agent: "PESHKAR", description: "Procedural rights worked out from the dates in the file." },
  { id: "BRIEF", key: "IV", label: "Draft grounds", tab: "brief", agent: "VAKEEL", description: "The draft grounds, each tied to the facts and authorities it relies on." },
  { id: "SPAR", key: "V", label: "Likely objections", tab: "spar", agent: "ABHIYOJAK", inStepper: false, description: "What the prosecution is likely to say, and the reply to each point." },
  { id: "HEARING_PREP", key: "VI", label: "Prepare for the hearing", tab: "prep", agent: "VAKEEL", description: "One page to take into the hearing." },
  { id: "FILE", key: "VII", label: "Export", gate: "GATE_2_EXPORT", gatePosition: "before", tab: "prep", agent: null, description: "Approve the draft, then export the application." },
];

/** The stages that have a button in the stepper, in order. */
export const STEPPER_STAGES: readonly StageMeta[] = STAGES.filter((s) => s.inStepper !== false);

export const STAGE_BY_ID: Record<Stage, StageMeta> = Object.fromEntries(STAGES.map((s) => [s.id, s])) as Record<Stage, StageMeta>;

/** The stepper step a stage is shown in (Likely objections belong to Draft grounds). */
export function stepOf(stage: Stage): Stage {
  return stage === "SPAR" ? "BRIEF" : stage;
}

/** The step after this one, or null at the end. */
export function nextStep(stage: Stage): Stage | null {
  const at = STEPPER_STAGES.findIndex((s) => s.id === stepOf(stage));
  return STEPPER_STAGES[at + 1]?.id ?? null;
}

export const GATE_LABELS: Record<GateId, { short: string; label: string; description: string }> = {
  GATE_1_DOSSIER: {
    short: "Confirm facts",
    label: "Confirm these facts",
    description: "Once you confirm, drafting starts from these facts. If a fact changes later, you will be asked to confirm again.",
  },
  GATE_2_EXPORT: {
    short: "Approve for export",
    label: "Approve this draft for export",
    description: "Nothing is exported until you approve it. Approving records the decision as yours.",
  },
};

/** Position of a stage in the stage list (0-based). */
export function stageIndex(stage: Stage): number {
  return STAGE_IDS.indexOf(stage);
}

export function compareStages(a: Stage, b: Stage): number {
  return stageIndex(a) - stageIndex(b);
}

/** Step for a section (List of dates belongs to Review facts; Likely objections to Draft grounds). */
export const TAB_STAGE: Record<WorkspaceTab, Stage> = {
  dossier: "DOSSIER",
  dates: "DOSSIER",
  rights: "RIGHTS",
  brief: "BRIEF",
  spar: "BRIEF",
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
 * - Add documents and Review facts are always open.
 * - Every later step unlocks after Gate 1. Export is where Gate 2 is approved, and export stays disabled until Gate 2 (a 403 otherwise).
 */
export function isStageUnlocked(stage: Stage, ctx: StageContext): boolean {
  switch (stage) {
    case "INTAKE":
    case "DOSSIER":
      return true;
    case "RIGHTS":
    case "BRIEF":
    case "SPAR":
    case "HEARING_PREP":
    case "FILE":
      return ctx.gate1Approved;
  }
}

/** Why a stage is locked, for tooltips and aria-descriptions; null when it is open. */
export function lockReason(stage: Stage, ctx: StageContext): string | null {
  if (isStageUnlocked(stage, ctx)) return null;
  return "Opens once you confirm the facts.";
}

/** Can the section be opened? List of dates follows Review facts. */
export function isTabUnlocked(tab: WorkspaceTab, ctx: StageContext): boolean {
  return isStageUnlocked(stageForTab(tab), ctx);
}

export type StageState = "done" | "current" | "open" | "locked";

/**
 * Visual state of a step in the stepper, given the case's progress stage (CaseSummary.stage):
 * done = before the progress step; current = the progress step; open = after it but unlocked; locked otherwise.
 */
export function stageState(stage: Stage, progress: Stage, ctx: StageContext): StageState {
  if (!isStageUnlocked(stage, ctx)) return "locked";
  const d = compareStages(stage, stepOf(progress));
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
