// Typed client for the FastAPI backend (plan §13.1), one function per route in src/vakeel_sahayak/api/routers/.
//
// The client talks to NEXT_PUBLIC_API_BASE (or NEXT_PUBLIC_API_BASE_URL; default http://localhost:8000). NEXT_PUBLIC_API_MODE says what
// happens when the server cannot answer:
// - "live" (the default in production builds): the server only. A network failure or a 5xx surfaces as an ApiError that the page shows;
//   the client never answers with the sample cases in its place, so counsel never sees someone else's case as their own.
// - "demo": the built-in sample cases (lib/mock/server.ts) only, with no network. Also the mode when NEXT_PUBLIC_API_BASE is empty or "demo".
// - "auto" (the default in development and tests): the server, switching to the sample cases for the rest of the session on a network
//   error or a 5xx. Demo mode is sticky so that the event stream, the gates and the data stay consistent.
// NEXT_PUBLIC_DEMO_FALLBACK=strict, the older switch, means "live".
import { ApiError } from "./errors";
export { ApiError };
import * as demo from "./mock/server";
import type {
  ApproveRequest, BailBrief, BridgeData, BudgetState, CaseDossier, CaseSummary, ChatMessage, CitationGraphData,
  DeskBoard, DraftStartResponse, ExportFormat, GateId, GateStatus, GroundRevision, HearingPrepCard, IngestionReport,
  LibrarySearchHit, MockPage, RightsReport, ServerStatus, SparringRecord, TimelineEvent, UploadResponse,
} from "./types";

/* ── Mode ───────────────────────────────────────────────────────────────────────────────────────────────────────── */

const DEFAULT_API_BASE = "http://localhost:8000";

/**
 * Backend origin without a trailing slash. Defaults to http://localhost:8000 (the FastAPI dev server); set the variable to
 * an empty string (or "demo") to force the in-browser demo backend without probing the network (null).
 */
export const API_BASE: string | null = (() => {
  const raw = process.env.NEXT_PUBLIC_API_BASE ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE;
  const trimmed = raw.trim().replace(/\/+$/, "");
  return trimmed && trimmed !== "demo" ? trimmed : null;
})();

/** How the client chooses between the server and the sample cases (see the header comment). */
export type ApiSetting = "live" | "demo" | "auto";

export const API_SETTING: ApiSetting = (() => {
  const raw = (process.env.NEXT_PUBLIC_API_MODE ?? "").trim().toLowerCase();
  if (raw === "live" || raw === "demo" || raw === "auto") return raw;
  if (process.env.NEXT_PUBLIC_DEMO_FALLBACK === "strict") return "live";
  return process.env.NODE_ENV === "production" ? "live" : "auto";
})();

/** True when a failed request may switch the session to the sample cases ("auto" only). */
const MAY_FALL_BACK = API_SETTING === "auto";

export type ApiMode = "live" | "demo";

let mode: ApiMode = API_BASE && API_SETTING !== "demo" ? "live" : "demo";
let demoReason: string | null =
  API_SETTING === "demo" ? "NEXT_PUBLIC_API_MODE is demo" : API_BASE ? null : "NEXT_PUBLIC_API_BASE is empty";
const modeListeners = new Set<(m: ApiMode) => void>();

/** Whether the server answered the last request: "unknown" before the first one, "down" after a network failure or a 5xx. */
export type Connection = "unknown" | "ok" | "down";

let connection: Connection = "unknown";
const connectionListeners = new Set<(c: Connection) => void>();

function setConnection(next: Connection): void {
  if (next === connection) return;
  connection = next;
  connectionListeners.forEach((l) => l(connection));
}

export function getConnection(): Connection {
  return connection;
}

export function onConnectionChange(listener: (c: Connection) => void): () => void {
  connectionListeners.add(listener);
  return () => connectionListeners.delete(listener);
}

/** The message shown when the server cannot be reached in live mode. */
export function unreachableMessage(): string {
  return `Cannot reach the server at ${API_BASE ?? "(no address set)"}. Check that it is running, then try again.`;
}

/** "live" while the real backend answers; "demo" once the client has fallen back to the demo backend. */
export function getApiMode(): ApiMode {
  return mode;
}

export function isDemoMode(): boolean {
  return mode === "demo";
}

/** Why the client is in demo mode (for the "Demo mode" badge tooltip). */
export function getDemoReason(): string | null {
  return demoReason;
}

/** Switch to demo mode for the rest of the session; only in "auto" (a live session never turns into sample data). */
export function enterDemoMode(reason: string): void {
  if (mode === "demo" || !MAY_FALL_BACK) return;
  mode = "demo";
  demoReason = reason;
  if (typeof console !== "undefined") console.info(`[vakeel-sahayak] demo mode: ${reason}`);
  modeListeners.forEach((l) => l(mode));
}

export function onApiModeChange(listener: (m: ApiMode) => void): () => void {
  modeListeners.add(listener);
  return () => modeListeners.delete(listener);
}

/** Absolute URL of a backend path ("/api/cases"), or null in demo mode. */
export function apiUrl(path: string): string | null {
  return API_BASE && mode === "live" ? `${API_BASE}${path}` : null;
}

/** SSE endpoint for a case's agent events (GET /api/cases/{case_id}/events); null in demo mode. */
export function eventsUrl(caseId: string, lastEventId?: string | null): string | null {
  const base = apiUrl(`/api/cases/${encodeURIComponent(caseId)}/events`);
  if (!base) return null;
  return lastEventId ? `${base}?last_event_id=${encodeURIComponent(lastEventId)}` : base;
}

/* ── Transport ──────────────────────────────────────────────────────────────────────────────────────────────────── */

class FallBack extends Error {}

type Body = { json: unknown } | { form: FormData } | undefined;

async function http<T>(method: string, path: string, body?: Body, signal?: AbortSignal): Promise<T> {
  const url = apiUrl(path);
  if (!url) throw new FallBack("demo");
  let res: Response;
  try {
    res = await fetch(url, {
      method,
      signal,
      headers: body && "json" in body ? { "Content-Type": "application/json", Accept: "application/json" } : { Accept: "application/json" },
      body: body ? ("json" in body ? JSON.stringify(body.json) : body.form) : undefined,
    });
  } catch (e) {
    if (signal?.aborted) throw e;
    setConnection("down");
    if (!MAY_FALL_BACK) throw new ApiError(0, unreachableMessage());
    enterDemoMode(`the API at ${API_BASE} is unreachable`);
    throw new FallBack("network");
  }
  setConnection(res.status >= 500 ? "down" : "ok");
  if (!res.ok) {
    if (res.status >= 500 && MAY_FALL_BACK) {
      enterDemoMode(`the API answered ${res.status} for ${method} ${path}`);
      throw new FallBack("server");
    }
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      /* not JSON */
    }
    const said =
      detail && typeof detail === "object" && "detail" in detail && typeof (detail as { detail: unknown }).detail === "string"
        ? (detail as { detail: string }).detail
        : null;
    const message =
      res.status >= 500
        ? `The server could not complete this request (error ${res.status})${said ? `: ${said}` : ""}. Try again; if it keeps failing, check the server log.`
        : said ?? `${method} ${path} failed with ${res.status}`;
    throw new ApiError(res.status, message, detail);
  }
  if (res.status === 204) return undefined as T;
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? await res.json() : await res.text()) as T;
}

/** Call the backend; in demo mode, or after a network failure, answer from the demo backend instead. */
async function call<T>(live: () => Promise<T>, offline: () => Promise<T>): Promise<T> {
  if (mode === "demo") return offline();
  try {
    return await live();
  } catch (e) {
    if (e instanceof FallBack) return offline();
    throw e;
  }
}

const enc = encodeURIComponent;
const c = (caseId: string) => `/api/cases/${enc(caseId)}`;

/* ── Server status (asgi.py /healthz) ───────────────────────────────────────────────────────────────────────────── */

/** GET /healthz: the server's model and privacy settings; null in demo mode or when the server does not answer (never sample data). */
export async function getServerStatus(): Promise<ServerStatus | null> {
  if (!apiUrl("/healthz")) return null;
  try {
    return await http<ServerStatus>("GET", "/healthz");
  } catch (e) {
    if (e instanceof FallBack || (e instanceof ApiError && e.status === 0)) return null;
    throw e;
  }
}

/* ── /api/cases (routers/cases.py) ──────────────────────────────────────────────────────────────────────────────── */

/** GET /api/cases: the cause list. */
export function listCases(): Promise<CaseSummary[]> {
  return call(() => http("GET", "/api/cases"), () => demo.listCases());
}

/** POST /api/cases: create a case. */
export function createCase(title?: string | null): Promise<CaseSummary> {
  const body = { title: title ?? null };
  return call(() => http("POST", "/api/cases", { json: body }), () => demo.createCase(body));
}

/** GET /api/cases/{case_id}. */
export function getCase(caseId: string): Promise<CaseSummary> {
  return call(() => http("GET", c(caseId)), () => demo.getCase(caseId));
}

/** GET /api/cases/{case_id}/ingestion: the latest IngestionReport. */
export function getIngestion(caseId: string): Promise<IngestionReport> {
  return call(() => http("GET", `${c(caseId)}/ingestion`), () => demo.getIngestion(caseId));
}

/** GET /api/cases/{case_id}/dossier. */
export function getDossier(caseId: string): Promise<CaseDossier> {
  return call(() => http("GET", `${c(caseId)}/dossier`), () => demo.getDossier(caseId));
}

/** PATCH /api/cases/{case_id}/dossier/{field}: counsel edits a field; its status becomes USER_EDITED. */
export function editField(caseId: string, field: string, value: unknown): Promise<CaseDossier> {
  const body = { value };
  return call(() => http("PATCH", `${c(caseId)}/dossier/${enc(field)}`, { json: body }), () => demo.editField(caseId, field, body));
}

/** GET /api/cases/{case_id}/dates: the List of Dates and Events. */
export function getDates(caseId: string): Promise<TimelineEvent[]> {
  return call(() => http("GET", `${c(caseId)}/dates`), () => demo.getDates(caseId));
}

/** GET /api/cases/{case_id}/rights: the RightsReport. Optional list fields the backend leaves out become empty lists. */
export function getRights(caseId: string): Promise<RightsReport> {
  return call(
    async () => {
      const report = await http<RightsReport>("GET", `${c(caseId)}/rights`);
      return {
        ...report,
        checks: (report.checks ?? []).map((k) => ({ ...k, uses: k.uses ?? [], sources: k.sources ?? [], dates: k.dates ?? {} })),
      };
    },
    () => demo.getRights(caseId),
  );
}

/** POST /api/cases/{case_id}/draft: Sutradhar plans, Vakeel drafts, Abhiyojak spars (needs Gate 1). */
export function startDraft(caseId: string): Promise<DraftStartResponse> {
  return call(() => http("POST", `${c(caseId)}/draft`), () => demo.startDraft(caseId) as Promise<DraftStartResponse>);
}

/** GET /api/cases/{case_id}/brief: the BailBrief. */
export function getBrief(caseId: string): Promise<BailBrief> {
  return call(() => http("GET", `${c(caseId)}/brief`), () => demo.getBrief(caseId));
}

/**
 * Change highlights for the Brief tab (plan §10). There is no backend route for these yet: the live backend returns
 * [] and the demo returns its revisions (listed as a shared change).
 */
export function getBriefRevisions(caseId: string): Promise<GroundRevision[]> {
  return call(async () => [], () => demo.getBriefRevisions(caseId));
}

/** GET /api/cases/{case_id}/spar: the SparringRecord. */
export function getSpar(caseId: string): Promise<SparringRecord> {
  return call(() => http("GET", `${c(caseId)}/spar`), () => demo.getSpar(caseId));
}

/** GET /api/cases/{case_id}/prep: the hearing-prep card. */
export function getPrep(caseId: string): Promise<HearingPrepCard> {
  return call(() => http("GET", `${c(caseId)}/prep`), () => demo.getPrep(caseId));
}

/** GET /api/cases/{case_id}/budget: spend and budget hits. */
export function getBudget(caseId: string): Promise<BudgetState> {
  return call(() => http("GET", `${c(caseId)}/budget`), () => demo.getBudget(caseId));
}

/** What the PDF viewer shows for one page: the backend's page image, or a demo facsimile with text boxes. */
export type PageSource = { kind: "image"; url: string } | { kind: "mock"; page: MockPage };

/** URL of GET /api/cases/{case_id}/files/{doc_id}/pages/{page} (a page image), or null in demo mode. */
export function pageImageUrl(caseId: string, docId: string, page: number): string | null {
  return apiUrl(`${c(caseId)}/files/${enc(docId)}/pages/${page}`);
}

/** GET /api/cases/{case_id}/files/{doc_id}/pages/{page}. */
export async function getPage(caseId: string, docId: string, page: number): Promise<PageSource> {
  const url = pageImageUrl(caseId, docId, page);
  if (url) return { kind: "image", url };
  return { kind: "mock", page: await demo.getPage(caseId, docId, page) };
}

/* ── Upload (routers/upload.py) ─────────────────────────────────────────────────────────────────────────────────── */

/** POST /api/cases/{case_id}/upload: PDFs, photos, DOCX (multipart field "files"). */
export function uploadFiles(caseId: string, files: File[]): Promise<UploadResponse> {
  return call(
    () => {
      const form = new FormData();
      files.forEach((f) => form.append("files", f, f.name));
      return http("POST", `${c(caseId)}/upload`, { form });
    },
    () => demo.uploadFiles(caseId, files.map((f) => f.name)),
  );
}

/** POST /api/cases/{case_id}/audio: dictation (multipart field "file"); audio is deleted after transcription. */
export function uploadAudio(caseId: string, file: Blob, fileName = "dictation.webm"): Promise<UploadResponse> {
  return call(
    () => {
      const form = new FormData();
      form.append("file", file, fileName);
      return http("POST", `${c(caseId)}/audio`, { form });
    },
    () => demo.uploadAudio(caseId, fileName),
  );
}

/* ── Chat (routers/chat.py) ─────────────────────────────────────────────────────────────────────────────────────── */

/** POST /api/cases/{case_id}/chat: Sutradhar routes the question; a short cited answer (or a refusal). */
export function postChat(caseId: string, text: string): Promise<ChatMessage> {
  const body = { text };
  return call(() => http("POST", `${c(caseId)}/chat`, { json: body }), () => demo.postChat(caseId, body));
}

/** GET /api/cases/{case_id}/chat: chat history. */
export function getChatHistory(caseId: string): Promise<ChatMessage[]> {
  return call(() => http("GET", `${c(caseId)}/chat`), () => demo.getChatHistory(caseId));
}

/* ── Gates (routers/gates.py) ───────────────────────────────────────────────────────────────────────────────────── */

/** GET /api/cases/{case_id}/gates/{gate}: the gate checklist. */
export function getGate(caseId: string, gate: GateId): Promise<GateStatus> {
  return call(() => http("GET", `${c(caseId)}/gates/${gate}`), () => demo.getGate(caseId, gate));
}

/** POST /api/cases/{case_id}/gates/{gate}/approve: 409 while the checklist has unresolved items. */
export function approveGate(caseId: string, gate: GateId, acknowledged: string[] = []): Promise<GateStatus> {
  const body: ApproveRequest = { acknowledged_fields: acknowledged };
  return call(() => http("POST", `${c(caseId)}/gates/${gate}/approve`, { json: body }), () => demo.approveGate(caseId, gate, body));
}

/* ── Export (routers/export.py) ─────────────────────────────────────────────────────────────────────────────────── */

/** POST /api/cases/{case_id}/export: 403 unless Gate 2 is approved for this case (plan §16). Returns file paths. */
export function exportCase(caseId: string, format: ExportFormat = "DOCX"): Promise<string[]> {
  const body = { format };
  return call(() => http("POST", `${c(caseId)}/export`, { json: body }), () => demo.exportCase(caseId, body));
}

/* ── Desk (routers/desk.py) ─────────────────────────────────────────────────────────────────────────────────────── */

/** POST /api/desk/upload: a folder (zip) of case files; returns the new case ids. */
export function deskUpload(file: File): Promise<string[]> {
  return call(
    () => {
      const form = new FormData();
      form.append("file", file, file.name);
      return http("POST", "/api/desk/upload", { form });
    },
    () => demo.deskUpload(file.name),
  );
}

/** GET /api/desk/board: the triage board sorted by urgency. */
export function getDeskBoard(): Promise<DeskBoard> {
  return call(() => http("GET", "/api/desk/board"), () => demo.getDeskBoard());
}

/** POST /api/desk/{case_id}/open: open a case from the board (it still needs its own approvals). */
export function openDeskCase(caseId: string): Promise<CaseSummary> {
  return call(() => http("POST", `/api/desk/${enc(caseId)}/open`), () => demo.openDeskCase(caseId));
}

/* ── Library (routers/library.py) ───────────────────────────────────────────────────────────────────────────────── */

/** GET /api/library/search?q=: precedent search over caselaw.reasoning. */
export function searchLibrary(q: string): Promise<LibrarySearchHit[]> {
  return call(() => http("GET", `/api/library/search?q=${enc(q)}`), () => demo.searchLibrary(q));
}

/** GET /api/library/citations/{doc_id}: citation graph with good-law badges. */
export function getCitationGraph(docId: string): Promise<CitationGraphData> {
  return call(() => http("GET", `/api/library/citations/${enc(docId)}`), () => demo.getCitationGraph(docId));
}

/** GET /api/library/bridge/{code}/{section}: the IPC↔BNS bridge with a text diff. */
export function getBridge(code: string, section: string): Promise<BridgeData> {
  return call(() => http("GET", `/api/library/bridge/${enc(code)}/${enc(section)}`), () => demo.getBridge(code, section));
}

/* ── Grouped client (same functions; older call sites use these names) ──────────────────────────────────────────── */

export const api = {
  listCases,
  createCase,
  getCase,
  getIngestion,
  getDossier,
  editField,
  getDates,
  getRights,
  startDraft,
  getBrief,
  getBriefRevisions,
  getSpar,
  getPrep,
  getBudget,
  getPage,
  pageImageUrl,
  uploadFiles,
  uploadAudio,
  postChat,
  chat: postChat,
  getChatHistory,
  getGate,
  approveGate,
  exportCase,
  deskUpload,
  getDeskBoard,
  deskBoard: getDeskBoard,
  openDeskCase,
  searchLibrary,
  librarySearch: searchLibrary,
  getCitationGraph,
  libraryCitations: getCitationGraph,
  getBridge,
  libraryBridge: getBridge,
  eventsUrl,
  getServerStatus,
} as const;

export default api;
