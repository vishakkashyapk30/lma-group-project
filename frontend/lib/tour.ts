// Guided demos for an evaluator (docs/handoff/evaluator-demo.md). A tour is a recorded case plus nine steps, one per stage of
// the workflow; the evaluator presses Next after each and the workspace moves to that step. Only the Gate 2 step does
// anything: its Next calls the real Gate 2 approve route once (or moves on when the gate is already approved), so the
// evaluator reaches Export with the draft approved and can download the file.
//
// This module is plain TypeScript (no React): the tour types, the parser for GET /api/demo/tours[/slug], the map from a
// tour step to the workspace's stage, and the step machine (Back, Next, the Gate 2 action) the tour bar drives.
import { AGENT_NAMES, type AgentName, type Stage } from "./types";
import type { WorkspaceTab } from "./stages";

/** Tour stages, in the order the steps come. GATE_1 and GATE_2 are the two approvals; the rest are workspace stages. */
export const TOUR_STAGES = ["INTAKE", "DOSSIER", "GATE_1", "RIGHTS", "BRIEF", "SPAR", "HEARING_PREP", "GATE_2", "FILE"] as const;
export type TourStage = (typeof TOUR_STAGES)[number];

export const TOUR_TABS = ["dossier", "rights", "brief", "spar", "prep"] as const;
export type TourTab = (typeof TOUR_TABS)[number];

export type TourAction = "approve_gate_2";

export interface TourField {
  label: string;
  value: string;
}

/** Optional Hindi text of a step (scripts/demo/translate_tours_hi.py). Any field may be missing; `src` (hashes) is not read here. */
export interface TourStepHi {
  title?: string;
  caption?: string;
  filled?: { label?: string; value?: string }[];
}

export interface TourHi {
  title?: string;
  story?: string;
  variant?: Partial<TourVariant>;
}

export interface TourStep {
  stage: TourStage;
  tab: TourTab;
  title: string;
  /** Two to four sentences from the tour file (English; the Hindi, when present, is in `hi`). */
  caption: string;
  agent: AgentName | null;
  filled: TourField[];
  action: TourAction | null;
  hi?: TourStepHi;
}

export interface TourVariant {
  offence: string;
  custody: string;
  record: string;
  parity: string;
}

export interface TourSummary {
  slug: string;
  case_id: string;
  title: string;
  story: string;
  variant: TourVariant;
  hi?: TourHi;
}

export interface TourRecording {
  date: string;
  backend: string;
  model: string;
  cost_inr: number | null;
}

export interface Tour extends TourSummary {
  recorded: TourRecording | null;
  steps: TourStep[];
}

/* ── Parsing ────────────────────────────────────────────────────────────────────────────────────────────────────── */

type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const str = (v: unknown): string => (typeof v === "string" ? v : typeof v === "number" ? String(v) : "");

function parseVariant(raw: unknown): TourVariant {
  const v = isObj(raw) ? raw : {};
  return { offence: str(v.offence), custody: str(v.custody), record: str(v.record), parity: str(v.parity) };
}

const optStr = (v: unknown): string | undefined => (typeof v === "string" && v.trim() ? v : undefined);

function parseTourHi(raw: unknown): TourHi | undefined {
  if (!isObj(raw)) return undefined;
  const variant: Partial<TourVariant> = {};
  if (isObj(raw.variant)) {
    for (const k of ["offence", "custody", "record", "parity"] as const) {
      const v = optStr(raw.variant[k]);
      if (v) variant[k] = v;
    }
  }
  const out: TourHi = { title: optStr(raw.title), story: optStr(raw.story), variant };
  return out.title || out.story || Object.keys(variant).length ? out : undefined;
}

function parseStepHi(raw: unknown): TourStepHi | undefined {
  if (!isObj(raw)) return undefined;
  const filled = Array.isArray(raw.filled)
    ? raw.filled.map((f) => (isObj(f) ? { label: optStr(f.label), value: optStr(f.value) } : {}))
    : undefined;
  const out: TourStepHi = { title: optStr(raw.title), caption: optStr(raw.caption), filled };
  return out.title || out.caption || filled?.some((f) => f.label || f.value) ? out : undefined;
}

/** A tour summary from the list endpoint, or null when it lacks a slug or a case. */
export function parseTourSummary(raw: unknown): TourSummary | null {
  if (!isObj(raw)) return null;
  const slug = str(raw.slug).trim();
  const caseId = str(raw.case_id).trim();
  if (!slug || !caseId) return null;
  const hi = parseTourHi(raw.hi);
  return { slug, case_id: caseId, title: str(raw.title) || slug, story: str(raw.story), variant: parseVariant(raw.variant), ...(hi ? { hi } : {}) };
}

/** GET /api/demo/tours: the usable tours; anything that is not a list is no tours. */
export function parseTourList(raw: unknown): TourSummary[] {
  if (!Array.isArray(raw)) return [];
  return raw.map(parseTourSummary).filter((t): t is TourSummary => t !== null);
}

/** The workspace tab a stage opens on when the tour file gives none (or an unknown one). */
const DEFAULT_TAB: Record<TourStage, TourTab> = {
  INTAKE: "dossier", DOSSIER: "dossier", GATE_1: "dossier", RIGHTS: "rights", BRIEF: "brief", SPAR: "spar",
  HEARING_PREP: "prep", GATE_2: "prep", FILE: "prep",
};

function parseStep(raw: unknown): TourStep | null {
  if (!isObj(raw)) return null;
  const stage = str(raw.stage).toUpperCase() as TourStage;
  if (!(TOUR_STAGES as readonly string[]).includes(stage)) return null;
  const tab = (TOUR_TABS as readonly string[]).includes(str(raw.tab)) ? (str(raw.tab) as TourTab) : DEFAULT_TAB[stage];
  const agent = (AGENT_NAMES as readonly string[]).includes(str(raw.agent)) ? (str(raw.agent) as AgentName) : null;
  const filled = Array.isArray(raw.filled)
    ? raw.filled.filter(isObj).map((f) => ({ label: str(f.label), value: str(f.value) })).filter((f) => f.label || f.value)
    : [];
  // The Gate 2 step approves the draft whatever the file says; no other step has an action.
  const action: TourAction | null = stage === "GATE_2" ? "approve_gate_2" : null;
  const hi = parseStepHi(raw.hi);
  return { stage, tab, title: str(raw.title) || stage, caption: str(raw.caption), agent, filled, action, ...(hi ? { hi } : {}) };
}

/**
 * GET /api/demo/tours/{slug}: the tour with its steps in workflow order (INTAKE ... FILE). Steps with an unknown stage are
 * dropped; steps of the same stage keep the file's order. Null when the tour has no usable step.
 */
export function parseTour(raw: unknown): Tour | null {
  const summary = parseTourSummary(raw);
  if (!summary || !isObj(raw)) return null;
  const steps = (Array.isArray(raw.steps) ? raw.steps : [])
    .map((s, i) => ({ s: parseStep(s), i }))
    .filter((x): x is { s: TourStep; i: number } => x.s !== null)
    .sort((a, b) => TOUR_STAGES.indexOf(a.s.stage) - TOUR_STAGES.indexOf(b.s.stage) || a.i - b.i)
    .map((x) => x.s);
  if (steps.length === 0) return null;
  const rec = isObj(raw.recorded) ? raw.recorded : null;
  const recorded: TourRecording | null = rec
    ? { date: str(rec.date), backend: str(rec.backend), model: str(rec.model), cost_inr: typeof rec.cost_inr === "number" ? rec.cost_inr : null }
    : null;
  return { ...summary, recorded, steps };
}

/* ── Language ───────────────────────────────────────────────────────────────────────────────────────────────────── */

/** The tour's title, story and variant lines in the interface language: the Hindi text where the file has it, else the English. */
export function localizedTour(tour: Pick<TourSummary, "title" | "story" | "variant" | "hi">, lang: "en" | "hi"): Pick<TourSummary, "title" | "story" | "variant"> {
  const hi = lang === "hi" ? tour.hi : undefined;
  if (!hi) return { title: tour.title, story: tour.story, variant: tour.variant };
  const variant = { ...tour.variant };
  for (const k of ["offence", "custody", "record", "parity"] as const) variant[k] = hi.variant?.[k] || tour.variant[k];
  return { title: hi.title || tour.title, story: hi.story || tour.story, variant };
}

/** A step's title, caption and filled lines in the interface language, field by field with the English as the fallback. */
export function localizedStep(step: TourStep, lang: "en" | "hi"): Pick<TourStep, "title" | "caption" | "filled"> {
  const hi = lang === "hi" ? step.hi : undefined;
  if (!hi) return { title: step.title, caption: step.caption, filled: step.filled };
  return {
    title: hi.title || step.title,
    caption: hi.caption || step.caption,
    filled: step.filled.map((f, i) => ({ label: hi.filled?.[i]?.label || f.label, value: hi.filled?.[i]?.value || f.value })),
  };
}

/* ── Where a step shows in the workspace ────────────────────────────────────────────────────────────────────────── */

/** The workspace stage a tour step opens: the gates live inside Review facts (Gate 1) and Export (Gate 2). */
export function workspaceStageFor(stage: TourStage): Stage {
  switch (stage) {
    case "GATE_1":
      return "DOSSIER";
    case "GATE_2":
      return "FILE";
    default:
      return stage;
  }
}

/** The workspace section to bring into view for a step (Likely objections sit inside Draft grounds). */
export function workspaceTabFor(step: Pick<TourStep, "stage" | "tab">): WorkspaceTab {
  if (step.stage === "SPAR") return "spar";
  return step.tab;
}

/** The gate a step is about, if any. */
export function gateOfStep(stage: TourStage): "GATE_1_DOSSIER" | "GATE_2_EXPORT" | null {
  return stage === "GATE_1" ? "GATE_1_DOSSIER" : stage === "GATE_2" ? "GATE_2_EXPORT" : null;
}

/* ── The step machine ───────────────────────────────────────────────────────────────────────────────────────────── */

export interface TourDeps {
  /** Whether Gate 2 is approved for the case (the workspace's view). */
  isGate2Approved: () => boolean;
  /** POST /gates/GATE_2_EXPORT/approve. Rejects with the server's error. */
  approveGate2: () => Promise<void>;
  /** Asks the server again after a failed approval (a second evaluator may have approved it meanwhile). */
  recheckGate2?: () => Promise<boolean>;
}

export interface TourState {
  index: number;
  total: number;
  /** True while the Gate 2 approval is in flight; Back and Next wait. */
  busy: boolean;
  /** Why the last Next did not move (the approval failed); cleared by the next move. */
  error: string | null;
}

export interface TourMachine {
  getState: () => TourState;
  subscribe: (listener: () => void) => () => void;
  /** Move on. On the Gate 2 step this approves the draft first (once); on the last step it stays. */
  next: () => Promise<TourState>;
  back: () => TourState;
  /** Jump to a step (clamped). */
  goTo: (index: number) => TourState;
}

/**
 * The tour's step machine. Next and Back stay inside 0..n-1. The Gate 2 action runs at most once per machine: a second
 * Next while it is in flight waits for the same call, and once the gate is approved (by this tour or already before it)
 * Next simply moves on.
 */
export function createTourMachine(tour: Pick<Tour, "steps">, deps: TourDeps, start = 0): TourMachine {
  const total = tour.steps.length;
  const clamp = (i: number) => Math.max(0, Math.min(total - 1, Math.trunc(i)));
  let state: TourState = { index: clamp(start), total, busy: false, error: null };
  let approval: Promise<string | null> | null = null;
  let approved = false;
  const listeners = new Set<() => void>();
  const set = (patch: Partial<TourState>) => {
    state = { ...state, ...patch };
    listeners.forEach((l) => l());
    return state;
  };

  const runApproval = (): Promise<string | null> => {
    if (approved || deps.isGate2Approved()) {
      approved = true;
      return Promise.resolve(null);
    }
    if (!approval) {
      approval = (async () => {
        try {
          await deps.approveGate2();
          approved = true;
          return null;
        } catch (e) {
          const already = deps.recheckGate2 ? await deps.recheckGate2().catch(() => false) : false;
          if (already) {
            approved = true;
            return null;
          }
          approval = null; // let the evaluator try again
          return e instanceof Error && e.message ? e.message : "The draft could not be approved.";
        }
      })();
    }
    return approval;
  };

  return {
    getState: () => state,
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    async next() {
      if (state.busy) {
        await approval;
        return state;
      }
      const step = tour.steps[state.index];
      if (step?.action === "approve_gate_2") {
        set({ busy: true, error: null });
        const error = await runApproval();
        if (error) return set({ busy: false, error });
      }
      return set({ busy: false, error: null, index: clamp(state.index + 1) });
    },
    back() {
      if (state.busy) return state;
      return set({ error: null, index: clamp(state.index - 1) });
    },
    goTo(index) {
      if (state.busy) return state;
      return set({ error: null, index: clamp(index) });
    },
  };
}
