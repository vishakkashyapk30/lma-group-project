// The demo backend (plan §13.1): an in-browser imitation of every FastAPI route, backed by the case-0007 fixtures.
// lib/api.ts calls these functions whenever NEXT_PUBLIC_API_BASE is unset or the API is unreachable, so the whole
// app runs offline. It keeps the backend's rules: Gate 1 before drafting, Gate 2 before export (403 otherwise,
// plan §16), refusals for outcome predictions and lay advice (plan §6.4), and an append-only event log that the
// live trace replays (plan §3.3). State lives in memory and is mirrored to sessionStorage so a reload keeps it.
import { ApiError } from "../errors";
import { formatCourtDate } from "../format";
import { RIGHTS_CHECK_LABELS } from "../labels";
import { rightsChipFromCheck, sortRightsChips } from "../status";
import type {
  AgentEvent, AgentName, BailBrief, BudgetState, CaseDossier, CaseSummary, ChatMessage, DeskBoard, DossierFieldName,
  ExportFormat, GateId, GateStatus, GroundRevision, HearingPrepCard, IngestionReport, MockPage, RightsReport,
  SparringRecord, Stage, TimelineEvent, ToolChip, UploadResponse,
} from "../types";
import { DOSSIER_FIELD_NAMES } from "../types";
import { clone, sleep } from "../utils";
import {
  attentionCount, computeChecklist, parseChecklistKey, type ResolutionState,
} from "../workspace/checklist";
import {
  ANTECEDENTS_FROM_CERTIFICATE, CUSTODY_CERTIFICATE_DOC, G6_AFTER_CERTIFICATE, MOCK_CASE_ID,
} from "./case0007";
import { buildTemplate, CASE_SEEDS, STAGE_ORDER, templateForSeed, type CaseSeed, type CaseTemplate } from "./cases";
import { MOCK_DESK_BOARD, MOCK_DESK_TITLES } from "./desk";
import {
  buildCase0007History, certificateScript, chatScript, draftScript, intakeScript, materialize, redraftScript,
  type DemoEffect, type ScriptStep,
} from "./events";
import { mockBridgeFor, mockCitationGraphFor, mockSearchLibrary } from "./library";
import { getMockPage } from "./pages";
import type { BridgeData, CitationGraphData, LibrarySearchHit } from "../types";

/* ── State ──────────────────────────────────────────────────────────────────────────────────────────────────────── */

interface DemoCase {
  summary: Pick<CaseSummary, "case_id" | "title" | "stage">;
  template: CaseTemplate;
  ingestion: IngestionReport | null;
  dossier: CaseDossier | null;
  dates: TimelineEvent[] | null;
  rights: RightsReport | null;
  brief: BailBrief | null;
  spar: SparringRecord | null;
  prep: HearingPrepCard | null;
  chat: ChatMessage[];
  budget: BudgetState;
  revisions: GroundRevision[];
  approvals: { gate1: boolean; gate2: boolean };
  resolutions: ResolutionState;
  events: AgentEvent[];
  exports: string[];
  autoScript: "intake" | null;
  /** Fields changed by a new document and waiting for counsel's re-approval (plan §7.4). */
  pendingChange: string[];
  liveCounter: number;
}

const STORAGE_KEY = "vs:demo-state:v1";
const EMPTY_BUDGET: BudgetState = { tokens_spent: 0, tokens_cap: 150000, store_calls: {} };

let cases: Map<string, DemoCase> | null = null;
let deskOpened: Set<string> = new Set();
const subscribers = new Map<string, Set<(e: AgentEvent) => void>>();
const runners = new Map<string, Promise<void>>();
const busyListeners = new Set<(caseId: string, busy: boolean) => void>();
const busy = new Set<string>();

/** Multiplier on script delays: 1 is the normal demo pace; 0 plays scripts instantly (useful for e2e). */
let speed = (() => {
  const raw = typeof process !== "undefined" ? process.env.NEXT_PUBLIC_DEMO_SPEED : undefined;
  const n = raw ? Number(raw) : NaN;
  return Number.isFinite(n) && n >= 0 ? n : 1;
})();

/** Set the demo pace (1 = normal, 0 = instant). */
export function setDemoSpeed(value: number): void {
  speed = Math.max(0, value);
}

export function getDemoSpeed(): number {
  return speed;
}

function emptyCase(summary: DemoCase["summary"], template: CaseTemplate): DemoCase {
  return {
    summary, template, ingestion: null, dossier: null, dates: null, rights: null, brief: null, spar: null, prep: null,
    chat: [], budget: clone(EMPTY_BUDGET), revisions: [], approvals: { gate1: false, gate2: false },
    resolutions: { acknowledged: [], resolved: {} }, events: [], exports: [], autoScript: null, pendingChange: [],
    liveCounter: 0,
  };
}

function historyFor(seed: CaseSeed): AgentEvent[] {
  const id = seed.summary.case_id;
  switch (seed.history) {
    case "none":
      return [];
    case "intake":
      return materialize(id, intakeScript(), "2025-01-27T04:30:00Z", 4000, "intake");
    case "gate1":
      return [
        ...materialize(id, intakeScript(), "2025-01-27T04:30:00Z", 4000, "intake"),
        ...materialize(id, [{ kind: "GATE_APPROVED", actor: "counsel", inputs: { gate: "GATE_1_DOSSIER", acknowledged: ["antecedents"] }, outputs: { gate: "GATE_1_DOSSIER" } }], "2025-01-27T06:10:00Z", 60000, "gate1"),
      ];
    case "draft":
    case "all":
      return buildCase0007History(id);
    case "exported":
      return [
        ...buildCase0007History(id),
        ...materialize(id, [
          { kind: "GATE_APPROVED", actor: "counsel", inputs: { gate: "GATE_2_EXPORT", acknowledged: Object.keys(seed.resolved) }, outputs: { gate: "GATE_2_EXPORT" } },
          { kind: "TOOL_CALL", actor: "VAKEEL", tool: "export", inputs: { format: "DOCX" } },
          { kind: "TOOL_RESULT", actor: "VAKEEL", tool: "export", outputs: { files: seed.exports ?? [] } },
        ], "2025-02-04T05:00:00Z", 20000, "export"),
      ];
  }
}

function fromSeed(seed: CaseSeed): DemoCase {
  const t = templateForSeed(seed);
  const c = emptyCase({ ...seed.summary }, t);
  if (seed.has.ingestion) c.ingestion = clone(t.ingestion);
  if (seed.has.dossier) c.dossier = clone(t.dossier);
  if (seed.has.dossier) c.dates = clone(t.dates);
  if (seed.has.rights) c.rights = clone(t.rights);
  if (seed.has.brief) {
    c.brief = clone(t.brief);
    c.revisions = clone(t.revisions);
    c.budget = clone(t.budget);
  }
  if (seed.has.spar) c.spar = clone(t.spar);
  if (seed.has.prep) c.prep = clone(t.prep);
  if (seed.has.chat) c.chat = clone(t.chat);
  c.approvals = { ...seed.approvals };
  c.resolutions = {
    acknowledged: [...seed.acknowledged],
    resolved: Object.fromEntries(Object.entries(seed.resolved).map(([k, note]) => [k, { note, at: "2025-02-03T10:00:00+05:30" }])),
  };
  c.events = historyFor(seed);
  c.exports = [...(seed.exports ?? [])];
  c.autoScript = seed.autoScript ?? null;
  return c;
}

type Persisted = { cases: [string, Omit<DemoCase, "template">][]; deskOpened: string[] };

function persist(): void {
  if (!cases || typeof window === "undefined") return;
  try {
    const data: Persisted = {
      cases: [...cases.entries()].map(([id, c]) => {
        const { template: _t, ...rest } = c;
        return [id, rest];
      }),
      deskOpened: [...deskOpened],
    };
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {
    /* storage full or unavailable: the demo still works in memory */
  }
}

function restore(): Map<string, DemoCase> | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as Persisted;
    const map = new Map<string, DemoCase>();
    for (const [id, rest] of data.cases) {
      const seed = CASE_SEEDS.find((s) => s.summary.case_id === id);
      const template = seed ? templateForSeed(seed) : buildTemplate(id, pseudonymsFor(id));
      map.set(id, { ...rest, template });
    }
    deskOpened = new Set(data.deskOpened ?? []);
    return map;
  } catch {
    return null;
  }
}

function store(): Map<string, DemoCase> {
  if (!cases) {
    cases = restore() ?? new Map(CASE_SEEDS.map((s) => [s.summary.case_id, fromSeed(s)]));
  }
  return cases;
}

/** Forget every change made in the demo and start again from the seeds. */
export function resetDemo(): void {
  cases = null;
  deskOpened = new Set();
  runners.clear();
  busy.clear();
  if (typeof window !== "undefined") {
    try {
      window.sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }
}

function pseudonymsFor(caseId: string) {
  const n = Number(caseId.replace(/\D/g, "")) || 99;
  return { fir: `${n}/2025`, ps: `PS-${(n % 9) + 1}`, accused: `Accused-${n}` };
}

function getCaseState(caseId: string): DemoCase {
  const c = store().get(caseId);
  if (!c) throw new ApiError(404, `No case ${caseId} in the demo.`);
  return c;
}

function bumpStage(c: DemoCase, stage: Stage): void {
  if (STAGE_ORDER.indexOf(stage) > STAGE_ORDER.indexOf(c.summary.stage)) c.summary.stage = stage;
}

function wait(ms: number): Promise<void> {
  return speed === 0 ? Promise.resolve() : sleep(ms * speed);
}

/* ── Events ─────────────────────────────────────────────────────────────────────────────────────────────────────── */

function emit(caseId: string, step: ScriptStep): AgentEvent {
  const c = getCaseState(caseId);
  c.liveCounter += 1;
  const short = caseId.replace(/[^0-9a-z]/gi, "");
  const event: AgentEvent = {
    event_id: `evt-${short}-live-${Date.now().toString(36)}-${String(c.liveCounter).padStart(4, "0")}`,
    case_id: caseId,
    ts: new Date().toISOString(),
    kind: step.kind,
    actor: step.actor,
    tool: step.tool ?? null,
    inputs: step.inputs ?? {},
    outputs: step.outputs ?? {},
    sources: step.sources ?? [],
    parent_id: c.events.length ? c.events[c.events.length - 1].event_id : null,
  };
  c.events.push(event);
  persist();
  subscribers.get(caseId)?.forEach((fn) => fn(event));
  return event;
}

function setBusy(caseId: string, value: boolean): void {
  if (value) busy.add(caseId);
  else busy.delete(caseId);
  busyListeners.forEach((l) => l(caseId, value));
}

/** True while a demo script is playing for the case. */
export function isDemoBusy(caseId: string): boolean {
  return busy.has(caseId);
}

export function onDemoBusyChange(listener: (caseId: string, busy: boolean) => void): () => void {
  busyListeners.add(listener);
  return () => busyListeners.delete(listener);
}

function applyEffect(c: DemoCase, effect: DemoEffect): void {
  const t = c.template;
  switch (effect) {
    case "ingestion":
      c.ingestion = clone(t.ingestion);
      bumpStage(c, "INTAKE");
      break;
    case "dossier":
      c.dossier = clone(t.dossier);
      bumpStage(c, "DOSSIER");
      break;
    case "dates":
      c.dates = clone(t.dates);
      break;
    case "rights":
      c.rights = clone(t.rights);
      break;
    case "gate1Opened":
      bumpStage(c, "DOSSIER");
      break;
    case "brief":
      c.brief = clone(t.brief);
      c.revisions = [];
      bumpStage(c, "BRIEF");
      break;
    case "spar":
      c.spar = clone(t.spar);
      bumpStage(c, "SPAR");
      break;
    case "prep":
      c.prep = clone(t.prep);
      break;
    case "gate2Opened":
      bumpStage(c, "SPAR");
      break;
    case "budget":
      c.budget = clone(t.budget);
      break;
    case "certificateIngested": {
      const ing = c.ingestion ?? clone(t.ingestion);
      if (!ing.documents.some((d) => d.doc_id === CUSTODY_CERTIFICATE_DOC.doc_id)) {
        ing.documents.push(clone(CUSTODY_CERTIFICATE_DOC));
      }
      ing.gaps = ing.gaps.filter((g) => !/custody certificate/i.test(g.item));
      ing.questions = ing.questions.filter((q) => !/custody certificate/i.test(q));
      ing.filed = { ...ing.filed, chunks: ing.filed.chunks + 3 };
      c.ingestion = ing;
      break;
    }
    case "certificateDossier":
      if (c.dossier) {
        c.dossier.fields.antecedents = clone(ANTECEDENTS_FROM_CERTIFICATE);
        c.dossier.open_questions = c.dossier.open_questions.filter((q) => !/other pending cases/i.test(q));
      }
      c.pendingChange = ["antecedents"];
      // Counsel must re-approve the changed dossier (plan §7.4, flow 4); the draft is kept but cannot be exported.
      c.approvals = { gate1: false, gate2: false };
      c.summary.stage = "DOSSIER";
      break;
    case "certificateRights":
      if (c.rights) {
        const check = c.rights.checks.find((x) => x.check === "undertrial_limit");
        if (check) {
          check.status = "NOT_YET";
          check.detail = "First-time offender (custody certificate: no other case). The one-third threshold is 852 days from arrest on 20.08.2024: about 20.12.2026.";
          check.uses = ["custody_days", "sections", "antecedents"];
          check.dates = { arrest_date: "2024-08-20", threshold_date: "2026-12-20" };
        }
      }
      break;
    case "redraft":
      if (c.brief) {
        const g6 = c.brief.grounds.find((g) => g.id === "G6");
        if (g6 && c.pendingChange.includes("antecedents")) {
          c.revisions = [
            ...c.revisions.filter((r) => r.ground_id !== "G6"),
            {
              ground_id: "G6",
              reason: (c.dossier?.fields.antecedents.source?.doc ?? "").startsWith("d7")
                ? "New document: the custody certificate verified antecedents. Only this ground was redrafted; the others stayed word for word."
                : "Counsel edited antecedents. Only this ground was redrafted; the others stayed word for word.",
              changed: ["antecedents"],
              previous_argument: g6.argument,
              at: new Date().toISOString(),
            },
          ];
          const fromCertificate = (c.dossier?.fields.antecedents.source?.doc ?? "").startsWith("d7");
          g6.argument = fromCertificate ? G6_AFTER_CERTIFICATE : G6_PER_COUNSEL;
          g6.check = "SUPPORTED";
          g6.state = "CURRENT";
          g6.depends_on = { ...g6.depends_on, facts: { ...g6.depends_on.facts, antecedents: "h:5b19" } };
          c.brief.open_issues = c.brief.open_issues.filter((i) => !/antecedents/i.test(i.item));
          delete c.resolutions.resolved["NEEDS_REVIEW:G6"];
        }
        c.pendingChange = [];
        bumpStage(c, "BRIEF");
        if (c.spar) bumpStage(c, "SPAR");
      }
      break;
  }
}

const G6_PER_COUNSEL =
  "Counsel's instructions are that the applicant has no other pending case [F:antecedents] (per counsel, not on record); the absence of antecedents weighs in favour of bail [A:DLHC-2020-0733#8].";

function runScript(caseId: string, steps: ScriptStep[]): Promise<void> {
  const previous = runners.get(caseId) ?? Promise.resolve();
  const next = previous.then(async () => {
    setBusy(caseId, true);
    try {
      for (const step of steps) {
        await wait(step.delay ?? 380);
        const c = store().get(caseId);
        if (!c) return;
        if (step.effect) applyEffect(c, step.effect);
        emit(caseId, step);
      }
    } finally {
      setBusy(caseId, false);
      persist();
    }
  });
  runners.set(caseId, next.catch(() => undefined));
  return next;
}

/**
 * Subscribe to a case's events, as the SSE route does: first every stored event after `lastEventId` (all of them when
 * it is null or unknown), then live events. A case seeded with an automatic script starts it on first subscribe.
 */
export function subscribeDemoEvents(caseId: string, lastEventId: string | null, onEvent: (e: AgentEvent) => void): () => void {
  const c = store().get(caseId);
  let cancelled = false;
  if (c) {
    const idx = lastEventId ? c.events.findIndex((e) => e.event_id === lastEventId) : -1;
    const backlog = c.events.slice(idx + 1);
    queueMicrotask(() => {
      if (!cancelled) backlog.forEach(onEvent);
    });
    if (c.autoScript === "intake") {
      c.autoScript = null;
      persist();
      void runScript(caseId, [{ kind: "AGENT_MESSAGE", actor: "MUNSHI", outputs: { text: "New bundle received: bundle_1.pdf" }, delay: 900 }, ...intakeScript().slice(1)]);
    }
  }
  const set = subscribers.get(caseId) ?? new Set();
  set.add(onEvent);
  subscribers.set(caseId, set);
  return () => {
    cancelled = true;
    set.delete(onEvent);
  };
}

/** The stored event log of a case (the trace drawer's history). */
export function getDemoEvents(caseId: string): AgentEvent[] {
  return clone(store().get(caseId)?.events ?? []);
}

/** Counsel's resolutions the demo starts with (seeded cases), for the workspace's initial checklist state. */
export function getDemoResolutions(caseId: string): ResolutionState {
  return clone(store().get(caseId)?.resolutions ?? { acknowledged: [], resolved: {} });
}

/* ── Case routes (/api/cases) ───────────────────────────────────────────────────────────────────────────────────── */

const QUIET_RIGHTS = new Set(["OK", "NOT_APPLICABLE", "A", "B", "C", "D"]);

function rightsChips(r: RightsReport | null): string[] {
  if (!r) return [];
  const chips = r.checks
    .filter((c) => !QUIET_RIGHTS.has(c.status))
    .map((c) => {
      const daysLeft = /(\d+) days left/.exec(c.detail ?? "")?.[1];
      return rightsChipFromCheck(c, daysLeft ? `${daysLeft} days left` : undefined);
    });
  return sortRightsChips(chips).map((c) => c.raw).slice(0, 4);
}

function summaryOf(c: DemoCase): CaseSummary {
  return {
    ...c.summary,
    rights_chips: rightsChips(c.rights),
    needs_attention:
      attentionCount({ dossier: c.dossier, brief: c.brief, spar: c.spar }, c.resolutions, c.approvals) + c.pendingChange.length,
  };
}

/** Delay that makes the demo feel like a network call. */
async function latency(): Promise<void> {
  await wait(120);
}

export async function listCases(): Promise<CaseSummary[]> {
  await latency();
  return [...store().values()].map(summaryOf);
}

export async function createCase(body: { title?: string | null } = {}): Promise<CaseSummary> {
  await latency();
  const map = store();
  const max = Math.max(0, ...[...map.keys()].map((k) => Number(k.replace(/\D/g, "")) || 0));
  const id = `case-${String(max + 1).padStart(4, "0")}`;
  const c = emptyCase({ case_id: id, title: body.title?.trim() || "New case · awaiting documents", stage: "INTAKE" }, buildTemplate(id, pseudonymsFor(id)));
  map.set(id, c);
  persist();
  return summaryOf(c);
}

export async function getCase(caseId: string): Promise<CaseSummary> {
  await latency();
  return summaryOf(getCaseState(caseId));
}

function need<T>(value: T | null, what: string, caseId: string): T {
  if (value === null) throw new ApiError(404, `No ${what} for ${caseId} yet.`);
  return clone(value);
}

export async function getIngestion(caseId: string): Promise<IngestionReport> {
  await latency();
  return need(getCaseState(caseId).ingestion, "ingestion report", caseId);
}

export async function getDossier(caseId: string): Promise<CaseDossier> {
  await latency();
  return need(getCaseState(caseId).dossier, "dossier", caseId);
}

export async function editField(caseId: string, field: string, body: { value: unknown }): Promise<CaseDossier> {
  await latency();
  const c = getCaseState(caseId);
  if (!c.dossier) throw new ApiError(404, `No dossier for ${caseId} yet.`);
  if (!(DOSSIER_FIELD_NAMES as readonly string[]).includes(field)) throw new ApiError(422, `Unknown dossier field ${field}.`);
  const name = field as DossierFieldName;
  // Counsel's edit: status USER_EDITED, and the court record no longer backs the value (plan §7.1).
  (c.dossier.fields as unknown as Record<string, unknown>)[name] = { value: body.value, source: null, status: "USER_EDITED" };
  if (c.approvals.gate1) {
    c.pendingChange = Array.from(new Set([...c.pendingChange, name]));
    c.approvals = { gate1: false, gate2: false };
  }
  emit(caseId, { kind: "USER_ACTION", actor: "counsel", inputs: { action: "edit_field", field: name, value: body.value }, outputs: { status: "USER_EDITED" } });
  persist();
  return clone(c.dossier);
}

export async function getDates(caseId: string): Promise<TimelineEvent[]> {
  await latency();
  return need(getCaseState(caseId).dates, "List of Dates", caseId);
}

export async function getRights(caseId: string): Promise<RightsReport> {
  await latency();
  return need(getCaseState(caseId).rights, "Rights Radar report", caseId);
}

export async function startDraft(caseId: string): Promise<Record<string, string>> {
  await latency();
  const c = getCaseState(caseId);
  if (!c.dossier) throw new ApiError(409, "Nothing to draft from yet: upload the case file first.");
  if (!c.approvals.gate1) throw new ApiError(409, "Gate 1 is not approved: counsel must approve the dossier before drafting.");
  const runId = `run-${Date.now().toString(36)}`;
  void runScript(caseId, draftScript());
  return { status: "started", run_id: runId };
}

export async function getBrief(caseId: string): Promise<BailBrief> {
  await latency();
  return need(getCaseState(caseId).brief, "brief", caseId);
}

/** Change highlights for the Brief tab (plan §10). Demo-only helper; the real backend derives them from the log. */
export async function getBriefRevisions(caseId: string): Promise<GroundRevision[]> {
  await latency();
  return clone(getCaseState(caseId).revisions);
}

export async function getSpar(caseId: string): Promise<SparringRecord> {
  await latency();
  return need(getCaseState(caseId).spar, "sparring record", caseId);
}

export async function getPrep(caseId: string): Promise<HearingPrepCard> {
  await latency();
  return need(getCaseState(caseId).prep, "hearing-prep card", caseId);
}

export async function getBudget(caseId: string): Promise<BudgetState> {
  await latency();
  return clone(getCaseState(caseId).budget);
}

/** Demo page facsimile for the PDF viewer (the real route returns a page image). */
export async function getPage(caseId: string, docId: string, page: number): Promise<MockPage> {
  getCaseState(caseId);
  const p = getMockPage(docId, page);
  if (!p) throw new ApiError(404, `No page ${page} of ${docId} in the demo.`);
  return clone(p);
}

/* ── Upload (/api/cases/{id}/upload, /audio) ────────────────────────────────────────────────────────────────────── */

export async function uploadFiles(caseId: string, fileNames: string[]): Promise<UploadResponse> {
  await latency();
  const c = getCaseState(caseId);
  if (fileNames.length === 0) throw new ApiError(422, "No files received.");
  const certificate = c.dossier !== null || fileNames.some((n) => /custody|certificate/i.test(n));
  if (certificate && c.dossier) {
    void runScript(caseId, certificateScript(fileNames[0]));
    return { case_id: caseId, accepted: fileNames, questions: [] };
  }
  if (c.summary.title.startsWith("New case")) c.summary.title = `New bundle · ${fileNames[0]}`;
  void runScript(caseId, intakeScript(fileNames[0]));
  return { case_id: caseId, accepted: fileNames, questions: [...c.template.ingestion.questions] };
}

/** Dictation (plan §4.5, flow 5): Munshi transcribes, reads back dates and sections, and files them as USER_STATED. */
export async function uploadAudio(caseId: string, fileName = "dictation.webm"): Promise<UploadResponse> {
  await latency();
  const c = getCaseState(caseId);
  const readBack = "I heard: arrested on 20.08.2024; sections 318(4) and 316(2) BNS; he is the sole earning member of his family. Please confirm. These are filed as stated by counsel, not on record.";
  const turn = `turn ${c.chat.filter((m) => m.role === "counsel").length + 1}`;
  const message: ChatMessage = {
    message_id: `m-${Date.now().toString(36)}`, case_id: caseId, role: "agent", agent: "MUNSHI", text: readBack,
    chips: [{ tool: "transcribe", store: null }, { tool: "translate", store: null }, { tool: "file_item", store: "case.facts" }], refused: false,
  };
  void runScript(caseId, [
    { kind: "USER_ACTION", actor: "counsel", inputs: { action: "dictate", file: fileName }, delay: 100 },
    { kind: "TOOL_CALL", actor: "MUNSHI", tool: "transcribe", inputs: { lang: "hi", keep_audio: false } },
    { kind: "TOOL_RESULT", actor: "MUNSHI", tool: "transcribe", outputs: { seconds: 42, deleted_audio: true } },
    { kind: "TOOL_CALL", actor: "MUNSHI", tool: "translate", inputs: { src: "hi", tgt: "en" } },
    { kind: "STORE_WRITE", actor: "MUNSHI", tool: "file_item", inputs: { store: "case.facts" }, outputs: { status: "USER_STATED", chat: turn } },
    { kind: "AGENT_MESSAGE", actor: "MUNSHI", outputs: { text: readBack, status: "done" } },
  ]).then(() => {
    const cs = store().get(caseId);
    if (!cs) return;
    cs.chat.push(message);
    if (cs.dossier && cs.dossier.fields.personal.status !== "USER_EDITED") {
      cs.dossier.fields.personal = { value: ["sole earning member"], source: { chat: turn }, status: "USER_STATED" };
    }
    persist();
  });
  return { case_id: caseId, accepted: [fileName], questions: [readBack] };
}

/* ── Chat (/api/cases/{id}/chat) ────────────────────────────────────────────────────────────────────────────────── */

interface Routed {
  agent: AgentName;
  text: string;
  chips: ToolChip[];
  refused: boolean;
}

const PREDICTION_RE = /\b(chances?|predict\w*|probab\w*|odds|likel(y|ihood)|grant rate|success rate|percent(age)?|will (he|she|they|my client|the applicant) (get|be granted|be released)|win)\b/i;
const LAY_RE = /\b(i am the accused|i'm the accused|my (son|husband|brother|father|wife|daughter|mother) (is|was|has been)|what should i do|can i get bail|am i eligible)\b/i;

function routeChat(text: string, c: DemoCase): Routed {
  const q = text.toLowerCase();
  if (LAY_RE.test(text)) {
    return {
      agent: "SUTRADHAR", refused: true, chips: [],
      text: "This assistant is for counsel and can't advise accused persons or the public. For free legal aid, call the NALSA helpline on 15100.",
    };
  }
  if (PREDICTION_RE.test(text)) {
    return {
      agent: "SUTRADHAR", refused: true, chips: [],
      text: "I can't predict outcomes or give grant rates. I can show the grounds with their sources, the likely objections and the hearing-prep card.",
    };
  }
  const d = c.dossier?.fields;
  if (!d) {
    return {
      agent: "MUNSHI", refused: false, chips: [{ tool: "search_pages", store: null }],
      text: "Nothing is filed for this case yet. Drop the bundle in the case-file pane and I will read, split and file it.",
    };
  }
  const arrest = d.arrest_date.value ? formatCourtDate(d.arrest_date.value) : "the arrest date";
  if (/\b(479|436a|undertrial|eligible|default bail|187|entitle|rights?)\b/.test(q)) {
    const ut = c.rights?.checks.find((x) => x.check === "undertrial_limit");
    const db = c.rights?.checks.find((x) => x.check === "default_bail");
    return {
      agent: "PESHKAR", refused: false, chips: [{ tool: "rights_check", store: null }, { tool: "date_calc", store: "case.timeline" }],
      text: `Rights Radar (possible entitlements to check, not advice): ${RIGHTS_CHECK_LABELS.undertrial_limit} ${ut?.status ?? "CHECK"}: ${ut?.detail ?? "not run yet"} ${RIGHTS_CHECK_LABELS.default_bail} ${db?.status ?? "CHECK"} [${db?.rule ?? "BNSS s.187(3)"}].`,
    };
  }
  if (/\b(custody|days|how long|detained|jail)\b/.test(q)) {
    return {
      agent: "PESHKAR", refused: false, chips: [{ tool: "date_calc", store: "case.timeline" }, { tool: "rights_check", store: null }],
      text: `Custody: ${d.custody_days.value ?? "?"} days [date_calc from arrest ${arrest}]; s.479 not yet reached.`,
    };
  }
  if (/\b(bns|ipc|equivalent|420|406|318|316|section|concordance)\b/.test(q)) {
    return {
      agent: "SUTRADHAR", refused: false, chips: [{ tool: "map_section", store: "law.concordance" }, { tool: "transfer_check", store: "law.concordance" }],
      text: "IPC 420 → BNS 318(4), same text (maximum 7 years, non-bailable): precedents apply as they are. IPC 406 → BNS 316(2): the maximum rose from 3 to 5 years (CHANGED): qualify precedents decided under IPC 406.",
    };
  }
  if (/\b(parity|co-accused|precedent|supreme court|sc case|authority|judgment)\b/.test(q)) {
    return {
      agent: "SUTRADHAR", refused: false,
      chips: [{ tool: "search_reasoning", store: "caselaw.reasoning" }, { tool: "citations", store: "caselaw.citations" }, { tool: "search_objections", store: "advocacy.objections" }],
      text: "DLHC-2022-1187 ¶14 (IPC 420, parity) rests on SC-2014-0463 ¶9; both are good law. Expect the objection that the applicant's role differs (DLHC-2023-0911 ¶6).",
    };
  }
  if (/\b(oppose|objection|prosecution|state usually|ndps|argue)\b/.test(q)) {
    return {
      agent: "SUTRADHAR", refused: false, chips: [{ tool: "search_objections", store: "advocacy.objections" }, { tool: "get_statute", store: "law.statutes" }],
      text: "In cheating cases the State usually argues the role of the applicant, the amount involved, and the risk of influencing the complainant before examination (advocacy.objections). NDPS s.37 does not apply here: statutory bar NOT_APPLICABLE.",
    };
  }
  if (/\b(charge ?sheet|investigation)\b/.test(q)) {
    const cs = d.charge_sheet.value;
    return {
      agent: "PESHKAR", refused: false, chips: [{ tool: "get_fact", store: "case.facts" }, { tool: "get_timeline", store: "case.timeline" }],
      text: cs?.filed ? `Charge sheet filed on ${formatCourtDate(cs.date)} [${d.charge_sheet.source?.doc ?? "order sheet"}, p.${d.charge_sheet.source?.page ?? "?"}]; trial stage: ${d.trial_stage.value ?? "unknown"}.` : "No charge sheet on record yet.",
    };
  }
  if (/\b(sessions|order|said|antecedent|reject|remand)\b/.test(q)) {
    return {
      agent: "SUTRADHAR", refused: false, chips: [{ tool: "search_case_docs", store: "case.docs" }],
      text: "The Sessions Court order of 30.09.2024 (d4, p.10) does not mention antecedents. It rejected bail on the seriousness of the allegations and because investigation was at a nascent stage.",
    };
  }
  return {
    agent: "SUTRADHAR", refused: false, chips: [{ tool: "search_case_docs", store: "case.docs" }, { tool: "get_fact", store: "case.facts" }],
    text: "I found nothing on that in the case file or the stores. Ask about custody, sections, rights, precedents, objections or the earlier orders.",
  };
}

export async function postChat(caseId: string, body: { text: string }): Promise<ChatMessage> {
  const c = getCaseState(caseId);
  const text = body.text.trim();
  if (!text) throw new ApiError(422, "Empty message.");
  const counsel: ChatMessage = { message_id: `m-${Date.now().toString(36)}c`, case_id: caseId, role: "counsel", agent: null, text, chips: [], refused: false };
  c.chat.push(counsel);
  emit(caseId, { kind: "USER_ACTION", actor: "counsel", inputs: { action: "chat", text } });
  const routed = routeChat(text, c);
  await runScript(caseId, chatScript(routed.chips, routed.agent, routed.refused));
  const reply: ChatMessage = {
    message_id: `m-${Date.now().toString(36)}a`, case_id: caseId, role: "agent", agent: routed.agent, text: routed.text,
    chips: routed.chips, refused: routed.refused,
  };
  getCaseState(caseId).chat.push(reply);
  persist();
  return clone(reply);
}

export async function getChatHistory(caseId: string): Promise<ChatMessage[]> {
  await latency();
  return clone(getCaseState(caseId).chat);
}

/* ── Gates (/api/cases/{id}/gates) ──────────────────────────────────────────────────────────────────────────────── */

function gateStatus(c: DemoCase, gate: GateId): GateStatus {
  const checklist = computeChecklist(gate, { dossier: c.dossier, brief: c.brief, spar: c.spar }, c.resolutions, c.approvals);
  const approved = gate === "GATE_1_DOSSIER" ? c.approvals.gate1 : c.approvals.gate2;
  return {
    gate,
    open: !approved,
    unresolved_unsupported: checklist.blocking.filter((i) => i.kind === "UNSUPPORTED").map((i) => i.ref),
    unresolved_needs_review: checklist.blocking.filter((i) => i.kind === "NEEDS_REVIEW").map((i) => i.ref),
    unresolved_unanswered: checklist.blocking.filter((i) => i.kind === "UNANSWERED").map((i) => i.ref),
  };
}

export async function getGate(caseId: string, gate: GateId): Promise<GateStatus> {
  await latency();
  return gateStatus(getCaseState(caseId), gate);
}

function absorbAcknowledged(c: DemoCase, acknowledged: string[]): void {
  for (const entry of acknowledged) {
    const parsed = parseChecklistKey(entry);
    if (!parsed) {
      const key = `UNSUPPORTED:${entry}`;
      if (!c.resolutions.acknowledged.includes(key)) c.resolutions.acknowledged.push(key);
    } else if (parsed.kind === "UNSUPPORTED") {
      if (!c.resolutions.acknowledged.includes(entry)) c.resolutions.acknowledged.push(entry);
    } else if (!c.resolutions.resolved[entry]) {
      c.resolutions.resolved[entry] = { note: null, at: new Date().toISOString() };
    }
  }
}

export async function approveGate(caseId: string, gate: GateId, body: { acknowledged_fields: string[] }): Promise<GateStatus> {
  await latency();
  const c = getCaseState(caseId);
  if (gate === "GATE_1_DOSSIER" && !c.dossier) throw new ApiError(409, "There is no dossier to approve yet.");
  if (gate === "GATE_2_EXPORT" && !c.approvals.gate1) throw new ApiError(409, "Gate 2 needs Gate 1 first.");
  if (gate === "GATE_2_EXPORT" && !c.brief) throw new ApiError(409, "There is no draft to approve yet.");
  absorbAcknowledged(c, body.acknowledged_fields ?? []);
  const status = gateStatus(c, gate);
  const blocking = status.unresolved_unsupported.length + status.unresolved_needs_review.length + status.unresolved_unanswered.length;
  if (blocking > 0) throw new ApiError(409, `${blocking} checklist item(s) are unresolved.`, status);
  const changed = [...c.pendingChange];
  if (gate === "GATE_1_DOSSIER") {
    c.approvals.gate1 = true;
    bumpStage(c, c.brief ? (c.spar ? "SPAR" : "BRIEF") : "BRIEF");
  } else {
    c.approvals.gate2 = true;
    bumpStage(c, "FILE");
  }
  emit(caseId, { kind: "GATE_APPROVED", actor: "counsel", inputs: { gate, acknowledged: body.acknowledged_fields ?? [] }, outputs: { gate } });
  persist();
  // Re-approval of a changed dossier: only the affected grounds are redrafted (plan §10, flow 4).
  if (gate === "GATE_1_DOSSIER" && changed.length && c.brief) {
    const stale = changed.includes("antecedents") ? ["G6"] : [];
    void runScript(caseId, redraftScript(changed, stale, c.brief.grounds.length - stale.length));
  } else if (gate === "GATE_1_DOSSIER") {
    c.pendingChange = [];
  }
  return gateStatus(c, gate);
}

/* ── Export (/api/cases/{id}/export) ────────────────────────────────────────────────────────────────────────────── */

export async function exportCase(caseId: string, body: { format: ExportFormat }): Promise<string[]> {
  await latency();
  const c = getCaseState(caseId);
  // Enforced here as in the backend: nothing leaves without counsel's Gate 2 approval (plan §16).
  if (!c.approvals.gate2) throw new ApiError(403, "Export is blocked until counsel approves Gate 2.");
  const ext = body.format === "PDF" ? "pdf" : "docx";
  const files = [
    `exports/${caseId}/bail_application.${ext}`,
    `exports/${caseId}/list_of_dates.${ext}`,
    `exports/${caseId}/objections_sheet.${ext}`,
    `exports/${caseId}/hearing_card.pdf`,
  ];
  c.exports = Array.from(new Set([...c.exports, ...files]));
  void runScript(caseId, [
    { kind: "TOOL_CALL", actor: "VAKEEL", tool: "export", inputs: { format: body.format }, delay: 100 },
    { kind: "TOOL_RESULT", actor: "VAKEEL", tool: "export", outputs: { files } },
    { kind: "AGENT_MESSAGE", actor: "VAKEEL", outputs: { text: `Exported ${files.length} files (${body.format}). AI-generated draft: check against your court's rules.`, status: "done" } },
  ]);
  return files;
}

export function getDemoExports(caseId: string): string[] {
  return [...(store().get(caseId)?.exports ?? [])];
}

/* ── Desk (/api/desk) ───────────────────────────────────────────────────────────────────────────────────────────── */

export async function deskUpload(fileName: string): Promise<string[]> {
  await wait(600);
  if (!fileName) throw new ApiError(422, "No file received.");
  return MOCK_DESK_BOARD.cards.map((c) => c.case_id);
}

export async function getDeskBoard(): Promise<DeskBoard> {
  await latency();
  return clone(MOCK_DESK_BOARD);
}

/** Open a desk case in the workspace: Munshi, Peshkar and the Rights Radar have run; it still needs its own Gate 1. */
export async function openDeskCase(caseId: string): Promise<CaseSummary> {
  await latency();
  const map = store();
  const card = MOCK_DESK_BOARD.cards.find((c) => c.case_id === caseId);
  if (!card && !map.has(caseId)) throw new ApiError(404, `No case ${caseId} on the desk.`);
  if (!map.has(caseId)) {
    const t = buildTemplate(caseId, pseudonymsFor(caseId));
    const c = emptyCase({ case_id: caseId, title: MOCK_DESK_TITLES[caseId] ?? `Desk case ${caseId}`, stage: "DOSSIER" }, t);
    c.ingestion = clone(t.ingestion);
    c.dossier = clone(t.dossier);
    c.dates = clone(t.dates);
    c.rights = clone(t.rights);
    c.events = materialize(caseId, intakeScript(), "2025-02-03T01:00:00Z", 1500, "desk");
    map.set(caseId, c);
    deskOpened.add(caseId);
    persist();
  }
  return summaryOf(getCaseState(caseId));
}

/* ── Library (/api/library) ─────────────────────────────────────────────────────────────────────────────────────── */

export async function searchLibrary(q: string): Promise<LibrarySearchHit[]> {
  await latency();
  return clone(mockSearchLibrary(q));
}

export async function getCitationGraph(docId: string): Promise<CitationGraphData> {
  await latency();
  const g = mockCitationGraphFor(docId);
  if (!g) throw new ApiError(404, `No citation graph for ${docId} in the demo.`);
  return clone(g);
}

export async function getBridge(code: string, section: string): Promise<BridgeData> {
  await latency();
  const b = mockBridgeFor(code, section);
  if (!b) throw new ApiError(404, `No concordance edge for ${code} ${section} in the demo. Try IPC 420 or IPC 406.`);
  return clone(b);
}

/** The demo's default case (the worked example). */
export const DEMO_DEFAULT_CASE_ID = MOCK_CASE_ID;
