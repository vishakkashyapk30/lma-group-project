// The six recorded evaluator-demo cases (demo/cases/ in the repository) for the demo build, which has no backend.
// scripts/demo/snapshot_static_demo.py asks a running backend for every response the workspace reads and writes:
//   lib/mock/recorded/index.json                      the tours and the case summaries (bundled; small)
//   public/demo-cases/<case_id>.json                  one case's responses and event log (fetched when the case is opened)
//   public/demo-cases/<case_id>/pages/<doc>-<n>.png   page images for the PDF viewer
//   public/api/cases/<case_id>/export/files/<name>    the real exported files, at the path the client already links to
// The recorded runs are shown as they happened; Gate 2 stays open until the evaluator approves it in the browser.
import type {
  AgentEvent, BailBrief, BudgetState, CaseDossier, CaseSummary, ChatMessage, ExportFormat, IngestionReport,
  RightsReport, SparringRecord, TimelineEvent,
} from "../types";
import INDEX from "./recorded/index.json";

export interface RecordedSnapshot {
  summary: CaseSummary;
  ingestion: IngestionReport;
  dossier: CaseDossier;
  dates: TimelineEvent[];
  rights: RightsReport;
  brief: BailBrief | null;
  spar: SparringRecord | null;
  prep: unknown;
  budget: BudgetState;
  chat: ChatMessage[];
  approvals: { gate1: boolean; gate2: boolean };
  events: AgentEvent[];
  pages: string[];
  exports: Partial<Record<ExportFormat, string[]>>;
}

interface RecordedIndex {
  tours: Array<Record<string, unknown> & { slug: string; case_id: string }>;
  cases: Array<CaseSummary & { approvals?: { gate1: boolean; gate2: boolean } }>;
}

const index = INDEX as unknown as RecordedIndex;

/** The recorded tours (full, with steps), in the order the backend lists them. */
export const RECORDED_TOURS = index.tours;

/** The recorded cases' summaries as the backend gave them (stage, rights chips, items needing attention). */
export const RECORDED_SUMMARIES: CaseSummary[] = index.cases.map(({ approvals: _a, ...s }) => s);

/** Gate approvals of each recorded case as recorded (Gate 1 approved, Gate 2 open). */
export const RECORDED_APPROVALS: Record<string, { gate1: boolean; gate2: boolean }> = Object.fromEntries(
  index.cases.map((c) => [c.case_id, c.approvals ?? { gate1: true, gate2: false }]),
);

export const RECORDED_IDS: ReadonlySet<string> = new Set(RECORDED_SUMMARIES.map((s) => s.case_id));

export function isRecorded(caseId: string): boolean {
  return RECORDED_IDS.has(caseId);
}

const loads = new Map<string, Promise<RecordedSnapshot>>();
const loaded = new Map<string, RecordedSnapshot>();

/** Fetch one recorded case's responses (once per page load). */
export function loadRecorded(caseId: string): Promise<RecordedSnapshot> {
  let p = loads.get(caseId);
  if (!p) {
    p = fetch(`/demo-cases/${encodeURIComponent(caseId)}.json`).then(async (r) => {
      if (!r.ok) throw new Error(`The recorded case ${caseId} could not be loaded (${r.status}).`);
      const snap = (await r.json()) as RecordedSnapshot;
      loaded.set(caseId, snap);
      return snap;
    });
    p.catch(() => loads.delete(caseId));
    loads.set(caseId, p);
  }
  return p;
}

/** The snapshot if it is already loaded (synchronous callers). */
export function recordedNow(caseId: string): RecordedSnapshot | null {
  return loaded.get(caseId) ?? null;
}

/** URL of a recorded page image, or null when the page is not in the recording. */
export function recordedPageUrl(caseId: string, docId: string, page: number): string | null {
  if (!isRecorded(caseId)) return null;
  const key = `${docId}-${page}`;
  const snap = loaded.get(caseId);
  if (snap && !snap.pages.includes(key)) return null;
  return `/demo-cases/${encodeURIComponent(caseId)}/pages/${encodeURIComponent(key)}.png`;
}

/** Download links of the recorded export for a format (the files sit under public/ at the client's usual path). */
export function recordedExportUrls(caseId: string, format: ExportFormat): string[] {
  const ext = format === "PDF" ? ".pdf" : ".docx";
  const names = (loaded.get(caseId)?.exports[format] ?? loaded.get(caseId)?.exports.DOCX ?? []).filter(
    (n) => n.endsWith(".zip") || n.endsWith(ext),
  );
  return names.map((n) => `/api/cases/${encodeURIComponent(caseId)}/export/files/${encodeURIComponent(n)}`);
}

