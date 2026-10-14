// Mirrors src/vakeel_sahayak/schemas/ (plan §4.6, §6.3, §7, §8, §9, §11, §3.3). Keep in sync.

export type FieldStatus = "VERIFIED" | "COMPUTED" | "UNSUPPORTED" | "AMBIGUOUS" | "USER_STATED" | "USER_EDITED";
export type SlotStatus = "FILLED" | "WEAK" | "MISSING";
export type ClaimState = "CURRENT" | "STALE";
export type ClaimCheck = "SUPPORTED" | "REPAIRED" | "NEEDS_REVIEW";
export type SparringVerdict = "ANSWERED" | "PARTLY" | "UNANSWERED";
export type RightsStatus =
  | "ELIGIBLE" | "NOT_YET" | "WINDOW_CLOSED" | "CHECK" | "NOT_APPLICABLE"
  | "FLAG" | "OK" | "UNKNOWN" | "BAR_APPLIES" | "A" | "B" | "C" | "D";
export type RightsCheckName =
  | "default_bail" | "undertrial_limit" | "notice_of_appearance" | "grounds_of_arrest"
  | "production_24h" | "antil_category" | "statutory_bar";
export type TransferFlag = "SAME_TEXT" | "CHANGED" | "NEW";
export type GoodLawStatus = "OK" | "OVERRULED" | "DISTINGUISHED" | "UNKNOWN";
export type AgentName = "MUNSHI" | "PESHKAR" | "SUTRADHAR" | "VAKEEL" | "ABHIYOJAK" | "PAIROKAR";
export type StoreName =
  | "law.statutes" | "law.concordance" | "caselaw.reasoning" | "caselaw.citations" | "caselaw.similar"
  | "advocacy.arguments" | "advocacy.objections" | "case.docs" | "case.timeline" | "case.facts";
export type Factor =
  | "gravity_and_punishment" | "custody_period" | "charge_sheet_filed" | "trial_delay" | "parity_with_co_accused"
  | "antecedents" | "flight_risk" | "witness_tampering" | "weak_prima_facie" | "health_age_family"
  | "statutory_bar" | "undertrial_period";
export type Stage = "INTAKE" | "DOSSIER" | "RIGHTS" | "BRIEF" | "SPAR" | "HEARING_PREP" | "FILE";
export type GateId = "GATE_1_DOSSIER" | "GATE_2_EXPORT";
export type EventKind =
  | "TOOL_CALL" | "TOOL_RESULT" | "AGENT_MESSAGE" | "STORE_WRITE" | "GATE_OPENED" | "GATE_APPROVED"
  | "GATE_REJECTED" | "BUDGET_HIT" | "USER_ACTION" | "CHANGE_SET_APPROVED" | "CLAIM_STALED" | "ERROR";

export interface SourceRef {
  doc?: string; page?: number; box?: [number, number, number, number]; lang?: string; route?: string;
  quote?: string; quote_en?: string; tool?: string; chat?: string;
}
export interface TrackedField<T> { value: T | null; source: SourceRef | null; status: FieldStatus }

export interface PageRoute { page: number; kind: string; route: string[]; ocr_conf?: number; status: "OK" | "UNREADABLE" }
export interface DocumentEntry { doc_id: string; type: string; pages: [number, number]; lang: string; type_confidence?: number; page_routes: PageRoute[] }
export interface IngestionReport {
  case_id: string; file: string; documents: DocumentEntry[];
  filed: { timeline_events: number; parties: number; sections: number; chunks: number };
  gaps: { item: string; action: string }[]; questions: string[];
}

export interface CaseDossier {
  case_id: string; court?: string; as_of?: string;
  fields: Record<string, TrackedField<unknown>>;
  open_questions: string[];
}

export interface RightsCheckResult { check: RightsCheckName; status: RightsStatus; detail?: string; uses: string[]; rule?: string; last_verified?: string }
export interface RightsReport { case_id: string; as_of: string; checks: RightsCheckResult[] }

export interface PlanStep { slot: string; tool: string; args: Record<string, unknown> }
export interface RetrievalPlan {
  factor: Factor; round: number; budget_left: { store_calls: number; tokens: number };
  steps: PlanStep[]; assessment: Record<string, string>; next?: string;
}

export interface Authority { doc_id: string; para: number; citation?: string; transfer?: TransferFlag; good_law: GoodLawStatus; sc_root?: string }
export interface Ground {
  id: string; factor: Factor; stance: "favourable" | "adverse" | "not_applicable"; argument: string; authorities: Authority[];
  depends_on: { facts: Record<string, string>; events: string[]; rights: string[]; authorities: string[]; claims: string[] };
  check: ClaimCheck; state: ClaimState;
}
export interface BailBrief {
  case_id: string;
  statutory_position: { sections: string[]; bailable?: boolean; max_punishment?: string; rights?: string };
  grounds: Ground[];
  open_issues: { type: "NEEDS_REVIEW" | "CHANGED_PROVISION" | "MISSING_EVIDENCE"; item: string }[];
  label: string;
}

export interface Objection {
  id: string; against: string; factor: string; objection: string;
  grounds: { store?: string; doc_id?: string; para?: number; fact?: string }[];
  reply: { text: string; authorities: Authority[]; check: ClaimCheck } | null; verdict: SparringVerdict | null; reason?: string;
}
export interface SparringRecord { case_id: string; rounds: number; objections: Objection[]; discarded: string[] }

export interface TriageCard { case_id: string; urgency_rank: number; reasons: string[]; flags: string[]; missing_docs: string[]; next_step?: string }

export interface AgentEvent {
  event_id: string; case_id: string; ts: string; kind: EventKind; actor: AgentName | "counsel";
  tool?: string; inputs: Record<string, unknown>; outputs: Record<string, unknown>; sources: SourceRef[]; parent_id?: string;
}
export interface ChatMessage { message_id: string; case_id: string; role: "counsel" | "agent"; agent?: AgentName; text: string; chips: { tool: string; store?: StoreName }[]; refused: boolean }
export interface CaseSummary { case_id: string; title: string; stage: Stage; rights_chips: string[]; needs_attention: number }
export interface GateStatus { gate: GateId; open: boolean; unresolved_unsupported: string[]; unresolved_needs_review: string[]; unresolved_unanswered: string[] }
