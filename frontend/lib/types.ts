// Mirrors src/vakeel_sahayak/schemas/ and src/vakeel_sahayak/api/models.py (plan §3.3, §4.6, §5, §6.3, §7-§11).
// Keep in sync with the pydantic models. Optional pydantic fields with a default are typed as optional (`?`) so that
// mock data can omit them; fields the backend always sends are required. Frontend-only shapes are marked "UI".

/* ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
 * Enums (schemas/enums.py). Each union has a matching const array for iteration.
 * ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */

export const FIELD_STATUSES = ["VERIFIED", "COMPUTED", "UNSUPPORTED", "AMBIGUOUS", "USER_STATED", "USER_EDITED"] as const;
/** Status of a dossier field (plan §7.1). */
export type FieldStatus = (typeof FIELD_STATUSES)[number];

export const SLOT_STATUSES = ["FILLED", "WEAK", "MISSING"] as const;
/** Assessment of an evidence-contract slot (plan §6.2). */
export type SlotStatus = (typeof SLOT_STATUSES)[number];

export const CLAIM_STATES = ["CURRENT", "STALE"] as const;
/** Truth-maintenance state of a brief claim (plan §10). */
export type ClaimState = (typeof CLAIM_STATES)[number];

export const CLAIM_CHECKS = ["SUPPORTED", "REPAIRED", "NEEDS_REVIEW"] as const;
/** Vakeel's check-and-repair outcome (plan §8.1). */
export type ClaimCheck = (typeof CLAIM_CHECKS)[number];

export const SPARRING_VERDICTS = ["ANSWERED", "PARTLY", "UNANSWERED"] as const;
/** Abhiyojak's verdict on a reply (plan §9). */
export type SparringVerdict = (typeof SPARRING_VERDICTS)[number];

export const RIGHTS_STATUSES = [
  "ELIGIBLE", "NOT_YET", "WINDOW_CLOSED", "CHECK", "NOT_APPLICABLE", "FLAG", "OK", "UNKNOWN", "BAR_APPLIES",
  "A", "B", "C", "D",
] as const;
/** Union of all Rights Radar output statuses (plan §7.3). */
export type RightsStatus = (typeof RIGHTS_STATUSES)[number];

export const RIGHTS_CHECK_NAMES = [
  "default_bail", "undertrial_limit", "notice_of_appearance", "grounds_of_arrest", "production_24h", "antil_category",
  "statutory_bar",
] as const;
/** The seven Rights Radar checks (plan §7.3, Appendix C). */
export type RightsCheckName = (typeof RIGHTS_CHECK_NAMES)[number];

export const TRANSFER_FLAGS = ["SAME_TEXT", "CHANGED", "NEW"] as const;
/** IPC-to-BNS transfer flag on a precedent (plan §5.4). */
export type TransferFlag = (typeof TRANSFER_FLAGS)[number];

export const GOOD_LAW_STATUSES = ["OK", "OVERRULED", "DISTINGUISHED", "UNKNOWN"] as const;
/** Good-law flag on an authority (plan §5.3). */
export type GoodLawStatus = (typeof GOOD_LAW_STATUSES)[number];

export const TREATMENTS = ["FOLLOWED", "RELIED_ON", "DISTINGUISHED", "OVERRULED", "REFERRED", "UNKNOWN"] as const;
/** How a citing sentence treats the cited case (plan §5.3). */
export type Treatment = (typeof TREATMENTS)[number];

export const CONCORDANCE_EDGE_TYPES = ["SAME", "SPLIT", "MERGED", "REWORDED", "NEW"] as const;
/** Typed edge of the IPC/BNS and CrPC/BNSS concordance (plan §5.1). */
export type ConcordanceEdgeType = (typeof CONCORDANCE_EDGE_TYPES)[number];

export const FACTOR_STANCES = ["favourable", "adverse", "not_applicable"] as const;
/** Sutradhar's per-factor stance (plan §6.2). */
export type FactorStance = (typeof FACTOR_STANCES)[number];

export const OPEN_ISSUE_TYPES = ["NEEDS_REVIEW", "CHANGED_PROVISION", "MISSING_EVIDENCE"] as const;
/** Type of open issue in a BailBrief (plan §8.1). */
export type OpenIssueType = (typeof OPEN_ISSUE_TYPES)[number];

export const AGENT_NAMES = ["MUNSHI", "PESHKAR", "SUTRADHAR", "VAKEEL", "ABHIYOJAK", "PAIROKAR"] as const;
/** The six agents (plan §3.2). */
export type AgentName = (typeof AGENT_NAMES)[number];

export const FACTORS = [
  "gravity_and_punishment", "custody_period", "charge_sheet_filed", "trial_delay", "parity_with_co_accused",
  "antecedents", "flight_risk", "witness_tampering", "weak_prima_facie", "health_age_family", "statutory_bar",
  "undertrial_period",
] as const;
/** The 12 bail factors (plan Appendix A). */
export type Factor = (typeof FACTORS)[number];

export const SHELVES = ["law", "caselaw", "advocacy", "case"] as const;
/** The four shelves (plan §5.1). */
export type Shelf = (typeof SHELVES)[number];

export const STORE_NAMES = [
  "law.statutes", "law.concordance", "caselaw.reasoning", "caselaw.citations", "caselaw.similar",
  "advocacy.arguments", "advocacy.objections", "case.docs", "case.timeline", "case.facts",
] as const;
/** The ten stores (plan §5.1). */
export type StoreName = (typeof STORE_NAMES)[number];

export const DOCUMENT_TYPES = [
  "FIR", "ARREST_MEMO", "REMAND_ORDER", "BAIL_ORDER", "ORDER_SHEET", "CHARGE_SHEET_COVER", "CUSTODY_CERTIFICATE",
  "MEDICAL_RECORD", "AFFIDAVIT", "OTHER",
] as const;
/** Document labels assigned by Munshi (plan §4.3). */
export type DocumentType = (typeof DOCUMENT_TYPES)[number];

export const INPUT_KINDS = [
  "K1_BORN_DIGITAL", "K2_SCANNED", "K3_DEGRADED", "K4_PHONE_PHOTO", "K5_HINDI_MIXED", "K6_LEGACY_HINDI_FONT",
  "K7_HANDWRITING", "K8_BUNDLE", "K9_LOCKED_OR_BROKEN", "K10_NOT_PDF",
] as const;
/** Input kinds K1-K10 (plan §4.1). */
export type InputKind = (typeof INPUT_KINDS)[number];

export const PARSE_ROUTES = ["text_layer", "layout", "ocr", "vision", "ask_counsel"] as const;
/** Rungs of the routing ladder (plan §4.2). */
export type ParseRoute = (typeof PARSE_ROUTES)[number];

export const PAGE_STATUSES = ["OK", "UNREADABLE"] as const;
/** Final status of a page after routing (plan §4.6). */
export type PageStatus = (typeof PAGE_STATUSES)[number];

export const ORDER_PARTS = ["facts", "defense_submissions", "prosecution_submissions", "reasoning", "operative_order"] as const;
/** Part of a court order (plan §5.2). Authorities are cited from `reasoning` only. */
export type OrderPart = (typeof ORDER_PARTS)[number];

export const INFO_KINDS = ["dated_event", "party", "section", "earlier_outcome", "custody", "personal_circumstance"] as const;
/** Kind of information a paragraph holds (plan §4.3). */
export type InfoKind = (typeof INFO_KINDS)[number];

export const EVENT_KINDS = [
  "TOOL_CALL", "TOOL_RESULT", "AGENT_MESSAGE", "STORE_WRITE", "GATE_OPENED", "GATE_APPROVED", "GATE_REJECTED",
  "BUDGET_HIT", "USER_ACTION", "CHANGE_SET_APPROVED", "CLAIM_STALED", "ERROR",
] as const;
/** Kinds of event-log entries (plan §3.3). */
export type EventKind = (typeof EVENT_KINDS)[number];

export const GATE_IDS = ["GATE_1_DOSSIER", "GATE_2_EXPORT"] as const;
/** The two approval gates (plan §3.1). */
export type GateId = (typeof GATE_IDS)[number];

export const STAGE_IDS = ["INTAKE", "DOSSIER", "RIGHTS", "BRIEF", "SPAR", "HEARING_PREP", "FILE"] as const;
/** Workspace stages (plan §13.5). */
export type Stage = (typeof STAGE_IDS)[number];

export const EXPORT_FORMATS = ["DOCX", "PDF"] as const;
/** Export formats (plan §8.2, §13.1). */
export type ExportFormat = (typeof EXPORT_FORMATS)[number];

export const DOC_LANGS = ["en", "hi", "mixed"] as const;
/** Document language codes. */
export type DocLang = (typeof DOC_LANGS)[number];

/** Actor of an event: an agent or counsel (schemas/events.py COUNSEL). */
export type Actor = AgentName | "counsel";
export const COUNSEL = "counsel" as const;

/** Exact draft label (schemas/bail_brief.py DRAFT_LABEL); shown on every brief and export (plan §8.1, §16). */
export const DRAFT_LABEL = "AI-generated draft. Not legal advice." as const;

/* ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
 * Shared building blocks (schemas/common.py)
 * ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */

/** [x0, y0, x1, y1] in PDF points of the page (origin top-left), as Munshi records it. */
export type Box = [number, number, number, number];

/** Where a value came from (plan §4.4, §7.1). `doc` may be "d1" or "d1 (FIR)"; use parseDocId() from lib/format. */
export interface SourceRef {
  doc?: string | null;
  page?: number | null;
  box?: Box | number[] | null;
  lang?: string | null;
  route?: string | null;
  quote?: string | null;
  /** English translation of a Hindi quote (plan §4.5). */
  quote_en?: string | null;
  /** Set when status is COMPUTED. */
  tool?: string | null;
  /** e.g. "turn 3" for USER_STATED. */
  chat?: string | null;
}

/** A dossier value wrapped as {value, source, status} (plan §7.1). */
export interface TrackedField<T> {
  value: T | null;
  source: SourceRef | null;
  status: FieldStatus;
}

/* ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
 * IngestionReport (schemas/ingestion_report.py, plan §4.6)
 * ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */

export interface PageRoute {
  page: number;
  /** Free text, e.g. "scanned, handwriting". */
  kind: string;
  /** Steps taken, e.g. ["text_layer: rejected (legacy font)", "ocr: surya-hi"]. */
  route: string[];
  ocr_conf?: number | null;
  status: PageStatus;
}

export interface DocumentEntry {
  doc_id: string;
  type: DocumentType;
  /** [first, last] page of the file. */
  pages: [number, number] | number[];
  lang: string;
  type_confidence?: number | null;
  page_routes: PageRoute[];
}

export interface FiledCounts {
  timeline_events: number;
  parties: number;
  sections: number;
  chunks: number;
}

export interface Gap {
  item: string;
  action: string;
}

export interface IngestionReport {
  case_id: string;
  file: string;
  documents: DocumentEntry[];
  filed: FiledCounts;
  gaps: Gap[];
  questions: string[];
}

/* ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
 * CaseDossier (schemas/dossier.py, plan §7.1)
 * ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */

export interface FirValue {
  number?: string | null;
  police_station?: string | null;
  date?: string | null;
}

export interface SectionValue {
  as_written: string;
  code: string;
  section: string;
  equivalent?: string | null;
  bailable?: boolean | null;
  max_punishment?: string | null;
}

export interface ChargeSheetValue {
  filed: boolean;
  date?: string | null;
}

export interface PreviousBail {
  court: string;
  date: string;
  outcome: string;
}

export interface CoAccusedBail {
  id: string;
  outcome: string;
  date?: string | null;
}

/** The dossier fields, each tracked (plan §7.1). `bnss_479` moved to the RightsReport. */
export interface DossierFields {
  fir: TrackedField<FirValue>;
  offence_date: TrackedField<string>;
  sections: TrackedField<SectionValue[]>;
  arrest_date: TrackedField<string>;
  first_remand: TrackedField<string>;
  custody_days: TrackedField<number>;
  charge_sheet: TrackedField<ChargeSheetValue>;
  trial_stage: TrackedField<string>;
  previous_bail: TrackedField<PreviousBail[]>;
  co_accused_bail: TrackedField<CoAccusedBail[]>;
  antecedents: TrackedField<string[]>;
  personal: TrackedField<string[]>;
  parties: TrackedField<string[]>;
}

export type DossierFieldName = keyof DossierFields;
/** Value type of one dossier field. */
export type DossierFieldValue<K extends DossierFieldName> = DossierFields[K] extends TrackedField<infer V> ? V : never;

export const DOSSIER_FIELD_NAMES = [
  "fir", "offence_date", "sections", "arrest_date", "first_remand", "custody_days", "charge_sheet", "trial_stage",
  "previous_bail", "co_accused_bail", "antecedents", "personal", "parties",
] as const satisfies readonly DossierFieldName[];

export interface CaseDossier {
  case_id: string;
  court?: string | null;
  as_of?: string | null;
  fields: DossierFields;
  open_questions: string[];
}

/* ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
 * Timeline and store rows (schemas/store_rows.py, plan §5, §7.2)
 * ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */

/** A dated event with source: one row of the List of Dates (plan §4.4, §7.2). */
export interface TimelineEvent {
  event_id: string;
  date: string;
  label: string;
  source?: SourceRef | null;
  status: FieldStatus;
  /** Event ids of rows that disagree with this one; shown side by side. */
  conflicts_with: string[];
}

export interface StatuteRow {
  code: string;
  section: string;
  text: string;
  max_punishment?: string | null;
  bailable?: boolean | null;
  cognisable?: boolean | null;
}

export interface ConcordanceEdge {
  old_ref: string;
  new_ref: string;
  type: ConcordanceEdgeType;
  text_diff?: string | null;
}

/** A paragraph row with metadata (plan §5.2). */
export interface ParagraphRecord {
  doc_id: string;
  para: number;
  court: string;
  date: string;
  outcome?: string | null;
  part: OrderPart;
  sections: string[];
  section_family: string[];
  factors: Factor[];
  cites: string[];
  authority: number;
  text: string;
}

export interface CitationEdge {
  citing_doc_id: string;
  cited_doc_id: string;
  treatment: Treatment;
  court_level?: string | null;
  sentence?: string | null;
}

export interface FactSignature {
  sections: string[];
  custody_band?: string | null;
  charge_sheet_status?: string | null;
  co_accused_outcome?: string | null;
}

export interface SimilarOrderRow {
  doc_id: string;
  court: string;
  date: string;
  signature: FactSignature;
}

export interface CaseChunk {
  chunk_id: string;
  doc_id: string;
  doc_type: DocumentType;
  page: number;
  box?: Box | number[] | null;
  text: string;
  text_en?: string | null;
  info_kinds: InfoKind[];
}

/* ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
 * RightsReport (schemas/rights_report.py, plan §7.3)
 * ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */

export interface RightsCheckResult {
  check: RightsCheckName;
  status: RightsStatus;
  detail?: string | null;
  /** Dossier fields / events used. */
  uses: string[];
  /** Source citation, e.g. "BNSS s.187(3)". */
  rule?: string | null;
  /** The rule as coded (Appendix C), shown with every output. */
  rule_text?: string | null;
  /** Full source list for the rule. */
  sources?: string[];
  /** The dates the rule used, e.g. {first_remand: "2024-08-21"}. */
  dates?: Record<string, string>;
  last_verified?: string | null;
}

export interface RightsReport {
  case_id: string;
  as_of: string;
  checks: RightsCheckResult[];
}

/* ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
 * RetrievalPlan and EvidencePack (schemas/retrieval_plan.py, plan §6.3)
 * ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */

export interface BudgetLeft {
  store_calls: number;
  tokens: number;
}

/** One tool call in a plan. Args may contain "$slot.field" references. */
export interface PlanStep {
  slot: string;
  tool: string;
  args: Record<string, unknown>;
}

export interface RetrievalPlan {
  factor: Factor;
  round: number;
  budget_left: BudgetLeft;
  steps: PlanStep[];
  /** slot -> "FILLED" | "WEAK (1 of 2)" | "MISSING". Use parseSlotAssessment() from lib/status. */
  assessment: Record<string, string>;
  next?: string | null;
}

export interface SlotResult {
  slot: string;
  status: SlotStatus;
  items: Record<string, unknown>[];
  note?: string | null;
}

export interface EvidencePack {
  factor: Factor;
  stance: FactorStance;
  reason?: string | null;
  slots: SlotResult[];
  open_issues: string[];
}

/* ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
 * BailBrief (schemas/bail_brief.py, plan §8.1, §10)
 * ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */

/** A cited authority; citation text is rendered from corpus metadata, never model-written (plan §8.1). */
export interface Authority {
  doc_id: string;
  para: number;
  citation?: string | null;
  transfer?: TransferFlag | null;
  good_law: GoodLawStatus;
  sc_root?: string | null;
}

/** Dependencies of a claim for truth maintenance (plan §10). */
export interface DependsOn {
  /** field -> value hash "h:3f2a". */
  facts: Record<string, string>;
  events: string[];
  rights: string[];
  /** "doc_id#para". */
  authorities: string[];
  /** Claims this one cites. */
  claims: string[];
}

export interface Ground {
  id: string;
  factor: Factor;
  stance: FactorStance;
  /** Each sentence cites [F:field] facts and [A:doc#para] authorities. Use parseArgument() from lib/format. */
  argument: string;
  authorities: Authority[];
  depends_on: DependsOn;
  check: ClaimCheck;
  state: ClaimState;
}

export interface OpenIssue {
  type: OpenIssueType;
  item: string;
}

export interface StatutoryPosition {
  sections: string[];
  bailable?: boolean | null;
  max_punishment?: string | null;
  rights?: string | null;
}

export interface BailBrief {
  case_id: string;
  statutory_position: StatutoryPosition;
  grounds: Ground[];
  open_issues: OpenIssue[];
  /** Always exactly DRAFT_LABEL. */
  label: string;
}

/* ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
 * SparringRecord (schemas/sparring.py, plan §9)
 * ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */

/** What grounds an objection: a bank paragraph, refusal reasoning, statute or dossier fact. */
export interface ObjectionGround {
  store?: string | null;
  doc_id?: string | null;
  para?: number | null;
  fact?: string | null;
}

export interface Reply {
  text: string;
  authorities: Authority[];
  check: ClaimCheck;
}

export interface Objection {
  id: string;
  /** Ground id or "general". */
  against: string;
  factor: string;
  objection: string;
  grounds: ObjectionGround[];
  reply: Reply | null;
  verdict: SparringVerdict | null;
  reason?: string | null;
}

export interface SparringRecord {
  case_id: string;
  rounds: number;
  objections: Objection[];
  /** Ungrounded objections, logged. */
  discarded: string[];
}

/* ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
 * TriageCard (schemas/triage.py, plan §11)
 * ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */

export interface TriageCard {
  case_id: string;
  urgency_rank: number;
  reasons: string[];
  flags: string[];
  missing_docs: string[];
  next_step?: string | null;
}

/* ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
 * Event log (schemas/events.py, plan §3.3)
 * ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */

/** One append-only event-log entry: who, which tool, inputs, outputs, sources, time. */
export interface AgentEvent {
  event_id: string;
  case_id: string;
  /** ISO-8601 timestamp. */
  ts: string;
  kind: EventKind;
  actor: Actor | string;
  tool?: string | null;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  sources: SourceRef[];
  /** Causal link used by truth maintenance. */
  parent_id?: string | null;
}

/** Same as AgentEvent; named like the pydantic class. (Shadows the DOM `Event` type where imported.) */
export type Event = AgentEvent;

/* ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
 * ChangeSet (schemas/change_set.py, plan §7.4, §10)
 * ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */

export interface FieldChange {
  field: string;
  old_hash?: string | null;
  new_hash?: string | null;
}

export type ChangeSetTrigger = "new_document" | "clock" | "counsel_edit";

export interface ChangeSet {
  case_id: string;
  trigger: ChangeSetTrigger | string;
  fields: FieldChange[];
  new_event_ids: string[];
  rights_changed: string[];
}

/* ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
 * Chat (schemas/chat.py, plan §6.4)
 * ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */

/** Store/tool chip shown on an answer (plan §13.5). */
export interface ToolChip {
  tool: string;
  store?: StoreName | null;
}

export type ChatRole = "counsel" | "agent";

export interface ChatMessage {
  message_id: string;
  case_id: string;
  role: ChatRole;
  agent?: AgentName | null;
  text: string;
  chips: ToolChip[];
  /** Prediction / lay-advice requests are refused. */
  refused: boolean;
}

/* ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
 * Case-level view models (schemas/case.py, plan §13.5)
 * ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */

/** Card on the /cases cause list. `rights_chips` are "STATUS · label" strings; see parseRightsChip() in lib/status. */
export interface CaseSummary {
  case_id: string;
  title: string;
  stage: Stage;
  rights_chips: string[];
  needs_attention: number;
}

/** State of an approval gate. `open` is true while the gate has NOT been approved (record/gates.py). */
export interface GateStatus {
  gate: GateId;
  open: boolean;
  unresolved_unsupported: string[];
  unresolved_needs_review: string[];
  unresolved_unanswered: string[];
}

/** Spend shown in the UI (plan §6.2). */
export interface BudgetState {
  tokens_spent: number;
  tokens_cap: number;
  /** store -> calls made. */
  store_calls: Record<string, number>;
}

/* ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
 * API request / response models (api/models.py)
 * ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */

export interface NewCaseRequest {
  title?: string | null;
}

export interface ChatRequest {
  text: string;
}

export interface ApproveRequest {
  acknowledged_fields: string[];
}

export interface FieldEditRequest {
  value: unknown;
}

export interface ExportRequest {
  format: ExportFormat;
}

export interface UploadResponse {
  case_id: string;
  accepted: string[];
  questions: string[];
}

export interface DeskBoard {
  cards: TriageCard[];
}

/* ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
 * Tool results that reach the UI through events and chat (tools/types.py)
 * ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */

export interface DateCalcResult {
  value: number | string;
  rule: string;
  start: string;
  end: string;
}

export interface MapSectionResult {
  equivalent?: string | null;
  edge_type?: ConcordanceEdgeType | null;
  ambiguous: boolean;
  governing?: string | null;
  candidates: string[];
}

export interface TransferCheckResult {
  flag: TransferFlag;
  text_diff?: string | null;
  qualification?: string | null;
}

export interface GoodLawResult {
  status: GoodLawStatus;
  overruled_by?: string | null;
  sc_root?: string | null;
  note?: string | null;
}

/* ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
 * Shapes the backend returns as dict[str, Any]. Defined here (UI) and listed as a shared change for the backend.
 * ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */

/** POST /api/cases/{id}/draft. */
export interface DraftStartResponse {
  status: string;
  [key: string]: string;
}

/** A likely concern from the bench (plan §8.3), answered by pointing to a ground and an authority. */
export interface PrepConcern {
  concern: string;
  factor: Factor;
  /** Why this concern: comparable orders / reasoning paragraphs (never a rate). */
  basis: string;
  answer: string;
  ground_id?: string | null;
  authority?: string | null;
  sources?: string[];
}

export interface PrepLeadPoint {
  ground_id: string;
  point: string;
}

/** A condition courts often impose in similar grants, taken from operative orders. Never a rate. */
export interface PrepCondition {
  condition: string;
  seen_in: string[];
}

/** GET /api/cases/{id}/prep: the one-page hearing-prep card (plan §8.3). No outcome prediction, no grant rates. */
export interface HearingPrepCard {
  case_id: string;
  hearing_date?: string | null;
  likely_concerns: PrepConcern[];
  /** Exactly three strongest SUPPORTED grounds. */
  lead_points: PrepLeadPoint[];
  conditions: PrepCondition[];
  open_issues: string[];
  label: string;
}

/** A judgment node in the citation graph (plan §5.3). */
export interface CitationNode {
  doc_id: string;
  /** Rendered from corpus metadata. */
  citation: string;
  court: string;
  court_level: "SC" | "HC" | "DC" | string;
  date: string;
  good_law: GoodLawStatus;
  authority: number;
  overruled_by?: string | null;
  sc_root?: string | null;
  outcome?: string | null;
}

/** GET /api/library/citations/{doc_id}. */
export interface CitationGraphData {
  root: string;
  nodes: CitationNode[];
  edges: CitationEdge[];
}

export type DiffOp = "equal" | "insert" | "delete";

export interface DiffSegment {
  op: DiffOp;
  text: string;
}

/** GET /api/library/bridge/{code}/{section}: the IPC<->BNS bridge with a text diff (plan §5.4). */
export interface BridgeData {
  query: string;
  old_ref: string;
  new_ref: string;
  edge_type: ConcordanceEdgeType;
  flag: TransferFlag;
  old_heading?: string | null;
  new_heading?: string | null;
  old_text: string;
  new_text: string;
  /** Unified diff text, as stored on the concordance edge. */
  text_diff?: string | null;
  /** Word-level diff segments (old -> new). */
  diff: DiffSegment[];
  old_max_punishment?: string | null;
  new_max_punishment?: string | null;
  /** What the brief must say when the flag is CHANGED. */
  qualification?: string | null;
  /** Other edges touching either section. */
  related: ConcordanceEdge[];
}

/** GET /api/library/search: a paragraph plus the good-law flag and rendered citation when the backend adds them. */
export interface LibrarySearchHit extends ParagraphRecord {
  good_law?: GoodLawStatus;
  citation?: string;
  transfer?: TransferFlag | null;
}

/* ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
 * UI-only shapes
 * ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */

/** The source the PDF viewer should scroll to and highlight. */
export interface SelectedSource {
  doc_id: string;
  page: number;
  box?: Box | null;
  quote?: string | null;
  quote_en?: string | null;
  lang?: string | null;
  route?: string | null;
  /** What asked for it (a field name, a citation, a timeline row), for aria-live announcements. */
  origin?: string | null;
}

/** One line of a demo page facsimile (demo mode has no real PDF; see lib/mock/pages.ts). */
export interface MockPageLine {
  text: string;
  /** English translation for Hindi lines. */
  text_en?: string;
  box: Box;
  handwritten?: boolean;
  /** Visual emphasis: heading line, stamp, signature. */
  style?: "heading" | "body" | "stamp" | "signature" | "table";
}

/** A demo page facsimile, sized in PDF points (A4: 595 x 842). */
export interface MockPage {
  doc_id: string;
  page: number;
  width: number;
  height: number;
  lang: string;
  kind: string;
  /** Rotation in degrees for skewed scans and photos (render with transform only). */
  skew?: number;
  unreadable?: boolean;
  lines: MockPageLine[];
}

/** Why a ground was redrafted (plan §10): shown as a change highlight in the Brief tab. */
export interface GroundRevision {
  ground_id: string;
  reason: string;
  /** Changed dependencies, e.g. ["custody_days"]. */
  changed: string[];
  previous_argument?: string | null;
  at: string;
}

/** GET /healthz: the server's effective settings for the Settings page (src/vakeel_sahayak/api/asgi.py `_settings`). Never carries a key. */
export interface ServerStatus {
  status: string;
  api_implemented: boolean;
  /** VS_MODELS: "offline" (built-in stand-ins), "real" or "auto". */
  models: string | null;
  /** VS_LLM_BACKEND: "offline" | "local" | "sarvam" | "openai"; null when each role follows configs/models.yaml. */
  llm_backend: string | null;
  /** VS_EXTERNAL: the shared gate for hosted model services ("off" | "public" | "pseudonymised" | "consented"). */
  external: string | null;
  sarvam: string | null;
  openai: string | null;
  data_dir: string | null;
}
