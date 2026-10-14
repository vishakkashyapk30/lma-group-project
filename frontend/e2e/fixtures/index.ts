// Typed loaders for the JSON fixtures. dossier.json, rights_report.json and timeline.json are copies of
// tests/fixtures/case_0007/*.json (plan §7.3 worked example); the rest are hand-built to match src/vakeel_sahayak/schemas
// and lib/types.ts (guarded by tests/unit/e2eFixtures.test.ts).
import fs from "node:fs";
import path from "node:path";
import type {
  BailBrief, CaseDossier, CaseSummary, ChatMessage, GateStatus, IngestionReport, RightsReport, SparringRecord, TriageCard, AgentEvent,
} from "../../lib/types";

const dir = __dirname;
function load<T>(name: string): T {
  return JSON.parse(fs.readFileSync(path.join(dir, name), "utf8")) as T;
}

export const fx = {
  caseSummary: () => load<CaseSummary>("case_summary.json"),
  dossier: () => load<CaseDossier>("dossier.json"),
  rights: () => load<RightsReport>("rights_report.json"),
  timeline: () => load<Record<string, unknown>[]>("timeline.json"),
  gate1Blocked: () => load<GateStatus>("gate1_blocked.json"),
  gate1Open: () => load<GateStatus>("gate1_open.json"),
  gate2Blocked: () => load<GateStatus>("gate2_blocked.json"),
  gate2Open: () => load<GateStatus>("gate2_open.json"),
  chatMessage: () => load<ChatMessage>("chat_message.json"),
  munshiQuestion: () => load<ChatMessage>("munshi_question.json"),
  triageCards: () => load<TriageCard[]>("triage_cards.json"),
  brief: () => load<BailBrief>("bail_brief.json"),
  spar: () => load<SparringRecord>("sparring_record.json"),
  prep: () => load<Record<string, unknown>>("prep_card.json"),
  ingestionEmpty: () => load<IngestionReport>("ingestion_empty.json"),
  ingestionBundle: () => load<IngestionReport>("ingestion_bundle.json"),
  draftEvents: () => load<AgentEvent[]>("draft_events.json"),
  // flow 4 (the case moves on, plan §13.6): charge sheet not filed -> filed; ch001 = change set, ch002-ch005 = re-approval and redraft of G2 only
  dossierBeforeChange: () => load<CaseDossier>("dossier_before_change.json"),
  dossierAfterChange: () => load<CaseDossier>("dossier_after_change.json"),
  briefBeforeChange: () => load<BailBrief>("bail_brief_before_change.json"),
  briefAfterChange: () => load<BailBrief>("bail_brief_after_change.json"),
  changeEvents: () => load<AgentEvent[]>("change_events.json"),
  // flow 5 (a dictated case): Munshi's read-back, USER_STATED dossier, a brief that says "per counsel, not on record"
  dictationReadback: () => load<{ case_id: string; accepted: string[]; questions: string[] }>("dictation_readback.json"),
  dossierDictated: () => load<CaseDossier>("dossier_dictated.json"),
  briefDictated: () => load<BailBrief>("bail_brief_dictated.json"),
};
