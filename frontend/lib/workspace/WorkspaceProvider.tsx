"use client";
// Case workspace state (plan §13.5): case data loading, the active stage and tab, the selected source for
// highlight-and-scroll, the event stream, gate status and checklists, and counsel's edits (USER_EDITED).
// Every workspace component reads it through the hooks at the bottom of this file.
import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode,
} from "react";
import * as api from "../api";
import { ApiError, errorMessage } from "../errors";
import { toSelectedSource } from "../format";
import { getDemoResolutions } from "../mock/server";
import {
  isStageUnlocked, isTabUnlocked, stageForTab, tabForStage, type StageContext, type WorkspaceTab,
} from "../stages";
import type {
  AgentEvent, BailBrief, BudgetState, CaseDossier, CaseSummary, ChatMessage, DossierFieldName, DossierFields,
  ExportFormat, GateId, GateStatus, GroundRevision, HearingPrepCard, IngestionReport, RightsReport, SelectedSource,
  SourceRef, SparringRecord, Stage, TimelineEvent, UploadResponse,
} from "../types";
import { DOSSIER_FIELD_NAMES } from "../types";
import { useEventStream, type StreamStatus } from "../useEventStream";
import { deriveActivity, hasRecentEvents, type ActivityState } from "./activity";
import {
  acknowledgedForApproval, computeChecklist, type GateChecklist, type ResolutionState,
} from "./checklist";
import {
  applyDateEdits, EMPTY_LOCAL_STATE, loadLocalState, saveLocalState, type DateEdit, type LocalWorkspaceState,
} from "./local";

/* ── Types ──────────────────────────────────────────────────────────────────────────────────────────────────────── */

export interface CaseData {
  summary: CaseSummary | null;
  ingestion: IngestionReport | null;
  dossier: CaseDossier | null;
  /** List of Dates with counsel's row edits applied. */
  dates: TimelineEvent[] | null;
  rights: RightsReport | null;
  /** Brief with counsel's reworded grounds applied. */
  brief: BailBrief | null;
  revisions: GroundRevision[];
  spar: SparringRecord | null;
  prep: HearingPrepCard | null;
  budget: BudgetState | null;
  chat: ChatMessage[];
}

export type Resource =
  | "summary" | "ingestion" | "dossier" | "dates" | "rights" | "brief" | "revisions" | "spar" | "prep" | "budget"
  | "chat" | "gates";

export const ALL_RESOURCES: readonly Resource[] = [
  "summary", "ingestion", "dossier", "dates", "rights", "brief", "revisions", "spar", "prep", "budget", "chat", "gates",
];

export interface GateState {
  approvals: { gate1: boolean; gate2: boolean };
  /** The backend's view (GET /gates/{gate}); null until loaded. */
  status: Record<GateId, GateStatus | null>;
  /** The checklists computed locally from the data and counsel's resolutions (plan §13.5). */
  checklists: Record<GateId, GateChecklist>;
}

export interface WorkspaceValue {
  caseId: string;
  data: CaseData;
  /** True while the first load of a resource is in flight. */
  loading: Record<Resource, boolean>;
  /** True until the first load of every resource has settled. */
  initialLoading: boolean;
  errors: Partial<Record<Resource, string>>;
  /** Last error from an action (edit, approve, upload, chat...), for a toast or aria-live region. */
  actionError: string | null;
  clearActionError: () => void;
  refresh: (resources?: readonly Resource[]) => Promise<void>;

  /* Stage rail and tabs */
  /** The case's progress stage (CaseSummary.stage). */
  progressStage: Stage;
  activeStage: Stage;
  activeTab: WorkspaceTab;
  stageContext: StageContext;
  /** Go to a stage (and its tab). Returns false when the stage is locked. */
  setStage: (stage: Stage) => boolean;
  /** Open a right-pane tab (and its stage). Returns false when the tab is locked. */
  setTab: (tab: WorkspaceTab) => boolean;
  isStageUnlocked: (stage: Stage) => boolean;
  isTabUnlocked: (tab: WorkspaceTab) => boolean;
  /** Item to scroll to in the active tab (a field name, ground id, objection id...), set by checklist links. */
  focusTarget: { tab: WorkspaceTab; id: string; nonce: number } | null;
  focusItem: (tab: WorkspaceTab, id: string) => void;

  /* Source highlight */
  selectedSource: SelectedSource | null;
  /** Increments on every selection so re-selecting the same source scrolls again. */
  sourceNonce: number;
  selectSource: (source: SourceRef | SelectedSource | null, origin?: string) => void;
  clearSource: () => void;
  /** Document shown in the case-file viewer. */
  activeDocId: string | null;
  setActiveDocId: (docId: string | null) => void;

  /* Events and agents */
  events: AgentEvent[];
  streamStatus: StreamStatus;
  activity: ActivityState;
  mode: api.ApiMode;

  /* Gates */
  gates: GateState;
  approveGate: (gate: GateId) => Promise<GateStatus>;

  /* Counsel's edits and resolutions */
  resolutions: ResolutionState;
  acknowledge: (key: string) => void;
  unacknowledge: (key: string) => void;
  resolveItem: (key: string, note?: string | null) => void;
  unresolveItem: (key: string) => void;
  editField: <K extends DossierFieldName>(field: K, value: DossierFields[K]["value"]) => Promise<void>;
  /** Fields whose value or status changed since they were first loaded (flow 4 highlights). */
  changedFields: DossierFieldName[];
  clearChangedFields: () => void;
  editDate: (eventId: string, patch: Omit<DateEdit, "at">) => void;
  resetDate: (eventId: string) => void;
  editGround: (groundId: string, argument: string, note?: string | null) => void;
  resetGround: (groundId: string) => void;
  editedGrounds: string[];

  /* Agent runs */
  startDraft: () => Promise<void>;
  drafting: boolean;
  sendChat: (text: string) => Promise<ChatMessage | null>;
  chatPending: boolean;
  upload: (files: File[]) => Promise<UploadResponse | null>;
  uploadAudio: (blob: Blob, fileName?: string) => Promise<UploadResponse | null>;
  uploading: boolean;
  /** Questions Munshi asked after the last upload. */
  uploadQuestions: string[];
  /** Export is impossible before Gate 2 (plan §16): this rejects with a 403 ApiError without calling the API. */
  exportCase: (format?: ExportFormat) => Promise<string[]>;
  exports: string[];
  canExport: boolean;
}

const WorkspaceContext = createContext<WorkspaceValue | null>(null);

/* ── Helpers ────────────────────────────────────────────────────────────────────────────────────────────────────── */

const EMPTY_DATA: CaseData = {
  summary: null, ingestion: null, dossier: null, dates: null, rights: null, brief: null, revisions: [], spar: null,
  prep: null, budget: null, chat: [],
};

function allFlags(value: boolean): Record<Resource, boolean> {
  return Object.fromEntries(ALL_RESOURCES.map((r) => [r, value])) as Record<Resource, boolean>;
}

/** 404 means "not produced yet", not an error. */
async function optional<T>(p: Promise<T>): Promise<T | null> {
  try {
    return await p;
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

function applyGroundEdits(brief: BailBrief | null, edits: LocalWorkspaceState["groundEdits"]): BailBrief | null {
  if (!brief || Object.keys(edits).length === 0) return brief;
  return { ...brief, grounds: brief.grounds.map((g) => (edits[g.id] ? { ...g, argument: edits[g.id].argument } : g)) };
}

/** Which resources an event makes stale (plan §3.3: the views are computed from the log). */
function resourcesForEvent(e: AgentEvent): Resource[] {
  const out = new Set<Resource>();
  const view = typeof e.inputs?.view === "string" ? e.inputs.view : null;
  const store = typeof e.inputs?.store === "string" ? e.inputs.store : null;
  switch (e.kind) {
    case "STORE_WRITE":
      out.add("summary");
      if (view === "ingestion_report") out.add("ingestion");
      if (view === "rights_report") out.add("rights");
      if (view === "brief") ["brief", "revisions", "budget"].forEach((r) => out.add(r as Resource));
      if (view === "sparring") out.add("spar");
      if (view === "hearing_card") out.add("prep");
      if (store === "case.facts") out.add("dossier");
      if (store === "case.timeline") out.add("dates");
      if (e.tool === "extract_dossier") out.add("dossier");
      break;
    case "GATE_OPENED":
    case "GATE_APPROVED":
    case "GATE_REJECTED":
      out.add("gates");
      out.add("summary");
      break;
    case "BUDGET_HIT":
      out.add("budget");
      break;
    case "CHANGE_SET_APPROVED":
    case "CLAIM_STALED":
      out.add("brief");
      out.add("revisions");
      break;
    case "USER_ACTION":
      if (e.inputs?.action === "edit_field" || e.inputs?.action === "state_field") out.add("dossier");
      break;
    case "AGENT_MESSAGE":
      if (e.outputs?.status === "done") {
        out.add("summary");
        out.add("chat");
      }
      break;
  }
  return [...out];
}

/* ── Provider ───────────────────────────────────────────────────────────────────────────────────────────────────── */

export interface WorkspaceProviderProps {
  caseId: string;
  children: ReactNode;
  /** Stage to open first; defaults to the case's progress stage. */
  initialStage?: Stage;
  /** Tab to open first; defaults to the stage's tab. */
  initialTab?: WorkspaceTab;
}

export function WorkspaceProvider({ caseId, children, initialStage, initialTab }: WorkspaceProviderProps) {
  const [raw, setRaw] = useState<CaseData>(EMPTY_DATA);
  const [loading, setLoading] = useState<Record<Resource, boolean>>(() => allFlags(true));
  const [errors, setErrors] = useState<Partial<Record<Resource, string>>>({});
  const [actionError, setActionError] = useState<string | null>(null);
  const [gateStatus, setGateStatus] = useState<Record<GateId, GateStatus | null>>({ GATE_1_DOSSIER: null, GATE_2_EXPORT: null });
  const [local, setLocal] = useState<LocalWorkspaceState>(EMPTY_LOCAL_STATE);
  const [localReady, setLocalReady] = useState(false);
  const [activeStage, setActiveStage] = useState<Stage>(initialStage ?? "INTAKE");
  const [activeTab, setActiveTab] = useState<WorkspaceTab>(initialTab ?? (initialStage ? tabForStage(initialStage) : "dossier"));
  const [focusTarget, setFocusTarget] = useState<WorkspaceValue["focusTarget"]>(null);
  const [selectedSource, setSelectedSource] = useState<SelectedSource | null>(null);
  const [sourceNonce, setSourceNonce] = useState(0);
  const [activeDocId, setActiveDocId] = useState<string | null>(null);
  const [changedFields, setChangedFields] = useState<DossierFieldName[]>([]);
  const [drafting, setDrafting] = useState(false);
  const [chatPending, setChatPending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadQuestions, setUploadQuestions] = useState<string[]>([]);
  const [exportsList, setExportsList] = useState<string[]>([]);
  const [now, setNow] = useState(() => Date.now());

  const placedStage = useRef(Boolean(initialStage));
  const baseline = useRef<Partial<Record<DossierFieldName, string>> | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  /* Local state: saved per case, or the demo's seeded resolutions. */
  useEffect(() => {
    const saved = loadLocalState(caseId);
    setLocal(saved ?? { ...EMPTY_LOCAL_STATE, resolutions: api.isDemoMode() ? getDemoResolutions(caseId) : EMPTY_LOCAL_STATE.resolutions });
    setLocalReady(true);
    baseline.current = null;
    setChangedFields([]);
    placedStage.current = Boolean(initialStage);
    // initialStage only matters on the first placement for this case
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  useEffect(() => {
    if (localReady) saveLocalState(caseId, local);
  }, [caseId, local, localReady]);

  /* Loading */
  const trackDossier = useCallback((d: CaseDossier | null) => {
    if (!d) return;
    const snapshot: Partial<Record<DossierFieldName, string>> = {};
    for (const name of DOSSIER_FIELD_NAMES) {
      const f = d.fields[name];
      snapshot[name] = JSON.stringify([f?.value ?? null, f?.status ?? null]);
    }
    if (!baseline.current) {
      baseline.current = snapshot;
      return;
    }
    const changed = DOSSIER_FIELD_NAMES.filter((n) => baseline.current?.[n] !== snapshot[n]);
    if (changed.length) setChangedFields((prev) => Array.from(new Set([...prev, ...changed])));
    baseline.current = snapshot;
  }, []);

  const loaders = useMemo(
    () => ({
      summary: () => optional(api.getCase(caseId)),
      ingestion: () => optional(api.getIngestion(caseId)),
      dossier: () => optional(api.getDossier(caseId)),
      dates: () => optional(api.getDates(caseId)),
      rights: () => optional(api.getRights(caseId)),
      brief: () => optional(api.getBrief(caseId)),
      revisions: () => optional(api.getBriefRevisions(caseId)).then((r) => r ?? []),
      spar: () => optional(api.getSpar(caseId)),
      prep: () => optional(api.getPrep(caseId)),
      budget: () => optional(api.getBudget(caseId)),
      chat: () => optional(api.getChatHistory(caseId)).then((r) => r ?? []),
      gates: async () => {
        const [g1, g2] = await Promise.all([optional(api.getGate(caseId, "GATE_1_DOSSIER")), optional(api.getGate(caseId, "GATE_2_EXPORT"))]);
        return { GATE_1_DOSSIER: g1, GATE_2_EXPORT: g2 };
      },
    }),
    [caseId],
  );

  const refresh = useCallback(
    async (resources: readonly Resource[] = ALL_RESOURCES) => {
      await Promise.all(
        resources.map(async (r) => {
          try {
            const value = await loaders[r]();
            if (!mounted.current) return;
            if (r === "gates") setGateStatus(value as Record<GateId, GateStatus | null>);
            else {
              if (r === "dossier") trackDossier(value as CaseDossier | null);
              setRaw((prev) => ({ ...prev, [r]: value }));
            }
            setErrors((prev) => {
              if (!(r in prev)) return prev;
              const next = { ...prev };
              delete next[r];
              return next;
            });
          } catch (e) {
            if (mounted.current) setErrors((prev) => ({ ...prev, [r]: errorMessage(e) }));
          } finally {
            if (mounted.current) setLoading((prev) => (prev[r] ? { ...prev, [r]: false } : prev));
          }
        }),
      );
    },
    [loaders, trackDossier],
  );

  useEffect(() => {
    setRaw(EMPTY_DATA);
    setLoading(allFlags(true));
    setErrors({});
    setGateStatus({ GATE_1_DOSSIER: null, GATE_2_EXPORT: null });
    void refresh();
  }, [refresh]);

  /* Events: coalesce refetches for the views an event touches. */
  const pending = useRef<Set<Resource>>(new Set());
  const flushTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onEvent = useCallback(
    (e: AgentEvent) => {
      for (const r of resourcesForEvent(e)) pending.current.add(r);
      if (pending.current.size === 0 || flushTimer.current) return;
      flushTimer.current = setTimeout(() => {
        flushTimer.current = null;
        const batch = [...pending.current];
        pending.current.clear();
        void refresh(batch);
      }, 180);
    },
    [refresh],
  );
  useEffect(
    () => () => {
      if (flushTimer.current) clearTimeout(flushTimer.current);
    },
    [],
  );

  const stream = useEventStream(caseId, { onEvent });

  // Keep the activity clock ticking while events are recent, so "working" turns into "done" without new events.
  useEffect(() => {
    setNow(Date.now());
    if (!hasRecentEvents(stream.events)) return;
    const t = setInterval(() => {
      setNow(Date.now());
      if (!hasRecentEvents(stream.events)) clearInterval(t);
    }, 2000);
    return () => clearInterval(t);
  }, [stream.events]);

  const activity = useMemo(() => deriveActivity(stream.events, now), [stream.events, now]);

  /* Derived data */
  const data: CaseData = useMemo(
    () => ({ ...raw, dates: applyDateEdits(raw.dates, local.dateEdits), brief: applyGroundEdits(raw.brief, local.groundEdits) }),
    [raw, local.dateEdits, local.groundEdits],
  );

  const approvals = useMemo(
    () => ({
      gate1: gateStatus.GATE_1_DOSSIER ? !gateStatus.GATE_1_DOSSIER.open : false,
      gate2: gateStatus.GATE_2_EXPORT ? !gateStatus.GATE_2_EXPORT.open : false,
    }),
    [gateStatus],
  );

  const checklists = useMemo(() => {
    const input = { dossier: data.dossier, brief: data.brief, spar: data.spar };
    return {
      GATE_1_DOSSIER: computeChecklist("GATE_1_DOSSIER", input, local.resolutions, approvals),
      GATE_2_EXPORT: computeChecklist("GATE_2_EXPORT", input, local.resolutions, approvals),
    };
  }, [data.dossier, data.brief, data.spar, local.resolutions, approvals]);

  const stageContext: StageContext = useMemo(
    () => ({
      gate1Approved: approvals.gate1,
      gate2Approved: approvals.gate2,
      hasIngestion: Boolean(data.ingestion),
      hasDossier: Boolean(data.dossier),
      hasRights: Boolean(data.rights),
      hasBrief: Boolean(data.brief),
      hasSpar: Boolean(data.spar),
    }),
    [approvals, data.ingestion, data.dossier, data.rights, data.brief, data.spar],
  );

  const progressStage: Stage = data.summary?.stage ?? "INTAKE";

  // First placement: open the case at its progress stage once the summary and gates are known.
  useEffect(() => {
    if (placedStage.current || loading.summary || loading.gates || !data.summary) return;
    placedStage.current = true;
    let stage = data.summary.stage;
    if (!isStageUnlocked(stage, stageContext)) stage = "DOSSIER";
    setActiveStage(stage);
    setActiveTab(tabForStage(stage));
  }, [data.summary, loading.summary, loading.gates, stageContext]);

  // If the active stage becomes locked (a changed dossier reopened Gate 1), fall back to the dossier.
  useEffect(() => {
    if (!placedStage.current || loading.gates) return;
    if (!isStageUnlocked(activeStage, stageContext)) {
      setActiveStage("DOSSIER");
      setActiveTab("dossier");
    }
  }, [activeStage, stageContext, loading.gates]);

  /* Navigation */
  const setStage = useCallback(
    (stage: Stage) => {
      if (!isStageUnlocked(stage, stageContext)) return false;
      setActiveStage(stage);
      setActiveTab(tabForStage(stage));
      return true;
    },
    [stageContext],
  );

  const setTab = useCallback(
    (tab: WorkspaceTab) => {
      if (!isTabUnlocked(tab, stageContext)) return false;
      setActiveTab(tab);
      setActiveStage((s) => (tabForStage(s) === tab ? s : stageForTab(tab)));
      return true;
    },
    [stageContext],
  );

  const focusItem = useCallback(
    (tab: WorkspaceTab, id: string) => {
      setTab(tab);
      setFocusTarget((prev) => ({ tab, id, nonce: (prev?.nonce ?? 0) + 1 }));
    },
    [setTab],
  );

  const selectSource = useCallback((source: SourceRef | SelectedSource | null, origin?: string) => {
    if (!source) {
      setSelectedSource(null);
      return;
    }
    const sel: SelectedSource | null =
      "doc_id" in source && typeof source.doc_id === "string"
        ? { ...(source as SelectedSource), origin: origin ?? (source as SelectedSource).origin ?? null }
        : toSelectedSource(source as SourceRef, origin);
    if (!sel) return;
    setSelectedSource(sel);
    setActiveDocId(sel.doc_id);
    setSourceNonce((n) => n + 1);
  }, []);

  const clearSource = useCallback(() => setSelectedSource(null), []);

  /* Resolutions and edits */
  const updateResolutions = useCallback((fn: (r: ResolutionState) => ResolutionState) => {
    setLocal((prev) => ({ ...prev, resolutions: fn(prev.resolutions) }));
  }, []);

  const acknowledge = useCallback(
    (key: string) => updateResolutions((r) => (r.acknowledged.includes(key) ? r : { ...r, acknowledged: [...r.acknowledged, key] })),
    [updateResolutions],
  );
  const unacknowledge = useCallback(
    (key: string) => updateResolutions((r) => ({ ...r, acknowledged: r.acknowledged.filter((k) => k !== key) })),
    [updateResolutions],
  );
  const resolveItem = useCallback(
    (key: string, note?: string | null) =>
      updateResolutions((r) => ({ ...r, resolved: { ...r.resolved, [key]: { note: note ?? null, at: new Date().toISOString() } } })),
    [updateResolutions],
  );
  const unresolveItem = useCallback(
    (key: string) =>
      updateResolutions((r) => {
        const resolved = { ...r.resolved };
        delete resolved[key];
        return { ...r, resolved };
      }),
    [updateResolutions],
  );

  const editField = useCallback(
    async <K extends DossierFieldName>(field: K, value: DossierFields[K]["value"]) => {
      const before = raw.dossier;
      if (before) {
        // Optimistic: counsel's value, status USER_EDITED, no court source behind it (plan §7.1).
        setRaw((prev) =>
          prev.dossier
            ? { ...prev, dossier: { ...prev.dossier, fields: { ...prev.dossier.fields, [field]: { value, source: null, status: "USER_EDITED" } } } }
            : prev,
        );
      }
      try {
        const updated = await api.editField(caseId, field, value);
        trackDossier(updated);
        setRaw((prev) => ({ ...prev, dossier: updated }));
        void refresh(["gates", "summary"]);
      } catch (e) {
        setRaw((prev) => ({ ...prev, dossier: before }));
        setActionError(errorMessage(e));
        throw e;
      }
    },
    [caseId, raw.dossier, refresh, trackDossier],
  );

  const editDate = useCallback((eventId: string, patch: Omit<DateEdit, "at">) => {
    setLocal((prev) => ({ ...prev, dateEdits: { ...prev.dateEdits, [eventId]: { ...prev.dateEdits[eventId], ...patch, at: new Date().toISOString() } } }));
  }, []);
  const resetDate = useCallback((eventId: string) => {
    setLocal((prev) => {
      const dateEdits = { ...prev.dateEdits };
      delete dateEdits[eventId];
      return { ...prev, dateEdits };
    });
  }, []);

  const editGround = useCallback(
    (groundId: string, argument: string, note?: string | null) => {
      setLocal((prev) => ({
        ...prev,
        groundEdits: { ...prev.groundEdits, [groundId]: { argument, note: note ?? null, at: new Date().toISOString() } },
      }));
      resolveItem(`NEEDS_REVIEW:${groundId}`, note ?? "Reworded by counsel");
    },
    [resolveItem],
  );
  const resetGround = useCallback(
    (groundId: string) => {
      setLocal((prev) => {
        const groundEdits = { ...prev.groundEdits };
        delete groundEdits[groundId];
        return { ...prev, groundEdits };
      });
      unresolveItem(`NEEDS_REVIEW:${groundId}`);
    },
    [unresolveItem],
  );

  /* Gates */
  const approveGate = useCallback(
    async (gate: GateId) => {
      const checklist = checklists[gate];
      if (!checklist.canApprove) {
        const err = new ApiError(409, checklist.summary);
        setActionError(err.message);
        throw err;
      }
      try {
        const status = await api.approveGate(caseId, gate, acknowledgedForApproval(checklist));
        setGateStatus((prev) => ({ ...prev, [gate]: status }));
        if (gate === "GATE_1_DOSSIER") setChangedFields([]);
        void refresh(["summary", "gates", "dossier"]);
        return status;
      } catch (e) {
        setActionError(errorMessage(e));
        throw e;
      }
    },
    [caseId, checklists, refresh],
  );

  /* Agent runs */
  const startDraft = useCallback(async () => {
    if (!approvals.gate1) {
      setActionError("Approve the dossier (Gate 1) before drafting.");
      return;
    }
    setDrafting(true);
    try {
      await api.startDraft(caseId);
      setActiveStage("BRIEF");
      setActiveTab("brief");
    } catch (e) {
      setActionError(errorMessage(e));
    } finally {
      setDrafting(false);
    }
  }, [approvals.gate1, caseId]);

  const sendChat = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return null;
      const temp: ChatMessage = { message_id: `pending-${Date.now()}`, case_id: caseId, role: "counsel", agent: null, text: trimmed, chips: [], refused: false };
      setRaw((prev) => ({ ...prev, chat: [...prev.chat, temp] }));
      setChatPending(true);
      try {
        const reply = await api.postChat(caseId, trimmed);
        const history = await optional(api.getChatHistory(caseId));
        setRaw((prev) => ({
          ...prev,
          chat: history ?? [...prev.chat.filter((m) => m.message_id !== temp.message_id), { ...temp, message_id: `${temp.message_id}-sent` }, reply],
        }));
        return reply;
      } catch (e) {
        setActionError(errorMessage(e));
        return null;
      } finally {
        setChatPending(false);
      }
    },
    [caseId],
  );

  const upload = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return null;
      setUploading(true);
      try {
        const res = await api.uploadFiles(caseId, files);
        setUploadQuestions(res.questions);
        void refresh(["summary"]);
        return res;
      } catch (e) {
        setActionError(errorMessage(e));
        return null;
      } finally {
        setUploading(false);
      }
    },
    [caseId, refresh],
  );

  const uploadAudio = useCallback(
    async (blob: Blob, fileName?: string) => {
      setUploading(true);
      try {
        const res = await api.uploadAudio(caseId, blob, fileName);
        setUploadQuestions(res.questions);
        return res;
      } catch (e) {
        setActionError(errorMessage(e));
        return null;
      } finally {
        setUploading(false);
      }
    },
    [caseId],
  );

  const canExport = approvals.gate1 && approvals.gate2;

  const exportCase = useCallback(
    async (format: ExportFormat = "DOCX") => {
      if (!canExport) {
        // Enforced in the UI as well as on the server (plan §16).
        const err = new ApiError(403, "Export is blocked until counsel approves Gate 2.");
        setActionError(err.message);
        throw err;
      }
      try {
        const files = await api.exportCase(caseId, format);
        setExportsList((prev) => Array.from(new Set([...prev, ...files])));
        return files;
      } catch (e) {
        setActionError(errorMessage(e));
        throw e;
      }
    },
    [canExport, caseId],
  );

  const initialLoading = ALL_RESOURCES.some((r) => loading[r]);

  const value: WorkspaceValue = {
    caseId,
    data,
    loading,
    initialLoading,
    errors,
    actionError,
    clearActionError: () => setActionError(null),
    refresh,
    progressStage,
    activeStage,
    activeTab,
    stageContext,
    setStage,
    setTab,
    isStageUnlocked: (s) => isStageUnlocked(s, stageContext),
    isTabUnlocked: (t) => isTabUnlocked(t, stageContext),
    focusTarget,
    focusItem,
    selectedSource,
    sourceNonce,
    selectSource,
    clearSource,
    activeDocId,
    setActiveDocId,
    events: stream.events,
    streamStatus: stream.status,
    activity,
    mode: stream.mode,
    gates: { approvals, status: gateStatus, checklists },
    approveGate,
    resolutions: local.resolutions,
    acknowledge,
    unacknowledge,
    resolveItem,
    unresolveItem,
    editField,
    changedFields,
    clearChangedFields: () => setChangedFields([]),
    editDate,
    resetDate,
    editGround,
    resetGround,
    editedGrounds: Object.keys(local.groundEdits),
    startDraft,
    drafting,
    sendChat,
    chatPending,
    upload,
    uploadAudio,
    uploading,
    uploadQuestions,
    exportCase,
    exports: exportsList,
    canExport,
  };

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

/* ── Hooks and selectors ────────────────────────────────────────────────────────────────────────────────────────── */

/** The whole workspace. Throws outside <WorkspaceProvider>. */
export function useWorkspace(): WorkspaceValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used inside <WorkspaceProvider>.");
  return ctx;
}

/** The workspace, or null outside a provider (for components that also render elsewhere, e.g. SourceChip). */
export function useOptionalWorkspace(): WorkspaceValue | null {
  return useContext(WorkspaceContext);
}

/** Case data, loading flags and errors. */
export function useCaseData() {
  const w = useWorkspace();
  return { caseId: w.caseId, ...w.data, loading: w.loading, initialLoading: w.initialLoading, errors: w.errors, refresh: w.refresh };
}

/** Stage rail and tabs. */
export function useStageNav() {
  const w = useWorkspace();
  return {
    progressStage: w.progressStage,
    activeStage: w.activeStage,
    activeTab: w.activeTab,
    stageContext: w.stageContext,
    setStage: w.setStage,
    setTab: w.setTab,
    isStageUnlocked: w.isStageUnlocked,
    isTabUnlocked: w.isTabUnlocked,
    focusTarget: w.focusTarget,
    focusItem: w.focusItem,
  };
}

/** The selected source for highlight-and-scroll. */
export function useSelectedSource() {
  const w = useWorkspace();
  return {
    selectedSource: w.selectedSource,
    sourceNonce: w.sourceNonce,
    selectSource: w.selectSource,
    clearSource: w.clearSource,
    activeDocId: w.activeDocId,
    setActiveDocId: w.setActiveDocId,
  };
}

/** Gate approvals, the backend's gate status and the local checklists, plus counsel's resolutions. */
export function useGates() {
  const w = useWorkspace();
  return {
    ...w.gates,
    approveGate: w.approveGate,
    resolutions: w.resolutions,
    acknowledge: w.acknowledge,
    unacknowledge: w.unacknowledge,
    resolveItem: w.resolveItem,
    unresolveItem: w.unresolveItem,
    canExport: w.canExport,
  };
}

/** One gate's checklist. */
export function useGateChecklist(gate: GateId): GateChecklist {
  return useWorkspace().gates.checklists[gate];
}

/** Chat history and sending. */
export function useChat() {
  const w = useWorkspace();
  return { messages: w.data.chat, send: w.sendChat, pending: w.chatPending, error: w.actionError };
}

/** Agent activity derived from the event stream. */
export function useAgentActivity(): ActivityState {
  return useWorkspace().activity;
}

/** The raw event log and stream status (live trace). */
export function useWorkspaceEvents() {
  const w = useWorkspace();
  return { events: w.events, status: w.streamStatus, mode: w.mode };
}

/** Counsel's edits to the dossier, the List of Dates and the grounds. */
export function useEdits() {
  const w = useWorkspace();
  return {
    editField: w.editField,
    changedFields: w.changedFields,
    clearChangedFields: w.clearChangedFields,
    editDate: w.editDate,
    resetDate: w.resetDate,
    editGround: w.editGround,
    resetGround: w.resetGround,
    editedGrounds: w.editedGrounds,
  };
}
