// Demo cause list (plan §13.5 /cases): six cases at different stages, all built from the case-0007 template with
// pseudonyms swapped. case-0007 is the fully worked example; case-0023 plays the intake live when first opened.
import { clone } from "../utils";
import type {
  BailBrief, BudgetState, CaseDossier, CaseSummary, ChatMessage, GroundRevision, HearingPrepCard, IngestionReport,
  RightsReport, SparringRecord, Stage, TimelineEvent,
} from "../types";
import {
  MOCK_BRIEF, MOCK_BRIEF_REVISIONS, MOCK_BUDGET, MOCK_CASE_ID, MOCK_CHAT, MOCK_DOSSIER, MOCK_INGESTION, MOCK_PREP,
  MOCK_RIGHTS, MOCK_SPAR, MOCK_TIMELINE,
} from "./case0007";

/** Everything the demo backend holds for one case. */
export interface CaseTemplate {
  ingestion: IngestionReport;
  dossier: CaseDossier;
  dates: TimelineEvent[];
  rights: RightsReport;
  brief: BailBrief;
  spar: SparringRecord;
  prep: HearingPrepCard;
  chat: ChatMessage[];
  budget: BudgetState;
  revisions: GroundRevision[];
}

export interface Pseudonyms {
  fir: string;
  ps: string;
  accused: string;
}

const BASE_PSEUDONYMS: Pseudonyms = { fir: "112/2024", ps: "PS-1", accused: "Accused-1" };

/** The case-0007 data re-labelled for another case id (and, optionally, other pseudonyms). */
export function buildTemplate(caseId: string, p: Pseudonyms = BASE_PSEUDONYMS): CaseTemplate {
  const base: CaseTemplate = {
    ingestion: MOCK_INGESTION, dossier: MOCK_DOSSIER, dates: MOCK_TIMELINE, rights: MOCK_RIGHTS, brief: MOCK_BRIEF,
    spar: MOCK_SPAR, prep: MOCK_PREP, chat: MOCK_CHAT, budget: MOCK_BUDGET, revisions: MOCK_BRIEF_REVISIONS,
  };
  let json = JSON.stringify(base);
  if (caseId !== MOCK_CASE_ID) json = json.split(MOCK_CASE_ID).join(caseId);
  if (p.fir !== BASE_PSEUDONYMS.fir) json = json.split(BASE_PSEUDONYMS.fir).join(p.fir);
  if (p.ps !== BASE_PSEUDONYMS.ps) json = json.split(`${BASE_PSEUDONYMS.ps}"`).join(`${p.ps}"`).split(`${BASE_PSEUDONYMS.ps},`).join(`${p.ps},`).split(`${BASE_PSEUDONYMS.ps} `).join(`${p.ps} `);
  // "Accused-1" (capital A) never matches inside "Co-accused-1".
  if (p.accused !== BASE_PSEUDONYMS.accused) json = json.split(BASE_PSEUDONYMS.accused).join(p.accused);
  return JSON.parse(json) as CaseTemplate;
}

export type SeedHistory = "none" | "intake" | "gate1" | "draft" | "all" | "exported";

export interface CaseSeed {
  summary: Pick<CaseSummary, "case_id" | "title" | "stage">;
  pseudonyms: Pseudonyms;
  /** Which artefacts exist when the demo starts. */
  has: { ingestion: boolean; dossier: boolean; rights: boolean; brief: boolean; spar: boolean; prep: boolean; chat: boolean };
  approvals: { gate1: boolean; gate2: boolean };
  acknowledged: string[];
  resolved: Record<string, string>;
  history: SeedHistory;
  /** Script that plays the first time the case is opened in the demo. */
  autoScript?: "intake";
  exports?: string[];
  /** Per-case tweaks after the template is built. */
  tweak?: (t: CaseTemplate) => void;
}

const ALL = { ingestion: true, dossier: true, rights: true, brief: true, spar: true, prep: true, chat: true };
const NONE = { ingestion: false, dossier: false, rights: false, brief: false, spar: false, prep: false, chat: false };

const RESOLVED_FOR_GATE2: Record<string, string> = {
  "NEEDS_REVIEW:G5": "Reworded to the record: charges not framed three months after the charge sheet. PHHC-2023-1120 kept as distinguished.",
  "NEEDS_REVIEW:G6": "Instructions confirm no other pending case; will file an affidavit.",
  "NEEDS_REVIEW:issue-0": "Confirmed with the client's family; affidavit to be annexed.",
  "UNANSWERED:O2": "Will offer a no-contact condition and appearance on every date.",
};

export const CASE_SEEDS: CaseSeed[] = [
  {
    summary: { case_id: "case-0007", title: "State v. Accused-1 · FIR 112/2024, PS-1 · BNS 318(4), 316(2)", stage: "SPAR" },
    pseudonyms: BASE_PSEUDONYMS,
    has: ALL,
    approvals: { gate1: true, gate2: false },
    acknowledged: ["UNSUPPORTED:antecedents"],
    resolved: {},
    history: "all",
  },
  {
    summary: { case_id: "case-0012", title: "State v. Accused-3 · FIR 77/2024, PS-4 · BNS 318(4), 316(2)", stage: "DOSSIER" },
    pseudonyms: { fir: "77/2024", ps: "PS-4", accused: "Accused-3" },
    has: { ...NONE, ingestion: true, dossier: true, rights: true },
    approvals: { gate1: false, gate2: false },
    acknowledged: [],
    resolved: {},
    history: "intake",
    tweak: (t) => {
      // Earlier in the case: day 55 from the first remand, no charge sheet yet: the default-bail window is 6 days away.
      t.dossier.as_of = "2024-10-14";
      t.dossier.fields.custody_days = { value: 55, source: { tool: "date_calc" }, status: "COMPUTED" };
      t.dossier.fields.charge_sheet = {
        value: { filed: false, date: null },
        source: { doc: "d3 (remand order)", page: 7, box: [72, 120, 523, 146], lang: "en", route: "ocr: surya-en", quote: "Investigation is stated to be in progress." },
        status: "VERIFIED",
      };
      t.dossier.fields.trial_stage = { value: "investigation pending", source: t.dossier.fields.charge_sheet.source, status: "VERIFIED" };
      t.dossier.fields.co_accused_bail = { value: null, source: null, status: "UNSUPPORTED" };
      t.dates = t.dates.filter((e) => e.date <= "2024-10-14");
      t.ingestion.documents = t.ingestion.documents.filter((d) => ["d1", "d2", "d3", "d4"].includes(d.doc_id));
      t.ingestion.file = "bundle_1.pdf";
      t.rights.as_of = "2024-10-14";
      for (const c of t.rights.checks) {
        if (c.check === "default_bail") {
          c.status = "NOT_YET";
          c.detail = "60-day limit (maximum 7 years). Day 1 is the first remand, 21.08.2024; today is day 55. No charge sheet on record. Default bail may open on day 61 (20.10.2024): 6 days left.";
          c.dates = { first_remand: "2024-08-21", day_61: "2024-10-20", as_of: "2024-10-14" };
        }
        if (c.check === "undertrial_limit") c.detail = "55 days in custody. The threshold is 852 days for a first-time offender (1/3 of 7 years) and 1,278 days otherwise (1/2). Antecedents unknown.";
        if (c.check === "production_24h") {
          c.status = "FLAG";
          c.detail = "Arrested at 09:10 on 20.08.2024; produced at 16:30 on 21.08.2024: about 31 hours (times on record).";
        }
      }
    },
  },
  {
    summary: { case_id: "case-0019", title: "State v. Accused-5 · FIR 203/2024, PS-2 · BNS 318(4), 316(2)", stage: "BRIEF" },
    pseudonyms: { fir: "203/2024", ps: "PS-2", accused: "Accused-5" },
    has: { ...ALL, spar: false, prep: false, chat: false },
    approvals: { gate1: true, gate2: false },
    acknowledged: ["UNSUPPORTED:antecedents"],
    resolved: {},
    history: "gate1",
    tweak: (t) => {
      for (const c of t.rights.checks) {
        if (c.check === "grounds_of_arrest") {
          c.status = "FLAG";
          c.detail = "The remand order records no written grounds of arrest, and the arrest was after the written-grounds rule.";
        }
        if (c.check === "notice_of_appearance") {
          c.status = "FLAG";
          c.detail = "Offence punishable up to 7 years; no notice of appearance and no recorded reasons for arrest in the file.";
        }
      }
    },
  },
  {
    summary: { case_id: "case-0023", title: "New bundle · bundle_1.pdf · 14 pages, Hindi FIR", stage: "INTAKE" },
    pseudonyms: { fir: "112/2024", ps: "PS-1", accused: "Accused-1" },
    has: NONE,
    approvals: { gate1: false, gate2: false },
    acknowledged: [],
    resolved: {},
    history: "none",
    autoScript: "intake",
  },
  {
    summary: { case_id: "case-0031", title: "State v. Accused-8 · FIR 15/2025, PS-7 · BNS 318(4), 316(2)", stage: "HEARING_PREP" },
    pseudonyms: { fir: "15/2025", ps: "PS-7", accused: "Accused-8" },
    has: ALL,
    approvals: { gate1: true, gate2: false },
    acknowledged: ["UNSUPPORTED:antecedents"],
    resolved: RESOLVED_FOR_GATE2,
    history: "all",
  },
  {
    summary: { case_id: "case-0036", title: "State v. Accused-11 · FIR 342/2024, PS-3 · BNS 318(4), 316(2)", stage: "FILE" },
    pseudonyms: { fir: "342/2024", ps: "PS-3", accused: "Accused-11" },
    has: ALL,
    approvals: { gate1: true, gate2: true },
    acknowledged: ["UNSUPPORTED:antecedents"],
    resolved: RESOLVED_FOR_GATE2,
    history: "exported",
    exports: ["exports/case-0036/bail_application.docx", "exports/case-0036/list_of_dates.docx", "exports/case-0036/objections_sheet.docx", "exports/case-0036/hearing_card.pdf"],
  },
];

/** The cause list as first shown (rights chips and attention counts are computed by the demo backend). */
export const MOCK_CASES: CaseSummary[] = CASE_SEEDS.map((s) => ({ ...s.summary, rights_chips: [], needs_attention: 0 }));

/** Template copy for a seed, with its tweaks applied. */
export function templateForSeed(seed: CaseSeed): CaseTemplate {
  const t = buildTemplate(seed.summary.case_id, seed.pseudonyms);
  seed.tweak?.(t);
  return clone(t);
}

/** Progress order used when effects move a case forward. */
export const STAGE_ORDER: Stage[] = ["INTAKE", "DOSSIER", "RIGHTS", "BRIEF", "SPAR", "HEARING_PREP", "FILE"];
