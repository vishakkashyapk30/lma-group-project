// Scripted agent events for the live trace in demo mode (plan §3.3, §4.3, §6.2, §7, §8.1, §9, §10). The vocabulary
// follows the backend's event folding (src/vakeel_sahayak/record/views.py): STORE_WRITE with inputs.store (and
// inputs.view for whole-object views), USER_ACTION with inputs.action, GATE_* with inputs.gate, CLAIM_STALED with
// outputs.claim_ids. AGENT_MESSAGE outputs carry `text` and, on the last message of a run, `status: "done"`.
import type { Actor, AgentEvent, EventKind, SourceRef } from "../types";
import { MOCK_CASE_ID } from "./case0007";

/** Demo-state change applied just before a step's event is delivered (interpreted by lib/mock/server.ts). */
export type DemoEffect =
  | "ingestion" | "dossier" | "dates" | "rights" | "gate1Opened" | "brief" | "spar" | "prep" | "gate2Opened"
  | "certificateIngested" | "certificateDossier" | "certificateRights" | "redraft" | "budget";

export interface ScriptStep {
  kind: EventKind;
  actor: Actor;
  tool?: string;
  inputs?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  sources?: SourceRef[];
  /** Milliseconds to wait before this step (default 450). */
  delay?: number;
  effect?: DemoEffect;
}

const say = (actor: Actor, text: string, extra?: Record<string, unknown>, delay?: number): ScriptStep => ({
  kind: "AGENT_MESSAGE", actor, outputs: { text, ...extra }, delay,
});
const call = (actor: Actor, tool: string, inputs: Record<string, unknown> = {}, delay?: number): ScriptStep => ({
  kind: "TOOL_CALL", actor, tool, inputs, delay,
});
const result = (actor: Actor, tool: string, outputs: Record<string, unknown>, delay?: number, sources?: SourceRef[]): ScriptStep => ({
  kind: "TOOL_RESULT", actor, tool, outputs, delay, sources,
});
const write = (actor: Actor, tool: string, inputs: Record<string, unknown>, outputs: Record<string, unknown>, effect?: DemoEffect, delay?: number): ScriptStep => ({
  kind: "STORE_WRITE", actor, tool, inputs, outputs, effect, delay,
});

/* ── Flow 1: Munshi reads the bundle, Peshkar builds the dossier, the Rights Radar runs, Gate 1 opens ──────────── */

export function intakeScript(file = "bundle_1.pdf"): ScriptStep[] {
  return [
    { kind: "USER_ACTION", actor: "counsel", inputs: { action: "upload", files: [file] }, delay: 100 },
    say("MUNSHI", `Surveying ${file}: 14 pages`, { phase: "survey" }, 300),
    call("MUNSHI", "inspect_page", { pages: "1-14" }),
    result("MUNSHI", "inspect_page", { summary: "text layer on 9 pages; legacy-font pattern on p.1; images only on p.2-3, 6-10", pages: 14 }),
    call("MUNSHI", "read_text_layer", { page: 1 }),
    result("MUNSHI", "read_text_layer", { page: 1, accepted: false, reason: "legacy font (Kruti Dev-style) decodes to Latin gibberish", route: "text_layer: rejected (legacy font)" }),
    call("MUNSHI", "ocr_page", { page: 1, lang: "hi" }),
    result("MUNSHI", "ocr_page", { page: 1, engine: "surya-hi", mean_conf: 0.81, route: "ocr: surya-hi", badge: "OCR" }),
    call("MUNSHI", "ocr_page", { page: 2, lang: "hi" }),
    result("MUNSHI", "ocr_page", { page: 2, engine: "surya-hi", mean_conf: 0.42, handwriting: true, escalate: "vision" }),
    call("MUNSHI", "vision_read_page", { page: 2, mode: "transcribe" }),
    result("MUNSHI", "vision_read_page", { page: 2, ok: true, route: "vision: qwen3-vl", badge: "VISION" }),
    call("MUNSHI", "clean_image", { page: 3, ops: ["dewarp"] }),
    call("MUNSHI", "vision_read_page", { page: 3, mode: "transcribe" }),
    result("MUNSHI", "vision_read_page", { page: 3, ok: false, status: "UNREADABLE", note: "transcript failed the word-list check" }),
    call("MUNSHI", "read_text_layer", { pages: "4-5" }),
    result("MUNSHI", "read_text_layer", { pages: "4-5", accepted: true, route: "text_layer", badge: "TEXT" }),
    call("MUNSHI", "clean_image", { pages: "6-7", ops: ["deskew", "denoise"] }),
    call("MUNSHI", "ocr_page", { pages: "6-10", lang: "en" }),
    result("MUNSHI", "ocr_page", { pages: "6-10", engine: "surya-en", mean_conf: 0.85, escalate_pages: [7] }),
    call("MUNSHI", "parse_layout", { pages: "11-12" }),
    result("MUNSHI", "parse_layout", { pages: "11-12", tables: 2, route: "layout: docling", badge: "LAYOUT" }),
    call("MUNSHI", "split_bundle", { file }),
    result("MUNSHI", "split_bundle", { documents: [{ doc_id: "d1", pages: [1, 3] }, { doc_id: "d2", pages: [4, 5] }, { doc_id: "d3", pages: [6, 7] }, { doc_id: "d4", pages: [8, 10] }, { doc_id: "d5", pages: [11, 12] }, { doc_id: "d6", pages: [13, 14] }] }),
    call("MUNSHI", "classify_document", { doc_ids: ["d1", "d2", "d3", "d4", "d5", "d6"] }),
    result("MUNSHI", "classify_document", { d1: "FIR", d2: "REMAND_ORDER", d3: "REMAND_ORDER", d4: "BAIL_ORDER", d5: "ORDER_SHEET", d6: "BAIL_ORDER", sensitive: false }),
    call("MUNSHI", "detect_script", { doc_id: "d1" }),
    call("MUNSHI", "translate", { doc_id: "d1", src: "hi", tgt: "en" }),
    result("MUNSHI", "translate", { doc_id: "d1", lines: 14, kept: "Hindi original + English translation" }),
    call("MUNSHI", "pseudonymise", { scope: "all documents" }),
    result("MUNSHI", "pseudonymise", { replaced: 7, tags: ["Accused-1", "Co-accused-1", "Complainant-1", "IO-1", "PS-1"] }),
    write("MUNSHI", "file_item", { store: "case.docs" }, { chunks: 31 }),
    write("MUNSHI", "file_item", { store: "case.timeline" }, { events: 11 }),
    write("MUNSHI", "file_item", { store: "case.facts" }, { parties: 4, sections: 2 }),
    call("MUNSHI", "search_pages", { query: "custody certificate", pages: "1-14" }),
    result("MUNSHI", "search_pages", { found: false }),
    call("MUNSHI", "ask_user", { questions: 3, grouped_unreadable_pages: [3] }),
    write("MUNSHI", "file_item", { store: "case.views", view: "ingestion_report" }, { documents: 6, questions: 3 }, "ingestion"),
    say("MUNSHI", "Filed 6 documents from 14 pages; 1 page unreadable; 3 questions for counsel.", { status: "done" }),

    say("PESHKAR", "Building the dossier from the case shelf", { phase: "extract" }, 500),
    call("PESHKAR", "extract_dossier", { store: "case.facts", fields: 13 }),
    call("PESHKAR", "span_check", { fields: 11 }),
    result("PESHKAR", "span_check", { supported: 10, failed: ["antecedents"], note: "antecedents not found in the file" }),
    call("PESHKAR", "map_section", { code: "BNS", section: "318(4)", offence_date: "2024-08-10" }),
    result("PESHKAR", "map_section", { equivalent: "IPC 420", edge_type: "SAME", governing: "BNS 318(4)" }),
    call("PESHKAR", "map_section", { code: "BNS", section: "316(2)", offence_date: "2024-08-10" }),
    result("PESHKAR", "map_section", { equivalent: "IPC 406", edge_type: "REWORDED", governing: "BNS 316(2)" }),
    call("PESHKAR", "date_calc", { start: "2024-08-20", end: "2025-02-03", rule: "custody_days" }),
    result("PESHKAR", "date_calc", { value: 167, rule: "custody_days", start: "2024-08-20", end: "2025-02-03" }),
    write("PESHKAR", "extract_dossier", { store: "case.facts" }, { fields: 13, unsupported: ["antecedents"], ambiguous: [] }, "dossier"),
    write("PESHKAR", "file_item", { store: "case.timeline" }, { events: 13, conflicts: [["e02", "e02b"]] }, "dates"),
    call("PESHKAR", "rights_check", { checks: 7 }),
    result("PESHKAR", "rights_check", { WINDOW_CLOSED: ["default_bail"], CHECK: ["undertrial_limit", "production_24h", "antil_category"], UNKNOWN: ["notice_of_appearance", "grounds_of_arrest"], NOT_APPLICABLE: ["statutory_bar"] }),
    write("PESHKAR", "rights_check", { store: "case.views", view: "rights_report" }, { checks: 7, flags: 6 }, "rights"),
    { kind: "GATE_OPENED", actor: "PESHKAR", tool: "request_approval", inputs: { gate: "GATE_1_DOSSIER" }, outputs: { gate: "GATE_1_DOSSIER", unresolved_unsupported: ["antecedents"] }, effect: "gate1Opened" },
    say("PESHKAR", "Dossier ready for review: 1 unsupported field (antecedents) and 1 date conflict (FIR date).", { status: "done" }),
  ];
}

/* ── Flow 3: Sutradhar plans, Vakeel drafts and checks, Abhiyojak spars, Gate 2 opens ──────────────────────────── */

export function draftScript(): ScriptStep[] {
  return [
    { kind: "USER_ACTION", actor: "counsel", inputs: { action: "draft" }, delay: 100 },
    say("SUTRADHAR", "Picking factors from the approved dossier and the RightsReport", { phase: "pick" }, 400),
    result("SUTRADHAR", "rights_check", { favourable: 7, adverse_to_answer: 2, not_applicable: 3 }),
    call("SUTRADHAR", "search_case_docs", { factor: "parity_with_co_accused", slot: "co_accused_order", store: "case.docs", query: "co-accused granted bail", doc_types: ["BAIL_ORDER"] }),
    call("SUTRADHAR", "search_reasoning", { factor: "parity_with_co_accused", slot: "authority", store: "caselaw.reasoning", section_family: ["BNS 318(4)", "IPC 420"], outcome: "granted", k: 10 }),
    result("SUTRADHAR", "search_reasoning", { factor: "parity_with_co_accused", slot: "authority", assessment: "WEAK (1 of 2)" }),
    call("SUTRADHAR", "citations", { factor: "parity_with_co_accused", slot: "good_law", store: "caselaw.citations", want: ["overruled_by", "sc_root"] }),
    call("SUTRADHAR", "search_objections", { factor: "parity_with_co_accused", slot: "likely_objection", store: "advocacy.objections" }),
    say("SUTRADHAR", "Parity, round 1: authority WEAK (1 of 2). Relaxing section_family to the offence group 'cheating'.", { factor: "parity_with_co_accused", round: 1 }),
    call("SUTRADHAR", "search_reasoning", { factor: "parity_with_co_accused", slot: "authority", store: "caselaw.reasoning", section_family: ["cheating"], k: 10 }),
    result("SUTRADHAR", "search_reasoning", { factor: "parity_with_co_accused", slot: "authority", assessment: "FILLED" }),
    call("SUTRADHAR", "get_timeline", { factor: "charge_sheet_filed", slot: "charge_sheet_date", store: "case.timeline" }),
    call("SUTRADHAR", "date_calc", { factor: "custody_period", store: "case.timeline", rule: "custody_days" }),
    call("SUTRADHAR", "similar_orders", { factor: "custody_period", store: "caselaw.similar", custody_band: "120-180 days" }),
    call("SUTRADHAR", "get_statute", { factor: "gravity_and_punishment", store: "law.statutes", code: "BNS", section: "318(4)" }),
    call("SUTRADHAR", "transfer_check", { factor: "gravity_and_punishment", store: "law.concordance", old_ref: "IPC 406", new_ref: "BNS 316(2)" }),
    result("SUTRADHAR", "transfer_check", { flag: "CHANGED", qualification: "maximum raised from three to five years" }),
    call("SUTRADHAR", "search_reasoning", { factor: "trial_delay", slot: "authority", store: "caselaw.reasoning", section_family: ["BNS 318(4)", "IPC 420"] }),
    call("SUTRADHAR", "search_reasoning", { factor: "trial_delay", slot: "authority", store: "caselaw.reasoning", section_family: ["cheating"] }),
    { kind: "BUDGET_HIT", actor: "SUTRADHAR", inputs: { factor: "trial_delay" }, outputs: { store_calls: 8, limit: 8, missing: ["sc_root"] }, effect: "budget" },
    call("SUTRADHAR", "get_fact", { factor: "antecedents", store: "case.facts", field: "antecedents" }),
    call("SUTRADHAR", "search_arguments", { factor: "health_age_family", store: "advocacy.arguments" }),
    say("SUTRADHAR", "Evidence packs ready for 7 factors; delegating to Vakeel.", { status: "done" }),

    say("VAKEEL", "Drafting one ground per factor; every sentence cites [F:field] and [A:doc#para]", { phase: "draft" }, 500),
    call("VAKEEL", "get_paragraph", { store: "caselaw.reasoning", doc_id: "DLHC-2022-1187", para: 14 }),
    call("VAKEEL", "check_claim", { claim: "G1" }),
    result("VAKEEL", "check_claim", { claim: "G1", supported: true, fact_support: 0.94, authority_support: 0.88, transfer: "SAME_TEXT", good_law: "OK" }),
    call("VAKEEL", "check_claim", { claim: "G2" }),
    result("VAKEEL", "check_claim", { claim: "G2", supported: false, note: "the cited paragraph does not say the prosecution conceded; rewording" }),
    call("VAKEEL", "check_claim", { claim: "G2", round: 2 }),
    result("VAKEEL", "check_claim", { claim: "G2", supported: true, check: "REPAIRED" }),
    call("VAKEEL", "good_law_check", { store: "caselaw.citations", doc_id: "DLHC-2022-1187" }),
    result("VAKEEL", "good_law_check", { status: "OK", sc_root: "SC-2014-0463" }),
    call("VAKEEL", "check_claim", { claim: "G5" }),
    result("VAKEEL", "check_claim", { claim: "G5", supported: false, check: "NEEDS_REVIEW", note: "authority from a wider section family" }),
    call("VAKEEL", "check_claim", { claim: "G6" }),
    result("VAKEEL", "check_claim", { claim: "G6", supported: false, check: "NEEDS_REVIEW", note: "antecedents UNSUPPORTED" }),
    call("VAKEEL", "render_citation", { doc_ids: ["DLHC-2022-1187", "SC-2014-0463", "DLHC-2023-0412", "SC-2012-0040", "SC-2022-0577", "DLHC-2021-0388", "PHHC-2023-1120", "DLHC-2020-0733"] }),
    write("VAKEEL", "assemble_application", { store: "case.views", view: "brief" }, { grounds: 7, needs_review: ["G5", "G6"], repaired: ["G2"] }, "brief"),
    say("VAKEEL", "Drafted 7 grounds: 4 supported, 1 repaired, 2 need review. Nothing was dropped.", { status: "done" }),

    say("ABHIYOJAK", "Round 1: reading the grounds, the dossier and the objection bank only", { phase: "round1" }, 500),
    call("ABHIYOJAK", "search_objections", { store: "advocacy.objections", factor: "parity_with_co_accused" }),
    call("ABHIYOJAK", "search_reasoning", { store: "caselaw.reasoning", outcome: "rejected", factor: "witness_tampering" }),
    call("ABHIYOJAK", "get_statute", { store: "law.statutes", code: "BNS", section: "318(4)" }),
    call("ABHIYOJAK", "get_fact", { store: "case.facts", field: "trial_stage" }),
    say("ABHIYOJAK", "Raised 3 objections (O1 vs G1, O2 general, O3 vs G4); discarded 1 ungrounded objection (flight risk).", { round: 1 }),
    call("VAKEEL", "check_claim", { claim: "reply:O1" }),
    call("VAKEEL", "check_claim", { claim: "reply:O3" }),
    say("ABHIYOJAK", "Round 2 verdicts: O1 ANSWERED, O3 PARTLY, O2 UNANSWERED (goes to counsel as NEEDS_REVIEW).", { round: 2 }),
    write("ABHIYOJAK", "file_item", { store: "case.views", view: "sparring" }, { objections: 3, unanswered: ["O2"] }, "spar"),
    call("VAKEEL", "similar_orders", { store: "caselaw.similar", want: "conditions in similar grants" }),
    write("VAKEEL", "assemble_application", { store: "case.views", view: "hearing_card" }, { concerns: 4, lead_points: 3, conditions: 5 }, "prep"),
    { kind: "GATE_OPENED", actor: "VAKEEL", tool: "request_approval", inputs: { gate: "GATE_2_EXPORT" }, outputs: { gate: "GATE_2_EXPORT", unresolved_needs_review: ["G5", "G6"], unresolved_unanswered: ["O2"] }, effect: "gate2Opened" },
    say("VAKEEL", "Draft ready for counsel: resolve 2 NEEDS_REVIEW grounds and 1 UNANSWERED objection before Gate 2.", { status: "done" }),
  ];
}

/* ── Plan §7.4, §10: the clock change set (custody grew), only G3 redrafted ─────────────────────────────────────── */

export function clockChangeScript(): ScriptStep[] {
  const changeSet = { case_id: MOCK_CASE_ID, trigger: "clock", fields: [{ field: "custody_days", old_hash: "h:61d0", new_hash: "h:a7c1" }], new_event_ids: [], rights_changed: [] };
  return [
    call("PESHKAR", "date_calc", { rule: "custody_days", end: "2025-02-03" }, 600),
    result("PESHKAR", "diff_case_state", { change_set: changeSet, summary: "custody_days 160 → 167" }),
    { kind: "CHANGE_SET_APPROVED", actor: "counsel", inputs: { change_set: changeSet }, outputs: { fields: ["custody_days"] } },
    { kind: "CLAIM_STALED", actor: "SUTRADHAR", inputs: { claim: "G3" }, outputs: { claim_ids: ["G3"], reason: "custody_days changed (clock)" } },
    say("SUTRADHAR", "Change set: 1 claim stale (G3). Re-planning custody_period only; 6 grounds unchanged."),
    call("VAKEEL", "check_claim", { claim: "G3" }),
    result("VAKEEL", "check_claim", { claim: "G3", supported: true }),
    write("VAKEEL", "assemble_application", { store: "case.views", view: "brief" }, { redrafted: ["G3"], unchanged: 6 }),
    say("VAKEEL", "Redrafted G3 (custody now 167 days); the other grounds stayed word for word.", { status: "done" }),
  ];
}

/* ── Flow 4: the custody certificate arrives; antecedents become VERIFIED; Gate 1 reopens for re-approval ───────── */

export function certificateScript(file = "custody_certificate.pdf"): ScriptStep[] {
  const changeSet = { case_id: MOCK_CASE_ID, trigger: "new_document", fields: [{ field: "antecedents", old_hash: "h:0000", new_hash: "h:5b19" }], new_event_ids: [], rights_changed: ["undertrial_limit"] };
  return [
    { kind: "USER_ACTION", actor: "counsel", inputs: { action: "upload", files: [file] }, delay: 100 },
    say("MUNSHI", `Reading ${file}: 1 page`, { phase: "survey" }, 300),
    call("MUNSHI", "inspect_page", { page: 1 }),
    call("MUNSHI", "clean_image", { page: 1, ops: ["deskew"] }),
    call("MUNSHI", "ocr_page", { page: 1, lang: "en" }),
    result("MUNSHI", "ocr_page", { page: 1, engine: "surya-en", mean_conf: 0.86, badge: "OCR" }),
    call("MUNSHI", "parse_layout", { page: 1 }),
    result("MUNSHI", "parse_layout", { page: 1, tables: 1, badge: "LAYOUT" }),
    call("MUNSHI", "classify_document", { doc_ids: ["d7"] }),
    result("MUNSHI", "classify_document", { d7: "CUSTODY_CERTIFICATE", sensitive: false }),
    call("MUNSHI", "pseudonymise", { doc_id: "d7" }),
    write("MUNSHI", "file_item", { store: "case.docs" }, { chunks: 3 }),
    write("MUNSHI", "file_item", { store: "case.facts" }, { personal: 1 }),
    write("MUNSHI", "file_item", { store: "case.views", view: "ingestion_report" }, { documents: 1 }, "certificateIngested"),
    say("MUNSHI", "Filed d7 (custody certificate). The custody-certificate gap is closed.", { status: "done" }),
    say("PESHKAR", "Re-extracting only the fields d7 touches: antecedents, custody_days", { phase: "change" }, 500),
    call("PESHKAR", "extract_dossier", { store: "case.facts", fields: ["antecedents", "custody_days"] }),
    call("PESHKAR", "span_check", { field: "antecedents", quote: "Involvement in other cases: Nil." }),
    result("PESHKAR", "span_check", { field: "antecedents", supported: true, score: 0.93 }),
    result("PESHKAR", "diff_case_state", { change_set: changeSet, summary: "antecedents: UNSUPPORTED → VERIFIED" }),
    write("PESHKAR", "extract_dossier", { store: "case.facts", field: "antecedents" }, { status: "VERIFIED" }, "certificateDossier"),
    call("PESHKAR", "rights_check", { checks: ["undertrial_limit"] }),
    result("PESHKAR", "rights_check", { undertrial_limit: "NOT_YET", detail: "first-time offender: s.479 one-third date 20.12.2026" }),
    write("PESHKAR", "rights_check", { store: "case.views", view: "rights_report" }, { changed: ["undertrial_limit"] }, "certificateRights"),
    { kind: "GATE_OPENED", actor: "PESHKAR", tool: "request_approval", inputs: { gate: "GATE_1_DOSSIER" }, outputs: { gate: "GATE_1_DOSSIER", changed: ["antecedents"], change_set: changeSet } },
    say("PESHKAR", "1 field changed (antecedents, now verified). Re-approve the dossier to redraft only the affected grounds.", { status: "done" }),
  ];
}

/** After counsel re-approves a change set: stale claims are redrafted, the rest stay word for word (plan §10). */
export function redraftScript(changedFields: string[], staleGrounds: string[], unchanged: number): ScriptStep[] {
  return [
    { kind: "CHANGE_SET_APPROVED", actor: "counsel", inputs: { fields: changedFields }, outputs: { fields: changedFields }, delay: 200 },
    { kind: "CLAIM_STALED", actor: "SUTRADHAR", inputs: {}, outputs: { claim_ids: staleGrounds, reason: `${changedFields.join(", ")} changed` } },
    say("SUTRADHAR", `Change set: ${staleGrounds.length} claim(s) stale (${staleGrounds.join(", ") || "none"}). Re-planning only the affected factors; ${unchanged} grounds unchanged.`),
    call("SUTRADHAR", "get_fact", { store: "case.facts", field: changedFields[0] ?? "" }),
    call("SUTRADHAR", "search_reasoning", { store: "caselaw.reasoning", factor: "antecedents" }),
    ...staleGrounds.flatMap((g) => [call("VAKEEL", "check_claim", { claim: g }), result("VAKEEL", "check_claim", { claim: g, supported: true })]),
    write("VAKEEL", "assemble_application", { store: "case.views", view: "brief" }, { redrafted: staleGrounds, unchanged }, "redraft"),
    call("ABHIYOJAK", "search_objections", { store: "advocacy.objections", factor: "antecedents", only_changed: staleGrounds }),
    write("ABHIYOJAK", "file_item", { store: "case.views", view: "sparring" }, { re_sparred: staleGrounds }),
    { kind: "GATE_OPENED", actor: "VAKEEL", tool: "request_approval", inputs: { gate: "GATE_2_EXPORT" }, outputs: { gate: "GATE_2_EXPORT" } },
    say("VAKEEL", `Redrafted ${staleGrounds.join(", ") || "nothing"}; ${unchanged} grounds stayed word for word.`, { status: "done" }),
  ];
}

/** Sutradhar routes a chat question (plan §6.4): one TOOL_CALL per chip, then the answer. */
export function chatScript(chips: { tool: string; store?: string | null }[], agent: Actor, refused: boolean): ScriptStep[] {
  if (refused) return [say("SUTRADHAR", "Refused: outcome predictions and lay advice are out of scope.", { status: "done", refused: true }, 200)];
  return [
    ...chips.map((c, i) => call(c.tool === "date_calc" || c.tool === "rights_check" ? "PESHKAR" : "SUTRADHAR", c.tool, { store: c.store ?? undefined, from: "chat" }, i === 0 ? 150 : 250)),
    say(agent, "Answered in chat", { status: "done" }, 250),
  ];
}

/* ── Materialise a script into events (used for the seeded history) ─────────────────────────────────────────────── */

/** Turn steps into events with deterministic ids (`evt-<case>-<tag>-<n>`) and timestamps `spacingMs` apart. */
export function materialize(caseId: string, steps: ScriptStep[], startIso: string, spacingMs = 6000, tag = "h"): AgentEvent[] {
  const start = new Date(startIso).getTime();
  const short = caseId.replace(/[^0-9a-z]/gi, "");
  return steps.map((s, i) => ({
    event_id: `evt-${short}-${tag}-${String(i + 1).padStart(3, "0")}`,
    case_id: caseId,
    ts: new Date(start + i * spacingMs).toISOString(),
    kind: s.kind,
    actor: s.actor,
    tool: s.tool ?? null,
    inputs: s.inputs ?? {},
    outputs: s.outputs ?? {},
    sources: s.sources ?? [],
    parent_id: null,
  }));
}

/** case-0007's full record so far: intake, counsel's Gate 1, drafting and sparring, then the clock change set. */
export function buildCase0007History(caseId: string = MOCK_CASE_ID): AgentEvent[] {
  const gate1: ScriptStep[] = [
    { kind: "USER_ACTION", actor: "counsel", inputs: { action: "state_field", field: "personal", value: ["sole earning member"], chat: "turn 3" } },
    { kind: "GATE_APPROVED", actor: "counsel", inputs: { gate: "GATE_1_DOSSIER", acknowledged: ["antecedents"] }, outputs: { gate: "GATE_1_DOSSIER", dossier_hash: "h:8c3e" } },
  ];
  return [
    ...materialize(caseId, intakeScript(), "2025-01-27T04:30:00Z", 4000, "intake"),
    ...materialize(caseId, gate1, "2025-01-27T06:10:00Z", 60000, "gate1"),
    ...materialize(caseId, draftScript(), "2025-01-27T06:20:00Z", 5000, "draft"),
    ...materialize(caseId, clockChangeScript(), "2025-02-03T03:30:00Z", 8000, "clock"),
  ];
}

/** The scripted sequence the live trace replays for case-0007 (exported for tests and the trace drawer's legend). */
export const MOCK_EVENT_SCRIPT: AgentEvent[] = buildCase0007History();
