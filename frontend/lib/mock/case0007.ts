// Demo data: the plan's worked example, case-0007 (plan §4.6, §6.3, §7.1-§7.3, §8.1-§8.3, §9, §10).
// Pseudonyms only (Accused-1, Co-accused-1, Complainant-1, IO-1, PS-1). Judgment ids are synthetic corpus ids and
// citations are rendered from (synthetic) corpus metadata, exactly as the system renders them: never a model-written
// case name. Two sections are charged so the brief has both a SAME_TEXT and a CHANGED transfer flag:
// BNS 318(4) carries IPC 420 over unchanged; BNS 316(2) raises IPC 406's maximum from three to five years.
import type {
  BailBrief, BudgetState, CaseDossier, ChatMessage, GroundRevision, HearingPrepCard, IngestionReport, RetrievalPlan,
  RightsReport, SparringRecord, TimelineEvent,
} from "../types";
import { DRAFT_LABEL } from "../types";

export const MOCK_CASE_ID = "case-0007";
export const MOCK_AS_OF = "2025-02-03";
export const MOCK_COURT = "Delhi High Court";

/* ── IngestionReport (plan §4.6) ─────────────────────────────────────────────────────────────────────────────────── */

export const MOCK_INGESTION: IngestionReport = {
  case_id: MOCK_CASE_ID,
  file: "bundle_1.pdf",
  documents: [
    {
      doc_id: "d1",
      type: "FIR",
      pages: [1, 3],
      lang: "hi",
      type_confidence: 0.94,
      page_routes: [
        { page: 1, kind: "scanned", route: ["text_layer: rejected (legacy font)", "ocr: surya-hi"], ocr_conf: 0.81, status: "OK" },
        { page: 2, kind: "scanned, handwriting", route: ["ocr: surya-hi", "vision: qwen3-vl"], ocr_conf: 0.42, status: "OK" },
        { page: 3, kind: "photo", route: ["dewarp", "ocr: surya-hi", "vision: qwen3-vl"], status: "UNREADABLE" },
      ],
    },
    {
      doc_id: "d2",
      type: "REMAND_ORDER",
      pages: [4, 5],
      lang: "en",
      type_confidence: 0.97,
      page_routes: [
        { page: 4, kind: "born-digital", route: ["text_layer"], status: "OK" },
        { page: 5, kind: "born-digital", route: ["text_layer"], status: "OK" },
      ],
    },
    {
      doc_id: "d3",
      type: "REMAND_ORDER",
      pages: [6, 7],
      lang: "en",
      type_confidence: 0.91,
      page_routes: [
        { page: 6, kind: "scanned, skewed", route: ["clean_image: deskew", "ocr: surya-en"], ocr_conf: 0.9, status: "OK" },
        { page: 7, kind: "degraded scan, stamp", route: ["clean_image: denoise", "ocr: surya-en", "vision: qwen3-vl"], ocr_conf: 0.57, status: "OK" },
      ],
    },
    {
      doc_id: "d4",
      type: "BAIL_ORDER",
      pages: [8, 10],
      lang: "en",
      type_confidence: 0.96,
      page_routes: [
        { page: 8, kind: "scanned", route: ["ocr: surya-en"], ocr_conf: 0.92, status: "OK" },
        { page: 9, kind: "scanned", route: ["ocr: surya-en"], ocr_conf: 0.9, status: "OK" },
        { page: 10, kind: "scanned, signature", route: ["ocr: surya-en"], ocr_conf: 0.88, status: "OK" },
      ],
    },
    {
      doc_id: "d5",
      type: "ORDER_SHEET",
      pages: [11, 12],
      lang: "mixed",
      type_confidence: 0.88,
      page_routes: [
        { page: 11, kind: "born-digital, table", route: ["text_layer", "layout: docling"], status: "OK" },
        { page: 12, kind: "born-digital, table", route: ["text_layer", "layout: docling"], status: "OK" },
      ],
    },
    {
      doc_id: "d6",
      type: "BAIL_ORDER",
      pages: [13, 14],
      lang: "en",
      type_confidence: 0.93,
      page_routes: [
        { page: 13, kind: "born-digital", route: ["text_layer"], status: "OK" },
        { page: 14, kind: "born-digital", route: ["text_layer"], status: "OK" },
      ],
    },
  ],
  filed: { timeline_events: 11, parties: 4, sections: 2, chunks: 31 },
  gaps: [
    { item: "charge-sheet status", action: "charge-sheet cover not in the bundle; order sheet p.11 records filing on 02.11.2024; asked counsel for the cover" },
    { item: "custody certificate", action: "searched pages 1-14; not found; asked counsel" },
    { item: "FIR page 3", action: "dewarp, OCR and the vision transcript all failed the check; asked counsel for a clearer copy" },
  ],
  questions: [
    "Page 3 of the FIR is unreadable. Can you upload a clearer copy?",
    "The order sheet records a charge sheet filed on 02.11.2024. Can you upload the charge-sheet cover?",
    "Please upload the jail custody certificate, if you have it.",
  ],
};

/** Display labels for the documents (the dossier's SourceRef.doc uses "d1 (FIR)"). */
export const MOCK_DOC_TITLES: Record<string, string> = {
  d1: "FIR No. 112/2024, PS-1 (Hindi)",
  d2: "Remand order, 21.08.2024",
  d3: "Remand order, 04.09.2024",
  d4: "Sessions Court bail rejection, 30.09.2024",
  d5: "Order sheet, Nov 2024 - Jan 2025",
  d6: "Co-accused-1 bail order, 05.12.2024",
  d7: "Jail custody certificate",
};

/* ── CaseDossier (plan §7.1) ─────────────────────────────────────────────────────────────────────────────────────── */

export const MOCK_DOSSIER: CaseDossier = {
  case_id: MOCK_CASE_ID,
  court: MOCK_COURT,
  as_of: MOCK_AS_OF,
  fields: {
    fir: {
      value: { number: "112/2024", police_station: "PS-1", date: "2024-08-14" },
      source: {
        doc: "d1 (FIR)", page: 1, box: [64, 120, 540, 152], lang: "hi", route: "ocr: surya-hi",
        quote: "प्रथम सूचना रिपोर्ट सं. 112/2024 दिनांक 14.08.2024",
        quote_en: "FIR No. 112/2024 dated 14.08.2024",
      },
      status: "VERIFIED",
    },
    offence_date: {
      value: "2024-08-10",
      source: {
        doc: "d1 (FIR)", page: 1, box: [64, 236, 420, 262], lang: "hi", route: "ocr: surya-hi",
        quote: "घटना की तिथि: 10.08.2024", quote_en: "Date of occurrence: 10.08.2024",
      },
      status: "VERIFIED",
    },
    sections: {
      value: [
        { as_written: "318(4) BNS", code: "BNS", section: "318(4)", equivalent: "IPC 420", bailable: false, max_punishment: "7 years" },
        { as_written: "316(2) BNS", code: "BNS", section: "316(2)", equivalent: "IPC 406", bailable: false, max_punishment: "5 years" },
      ],
      source: {
        doc: "d1 (FIR)", page: 1, box: [64, 196, 531, 222], lang: "hi", route: "ocr: surya-hi",
        quote: "अधिनियम एवं धाराएँ: भारतीय न्याय संहिता, 2023 - धारा 318(4), 316(2)",
        quote_en: "Act and sections: Bharatiya Nyaya Sanhita, 2023 - sections 318(4), 316(2)",
      },
      status: "VERIFIED",
    },
    arrest_date: {
      value: "2024-08-20",
      source: { doc: "d2 (remand order)", page: 4, box: [72, 262, 523, 288], lang: "en", route: "text_layer", quote: "...arrested on 20.08.2024..." },
      status: "VERIFIED",
    },
    first_remand: {
      value: "2024-08-21",
      source: {
        doc: "d2 (remand order)", page: 4, box: [72, 342, 523, 368], lang: "en", route: "text_layer",
        quote: "Remanded to judicial custody for 14 days, to be produced on 04.09.2024.",
      },
      status: "VERIFIED",
    },
    custody_days: { value: 167, source: { tool: "date_calc" }, status: "COMPUTED" },
    charge_sheet: {
      value: { filed: true, date: "2024-11-02" },
      source: {
        doc: "d5 (order sheet)", page: 11, box: [60, 300, 535, 326], lang: "en", route: "layout: docling",
        quote: "02.11.2024: Charge sheet filed by IO-1 under ss. 318(4), 316(2) BNS. Copy supplied.",
      },
      status: "VERIFIED",
    },
    trial_stage: {
      value: "charges not framed",
      source: {
        doc: "d5 (order sheet)", page: 12, box: [60, 180, 535, 206], lang: "en", route: "layout: docling",
        quote: "20.01.2025: Arguments on charge not concluded. Charges not framed. Put up on 18.02.2025.",
      },
      status: "VERIFIED",
    },
    previous_bail: {
      value: [{ court: "Sessions Court", date: "2024-09-30", outcome: "rejected" }],
      source: {
        doc: "d4 (bail order)", page: 10, box: [72, 420, 523, 446], lang: "en", route: "ocr: surya-en",
        quote: "...the bail application of the applicant Accused-1 is dismissed. Pronounced on 30.09.2024.",
      },
      status: "VERIFIED",
    },
    co_accused_bail: {
      value: [{ id: "Co-accused-1", outcome: "granted", date: "2024-12-05" }],
      source: {
        doc: "d6 (bail order)", page: 13, box: [72, 380, 523, 406], lang: "en", route: "text_layer",
        quote: "...Co-accused-1 is admitted to bail on furnishing a personal bond of ₹50,000 with one surety...",
      },
      status: "VERIFIED",
    },
    antecedents: { value: null, source: null, status: "UNSUPPORTED" },
    personal: { value: ["sole earning member"], source: { chat: "turn 3" }, status: "USER_STATED" },
    parties: {
      value: ["Accused-1", "Co-accused-1", "Complainant-1", "IO-1"],
      source: {
        doc: "d1 (FIR)", page: 1, box: [64, 300, 531, 352], lang: "hi", route: "ocr: surya-hi",
        quote: "शिकायतकर्ता: Complainant-1; आरोपीगण: Accused-1, Co-accused-1; विवेचना अधिकारी: IO-1",
        quote_en: "Complainant: Complainant-1; accused: Accused-1, Co-accused-1; investigating officer: IO-1",
      },
      status: "VERIFIED",
    },
  },
  open_questions: ["Does the accused have any other pending cases?"],
};

/* ── List of Dates and Events (plan §7.2) ───────────────────────────────────────────────────────────────────────── */

export const MOCK_TIMELINE: TimelineEvent[] = [
  {
    event_id: "e01", date: "2024-08-10", label: "Alleged offence (date of occurrence as per FIR)", status: "VERIFIED", conflicts_with: [],
    source: { doc: "d1 (FIR)", page: 1, box: [64, 236, 420, 262], lang: "hi", quote: "घटना की तिथि: 10.08.2024", quote_en: "Date of occurrence: 10.08.2024" },
  },
  {
    event_id: "e02", date: "2024-08-14", label: "FIR No. 112/2024 registered at PS-1 under ss. 318(4), 316(2) BNS", status: "VERIFIED", conflicts_with: ["e02b"],
    source: { doc: "d1 (FIR)", page: 1, box: [64, 120, 540, 152], lang: "hi", quote: "प्रथम सूचना रिपोर्ट सं. 112/2024 दिनांक 14.08.2024", quote_en: "FIR No. 112/2024 dated 14.08.2024" },
  },
  {
    event_id: "e02b", date: "2024-08-15", label: "FIR date as recited in the remand order", status: "AMBIGUOUS", conflicts_with: ["e02"],
    source: { doc: "d2 (remand order)", page: 4, box: [72, 150, 523, 176], lang: "en", quote: "State v. Accused-1, FIR No. 112/2024 dated 15.08.2024, PS-1" },
  },
  {
    event_id: "e03", date: "2024-08-20", label: "Accused-1 arrested", status: "VERIFIED", conflicts_with: [],
    source: { doc: "d2 (remand order)", page: 4, box: [72, 262, 523, 288], lang: "en", quote: "...arrested on 20.08.2024..." },
  },
  {
    event_id: "e04", date: "2024-08-21", label: "First remand: produced before the CJM; judicial custody for 14 days", status: "VERIFIED", conflicts_with: [],
    source: { doc: "d2 (remand order)", page: 4, box: [72, 342, 523, 368], lang: "en", quote: "Remanded to judicial custody for 14 days, to be produced on 04.09.2024." },
  },
  {
    event_id: "e05", date: "2024-09-04", label: "Judicial custody extended by 14 days", status: "VERIFIED", conflicts_with: [],
    source: { doc: "d3 (remand order)", page: 6, box: [72, 250, 523, 276], lang: "en", quote: "Judicial custody of the accused extended for 14 days." },
  },
  {
    event_id: "e06", date: "2024-09-12", label: "Bail application filed before the Sessions Court", status: "VERIFIED", conflicts_with: [],
    source: { doc: "d4 (bail order)", page: 8, box: [72, 196, 523, 222], lang: "en", quote: "Bail Application No. 1043/2024, filed on 12.09.2024" },
  },
  {
    event_id: "e07", date: "2024-09-30", label: "Sessions Court rejects bail", status: "VERIFIED", conflicts_with: [],
    source: { doc: "d4 (bail order)", page: 10, box: [72, 420, 523, 446], lang: "en", quote: "...the bail application of the applicant Accused-1 is dismissed. Pronounced on 30.09.2024." },
  },
  {
    event_id: "e08", date: "2024-10-20", label: "Day 61 from first remand: default-bail window opens (60-day limit)", status: "COMPUTED", conflicts_with: [],
    source: { tool: "date_calc" },
  },
  {
    event_id: "e09", date: "2024-11-02", label: "Charge sheet filed under ss. 318(4), 316(2) BNS (day 74)", status: "VERIFIED", conflicts_with: [],
    source: { doc: "d5 (order sheet)", page: 11, box: [60, 300, 535, 326], lang: "en", quote: "02.11.2024: Charge sheet filed by IO-1 under ss. 318(4), 316(2) BNS. Copy supplied." },
  },
  {
    event_id: "e12", date: "2024-12-05", label: "Co-accused-1 granted bail by the Sessions Court", status: "VERIFIED", conflicts_with: [],
    source: { doc: "d6 (bail order)", page: 13, box: [72, 380, 523, 406], lang: "en", quote: "...Co-accused-1 is admitted to bail on furnishing a personal bond of ₹50,000 with one surety..." },
  },
  {
    event_id: "e14", date: "2025-01-20", label: "Arguments on charge not concluded; charges not framed", status: "VERIFIED", conflicts_with: [],
    source: { doc: "d5 (order sheet)", page: 12, box: [60, 180, 535, 206], lang: "en", quote: "20.01.2025: Arguments on charge not concluded. Charges not framed. Put up on 18.02.2025." },
  },
  {
    event_id: "e15", date: "2025-02-18", label: "Next date before the trial court: arguments on charge", status: "VERIFIED", conflicts_with: [],
    source: { doc: "d5 (order sheet)", page: 12, box: [60, 180, 535, 206], lang: "en", quote: "Put up on 18.02.2025." },
  },
];

/* ── RightsReport (plan §7.3, Appendix C) ───────────────────────────────────────────────────────────────────────── */

const RULES_VERIFIED = "2025-01-15";

export const MOCK_RIGHTS: RightsReport = {
  case_id: MOCK_CASE_ID,
  as_of: MOCK_AS_OF,
  checks: [
    {
      check: "default_bail",
      status: "WINDOW_CLOSED",
      detail:
        "60-day limit (maximum 7 years). Day 1 is the first remand, 21.08.2024. The charge sheet was filed on day 74 (02.11.2024). Default bail was available on days 61-73 if an application was made; check whether one was.",
      uses: ["first_remand", "charge_sheet", "sections"],
      rule: "BNSS s.187(3)",
      rule_text:
        "Release if no charge sheet is filed within 90 days (offences punishable with death, life imprisonment, or 10 years or more) or 60 days (other offences). Count from the first remand, with that day as day 1. The right lapses if the charge sheet is filed before an application is made.",
      sources: ["BNSS s.187(3) (CrPC s.167(2))", "ED v. Kapil Wadhawan (2023), on counting", "M. Ravindran v. DRI (2020), on the right lapsing"],
      dates: { first_remand: "2024-08-21", day_60: "2024-10-19", charge_sheet: "2024-11-02" },
      last_verified: RULES_VERIFIED,
    },
    {
      check: "undertrial_limit",
      status: "CHECK",
      detail:
        "167 days in custody. The threshold is 852 days for a first-time offender (1/3 of 7 years) and 1,278 days otherwise (1/2). Antecedents unknown.",
      uses: ["custody_days", "sections", "antecedents"],
      rule: "BNSS s.479",
      rule_text:
        "Release on bond after half the maximum sentence, or one-third for a first-time offender. Does not apply to offences punishable with death or life imprisonment.",
      sources: ["BNSS s.479 (CrPC s.436A)", "In Re Inhuman Conditions in 1382 Prisons (2024): s.479 applies to pending cases"],
      dates: { arrest_date: "2024-08-20", as_of: MOCK_AS_OF, one_third: "2026-12-20", one_half: "2028-02-19" },
      last_verified: RULES_VERIFIED,
    },
    {
      check: "notice_of_appearance",
      status: "UNKNOWN",
      detail: "Offence punishable up to 7 years. No arrest memo or notice in the file.",
      uses: ["sections"],
      rule: "BNSS s.35(3); Arnesh Kumar (2014)",
      rule_text: "For offences punishable up to 7 years, a notice of appearance is the norm, and arrest needs recorded reasons.",
      sources: ["BNSS s.35(3) (CrPC s.41A)", "Arnesh Kumar v. State of Bihar (2014)", "Satender Kumar Antil v. CBI (2022)"],
      dates: { arrest_date: "2024-08-20" },
      last_verified: RULES_VERIFIED,
    },
    {
      check: "grounds_of_arrest",
      status: "UNKNOWN",
      detail: "No record that the grounds of arrest were communicated.",
      uses: ["arrest_date"],
      rule: "Art. 22(1); BNSS s.47; Vihaan Kumar (2025)",
      rule_text:
        "The grounds must be communicated. Since Mihir Rajesh Shah, they must be in writing, in a language the arrested person understands, at least 2 hours before production. Whether this applies to earlier arrests is contested, so it returns CHECK.",
      sources: ["Art. 22(1)", "BNSS s.47 (CrPC s.50)", "Vihaan Kumar v. State of Haryana (2025)", "Mihir Rajesh Shah v. State of Maharashtra (2025)"],
      dates: { arrest_date: "2024-08-20", first_remand: "2024-08-21" },
      last_verified: RULES_VERIFIED,
    },
    {
      check: "production_24h",
      status: "CHECK",
      detail: "Produced the next day; times not on record.",
      uses: ["arrest_date", "first_remand"],
      rule: "Art. 22(2); BNSS s.58",
      rule_text: "The arrested person must be produced before a magistrate within 24 hours of arrest, excluding travel time.",
      sources: ["Art. 22(2)", "BNSS s.58 (CrPC s.57)"],
      dates: { arrest_date: "2024-08-20", first_remand: "2024-08-21" },
      last_verified: RULES_VERIFIED,
    },
    {
      check: "antil_category",
      status: "CHECK",
      detail: "Category A (up to 7 years), unless treated as an economic offence (D).",
      uses: ["sections"],
      rule: "Satender Kumar Antil v. CBI (2022)",
      rule_text:
        "A: punishable up to 7 years (not B or D). B: death, life, or more than 7 years. C: special acts with strict bail conditions. D: economic offences not under special acts.",
      sources: ["Satender Kumar Antil v. CBI (2022)"],
      dates: {},
      last_verified: RULES_VERIFIED,
    },
    {
      check: "statutory_bar",
      status: "NOT_APPLICABLE",
      detail: "No NDPS, UAPA or PMLA section charged.",
      uses: ["sections"],
      rule: "NDPS s.37; UAPA s.43D(5); PMLA s.45",
      rule_text: "The twin conditions apply when a section of these acts is charged.",
      sources: ["NDPS Act s.37", "UAPA s.43D(5)", "PMLA s.45"],
      dates: {},
      last_verified: RULES_VERIFIED,
    },
  ],
};

/* ── RetrievalPlans (plan §6.3) ─────────────────────────────────────────────────────────────────────────────────── */

/** The plan's example, verbatim. */
export const MOCK_RETRIEVAL_PLAN: RetrievalPlan = {
  factor: "parity_with_co_accused",
  round: 1,
  budget_left: { store_calls: 6, tokens: 9000 },
  steps: [
    { slot: "co_accused_order", tool: "search_case_docs", args: { query: "co-accused granted bail", doc_types: ["BAIL_ORDER"] } },
    {
      slot: "authority", tool: "search_reasoning",
      args: { factor: "parity_with_co_accused", section_family: ["BNS 318(4)", "IPC 420"], before: "2025-02-03", outcome: "granted", k: 10 },
    },
    { slot: "good_law", tool: "citations", args: { doc_ids: "$authority.top3", want: ["overruled_by", "sc_root"] } },
    { slot: "likely_objection", tool: "search_objections", args: { factor: "parity_with_co_accused", section_family: ["BNS 318(4)", "IPC 420"] } },
  ],
  assessment: { co_accused_order: "FILLED", authority: "WEAK (1 of 2)", good_law: "FILLED", likely_objection: "FILLED" },
  next: "relax section_family to the offence group 'cheating'; retry authority",
};

export const MOCK_RETRIEVAL_PLANS: RetrievalPlan[] = [
  MOCK_RETRIEVAL_PLAN,
  {
    factor: "parity_with_co_accused",
    round: 2,
    budget_left: { store_calls: 4, tokens: 6100 },
    steps: [
      { slot: "authority", tool: "search_reasoning", args: { factor: "parity_with_co_accused", section_family: ["cheating"], before: "2025-02-03", outcome: "granted", k: 10 } },
      { slot: "good_law", tool: "good_law_check", args: { doc_id: "SC-2014-0463", as_of: "2025-02-03" } },
    ],
    assessment: { co_accused_order: "FILLED", authority: "FILLED", good_law: "FILLED", likely_objection: "FILLED" },
    next: null,
  },
  {
    factor: "charge_sheet_filed",
    round: 1,
    budget_left: { store_calls: 5, tokens: 8400 },
    steps: [
      { slot: "charge_sheet_date", tool: "get_timeline", args: { kinds: ["charge_sheet"] } },
      { slot: "authority", tool: "search_reasoning", args: { factor: "charge_sheet_filed", section_family: ["BNS 318(4)", "IPC 420"], before: "2025-02-03", k: 10 } },
      { slot: "likely_objection", tool: "search_objections", args: { factor: "charge_sheet_filed" } },
    ],
    assessment: { charge_sheet_date: "FILLED", authority: "FILLED", likely_objection: "FILLED" },
    next: null,
  },
  {
    factor: "trial_delay",
    round: 2,
    budget_left: { store_calls: 0, tokens: 2100 },
    steps: [
      { slot: "authority", tool: "search_reasoning", args: { factor: "trial_delay", section_family: ["cheating"], before: "2025-02-03", k: 10 } },
      { slot: "sc_root", tool: "citations", args: { doc_ids: "$authority.top3", want: ["sc_root"] } },
    ],
    assessment: { trial_stage: "FILLED", authority: "WEAK (1 of 1)", sc_root: "MISSING" },
    next: "budget spent: report sc_root as missing; open issue MISSING_EVIDENCE",
  },
];

/* ── BailBrief (plan §8.1) ──────────────────────────────────────────────────────────────────────────────────────── */

export const MOCK_CITATIONS: Record<string, string> = {
  "DLHC-2022-1187": "DLHC-2022-1187, Delhi High Court, 03.06.2022 (Bail Appln. 1187/2022)",
  "SC-2014-0463": "SC-2014-0463, Supreme Court of India, 2014 (Crl. Appeal 463/2014)",
  "DLHC-2023-0412": "DLHC-2023-0412, Delhi High Court, 17.04.2023 (Bail Appln. 412/2023)",
  "SC-2012-0040": "SC-2012-0040, Supreme Court of India, 2012 (Crl. Appeal 40/2012)",
  "SC-2022-0577": "SC-2022-0577, Supreme Court of India, 2022 (MA 577/2022)",
  "DLHC-2021-0388": "DLHC-2021-0388, Delhi High Court, 09.03.2021 (Bail Appln. 388/2021)",
  "PHHC-2023-1120": "PHHC-2023-1120, Punjab and Haryana High Court, 22.08.2023 (CRM-M 1120/2023)",
  "DLHC-2020-0733": "DLHC-2020-0733, Delhi High Court, 14.10.2020 (Bail Appln. 733/2020)",
  "DLHC-2023-0911": "DLHC-2023-0911, Delhi High Court, 11.09.2023 (Bail Appln. 911/2023)",
  "DLHC-2022-0644": "DLHC-2022-0644, Delhi High Court, 28.07.2022 (Bail Appln. 644/2022)",
  "BHC-2024-0871": "BHC-2024-0871, Bombay High Court, 19.11.2024 (BA 871/2024)",
  "DLHC-2019-0310": "DLHC-2019-0310, Delhi High Court, 05.02.2019 (Bail Appln. 310/2019)",
  "SC-2023-0112": "SC-2023-0112, Supreme Court of India, 2023 (Crl. Appeal 112/2023)",
};

const cite = (doc: string, para: number) => `${MOCK_CITATIONS[doc] ?? doc}, ¶${para}`;

export const G3_PREVIOUS_ARGUMENT =
  "The applicant has been in custody for 160 days since his arrest on 20.08.2024 [F:custody_days] [F:arrest_date]. Prolonged pre-trial detention, where the trial has not begun, weighs in favour of bail [A:SC-2012-0040#24].";

export const MOCK_BRIEF: BailBrief = {
  case_id: MOCK_CASE_ID,
  statutory_position: {
    sections: ["BNS 318(4) (≈ IPC 420)", "BNS 316(2) (≈ IPC 406)"],
    bailable: false,
    max_punishment: "7 years",
    rights: "default-bail window closed; s.479 not yet reached (see RightsReport)",
  },
  grounds: [
    {
      id: "G1",
      factor: "parity_with_co_accused",
      stance: "favourable",
      argument:
        "Co-accused-1, with an identical role, was granted bail on 05.12.2024 [F:co_accused_bail]. Both are alleged to have received the money in the same transaction [F:fir], and the charge sheet places them on the same footing [F:charge_sheet]. Where a co-accused with the same role has been enlarged on bail, parity ordinarily applies [A:DLHC-2022-1187#14], following the Supreme Court's reasoning on equal treatment of co-accused [A:SC-2014-0463#9].",
      authorities: [
        { doc_id: "DLHC-2022-1187", para: 14, citation: cite("DLHC-2022-1187", 14), transfer: "SAME_TEXT", good_law: "OK", sc_root: "SC-2014-0463" },
        { doc_id: "SC-2014-0463", para: 9, citation: cite("SC-2014-0463", 9), transfer: null, good_law: "OK", sc_root: null },
      ],
      depends_on: {
        facts: { co_accused_bail: "h:3f2a", sections: "h:91c0", fir: "h:77b1", charge_sheet: "h:2d4e" },
        events: ["e12"], rights: [], authorities: ["DLHC-2022-1187#14", "SC-2014-0463#9"], claims: [],
      },
      check: "SUPPORTED",
      state: "CURRENT",
    },
    {
      id: "G2",
      factor: "charge_sheet_filed",
      stance: "favourable",
      argument:
        "Investigation is complete: the charge sheet was filed on 02.11.2024 [F:charge_sheet]. Once the charge sheet is filed, continued custody serves no investigative purpose [A:DLHC-2023-0412#11].",
      authorities: [
        { doc_id: "DLHC-2023-0412", para: 11, citation: cite("DLHC-2023-0412", 11), transfer: "SAME_TEXT", good_law: "OK", sc_root: "SC-2012-0040" },
      ],
      depends_on: { facts: { charge_sheet: "h:2d4e" }, events: ["e09"], rights: [], authorities: ["DLHC-2023-0412#11"], claims: [] },
      check: "REPAIRED",
      state: "CURRENT",
    },
    {
      id: "G3",
      factor: "custody_period",
      stance: "favourable",
      argument:
        "The applicant has been in custody for 167 days since his arrest on 20.08.2024 [F:custody_days] [F:arrest_date]. Prolonged pre-trial detention, where the trial has not begun, weighs in favour of bail [A:SC-2012-0040#24].",
      authorities: [{ doc_id: "SC-2012-0040", para: 24, citation: cite("SC-2012-0040", 24), transfer: null, good_law: "OK", sc_root: null }],
      depends_on: {
        facts: { custody_days: "h:a7c1", arrest_date: "h:5e02" }, events: ["e03"], rights: ["undertrial_limit"],
        authorities: ["SC-2012-0040#24"], claims: [],
      },
      check: "SUPPORTED",
      state: "CURRENT",
    },
    {
      id: "G4",
      factor: "gravity_and_punishment",
      stance: "favourable",
      argument:
        "The offences under ss. 318(4) and 316(2) BNS carry a maximum of seven and five years [F:sections] and fall in Antil category A, where bail is the norm [A:SC-2022-0577#73]. Earlier rulings on criminal breach of trust under IPC 406 [A:DLHC-2021-0388#9] are relied on with the qualification that BNS 316(2) now prescribes a maximum of five years instead of three.",
      authorities: [
        { doc_id: "SC-2022-0577", para: 73, citation: cite("SC-2022-0577", 73), transfer: null, good_law: "OK", sc_root: null },
        { doc_id: "DLHC-2021-0388", para: 9, citation: cite("DLHC-2021-0388", 9), transfer: "CHANGED", good_law: "OK", sc_root: "SC-2022-0577" },
      ],
      depends_on: {
        facts: { sections: "h:91c0" }, events: [], rights: ["antil_category"],
        authorities: ["SC-2022-0577#73", "DLHC-2021-0388#9"], claims: [],
      },
      check: "SUPPORTED",
      state: "CURRENT",
    },
    {
      id: "G5",
      factor: "trial_delay",
      stance: "favourable",
      argument:
        "Charges are yet to be framed three months after the charge sheet [F:trial_stage] [F:charge_sheet], and the trial is unlikely to conclude soon [A:PHHC-2023-1120#17].",
      authorities: [
        { doc_id: "PHHC-2023-1120", para: 17, citation: cite("PHHC-2023-1120", 17), transfer: "SAME_TEXT", good_law: "DISTINGUISHED", sc_root: null },
      ],
      depends_on: {
        facts: { trial_stage: "h:c410", charge_sheet: "h:2d4e" }, events: ["e09", "e14"], rights: [],
        authorities: ["PHHC-2023-1120#17"], claims: [],
      },
      check: "NEEDS_REVIEW",
      state: "CURRENT",
    },
    {
      id: "G6",
      factor: "antecedents",
      stance: "favourable",
      argument: "Nothing on record shows any other case against the applicant [F:antecedents]; counsel to confirm before this is urged.",
      authorities: [],
      depends_on: { facts: { antecedents: "h:0000" }, events: [], rights: ["undertrial_limit"], authorities: [], claims: [] },
      check: "NEEDS_REVIEW",
      state: "CURRENT",
    },
    {
      id: "G7",
      factor: "health_age_family",
      stance: "favourable",
      argument:
        "The applicant is the sole earning member of his family [F:personal] (per counsel, not on record); family circumstances weigh with the other factors [A:DLHC-2020-0733#8].",
      authorities: [{ doc_id: "DLHC-2020-0733", para: 8, citation: cite("DLHC-2020-0733", 8), transfer: "SAME_TEXT", good_law: "OK", sc_root: null }],
      depends_on: { facts: { personal: "h:e19b" }, events: [], rights: [], authorities: ["DLHC-2020-0733#8"], claims: [] },
      check: "SUPPORTED",
      state: "CURRENT",
    },
  ],
  open_issues: [
    { type: "NEEDS_REVIEW", item: "Antecedents unknown: confirm no other pending cases." },
    { type: "CHANGED_PROVISION", item: "DLHC-2021-0388 interprets IPC 406; BNS 316(2) raises the maximum from three to five years: qualify." },
    { type: "MISSING_EVIDENCE", item: "No trial-delay authority in the same section family; widened to all cheating offences." },
  ],
  label: DRAFT_LABEL,
};

/** Change highlights for the Brief tab (plan §10): the clock change set redrafted G3 only. */
export const MOCK_BRIEF_REVISIONS: GroundRevision[] = [
  {
    ground_id: "G3",
    reason: "Clock change set: custody grew from 160 to 167 days. Only this ground was redrafted; the other six stayed word for word.",
    changed: ["custody_days"],
    previous_argument: G3_PREVIOUS_ARGUMENT,
    at: "2025-02-03T09:12:00+05:30",
  },
];

/* ── SparringRecord (plan §9): one ANSWERED, one PARTLY, one UNANSWERED ────────────────────────────────────────── */

export const MOCK_SPAR: SparringRecord = {
  case_id: MOCK_CASE_ID,
  rounds: 2,
  objections: [
    {
      id: "O1",
      against: "G1",
      factor: "parity_with_co_accused",
      objection: "The applicant, unlike Co-accused-1, received the money into his own account.",
      grounds: [{ store: "advocacy.objections", doc_id: "DLHC-2023-0911", para: 6 }, { fact: "fir" }],
      reply: {
        text:
          "The FIR names Co-accused-1 as receiving part of the same amount [F:fir], and the charge sheet attributes the same role to both [F:charge_sheet]. Receipt into one's own account did not displace parity on similar facts [A:DLHC-2022-1187#14].",
        authorities: [{ doc_id: "DLHC-2022-1187", para: 14, citation: cite("DLHC-2022-1187", 14), transfer: "SAME_TEXT", good_law: "OK", sc_root: "SC-2014-0463" }],
        check: "SUPPORTED",
      },
      verdict: "ANSWERED",
      reason: "The reply meets the distinction with the charge-sheet recital and a parity authority on similar facts.",
    },
    {
      id: "O2",
      against: "general",
      factor: "witness_tampering",
      objection: "Charges are not framed and the complainant is yet to be examined.",
      grounds: [{ fact: "trial_stage" }],
      reply: null,
      verdict: "UNANSWERED",
      reason: "No reply drafted: nothing on record addresses the risk before the complainant is examined. Counsel may offer a no-contact condition.",
    },
    {
      id: "O3",
      against: "G4",
      factor: "gravity_and_punishment",
      objection: "The amount involved makes this an economic offence (Antil category D), where a stricter view is taken.",
      grounds: [{ store: "advocacy.objections", doc_id: "DLHC-2022-0644", para: 4 }, { store: "law.statutes", doc_id: "BNS 318(4)" }],
      reply: {
        text:
          "The FIR alleges a single transaction with one complainant [F:fir]; the Rights Radar treats the category as A unless the offence is an economic offence, which is for the court to assess [A:SC-2022-0577#73].",
        authorities: [{ doc_id: "SC-2022-0577", para: 73, citation: cite("SC-2022-0577", 73), transfer: null, good_law: "OK", sc_root: null }],
        check: "SUPPORTED",
      },
      verdict: "PARTLY",
      reason: "Answers the scale of the transaction but not the economic-offence characterisation itself.",
    },
  ],
  discarded: ["Flight risk: no objection-bank paragraph, statute or dossier fact supports it (logged, not raised)."],
};

/* ── Hearing-prep card (plan §8.3): no outcome prediction, no grant rates ───────────────────────────────────────── */

export const MOCK_PREP: HearingPrepCard = {
  case_id: MOCK_CASE_ID,
  hearing_date: "2025-02-07",
  likely_concerns: [
    {
      concern: "Is the applicant's role different from Co-accused-1's?",
      factor: "parity_with_co_accused",
      basis: "Discussed in comparable refusals (caselaw.similar: DLHC-2023-0911, DLHC-2022-0644) and raised by Abhiyojak (O1).",
      answer: "Same role per the charge sheet; lead with G1 and the reply to O1.",
      ground_id: "G1",
      authority: "DLHC-2022-1187 ¶14",
      sources: ["DLHC-2023-0911", "DLHC-2022-0644"],
    },
    {
      concern: "Will the applicant influence the complainant before examination?",
      factor: "witness_tampering",
      basis: "Discussed in reasoning paragraphs from the same section family (BNS 318(4) / IPC 420) where charges were not framed.",
      answer: "Offer a no-contact condition and appearance on every date. O2 is still unanswered: resolve it before the hearing.",
      ground_id: null,
      authority: null,
      sources: ["DLHC-2023-0911"],
    },
    {
      concern: "Is this an economic offence (Antil category D)?",
      factor: "gravity_and_punishment",
      basis: "Raised in comparable orders on cheating with entrustment of money (caselaw.similar).",
      answer: "Single transaction, one complainant; category A unless treated as economic (Rights Radar: CHECK). See G4.",
      ground_id: "G4",
      authority: "SC-2022-0577 ¶73",
      sources: ["DLHC-2022-0644"],
    },
    {
      concern: "Does the applicant have antecedents?",
      factor: "antecedents",
      basis: "Courts in the same section family usually ask before granting bail.",
      answer: "Not on record. Confirm before the hearing (open issue); the custody certificate would settle it.",
      ground_id: "G6",
      authority: null,
      sources: [],
    },
  ],
  lead_points: [
    { ground_id: "G1", point: "Parity: Co-accused-1, with the same role, has been on bail since 05.12.2024." },
    { ground_id: "G2", point: "Investigation complete: charge sheet filed on 02.11.2024." },
    { ground_id: "G3", point: "167 days in custody; charges not yet framed." },
  ],
  conditions: [
    { condition: "Personal bond with one surety of the like amount", seen_in: ["DLHC-2022-1187", "DLHC-2023-0412", "BHC-2024-0871"] },
    { condition: "No contact with the complainant or prosecution witnesses", seen_in: ["DLHC-2022-1187", "DLHC-2020-0733"] },
    { condition: "Appear on every date of hearing", seen_in: ["DLHC-2023-0412", "BHC-2024-0871"] },
    { condition: "Not to leave Delhi without the court's permission", seen_in: ["DLHC-2022-1187"] },
    { condition: "Surrender of passport, if any", seen_in: ["DLHC-2020-0733"] },
  ],
  open_issues: [
    "Antecedents unknown: confirm no other pending cases.",
    "O2 (witness tampering) is unanswered.",
    "Default bail: check whether an application was made on days 61-73.",
  ],
  label: DRAFT_LABEL,
};

/* ── Chat history (plan §6.4): tool/store chips on every answer and one refusal ─────────────────────────────────── */

export const MOCK_CHAT: ChatMessage[] = [
  { message_id: "m01", case_id: MOCK_CASE_ID, role: "counsel", agent: null, text: "Days in custody?", chips: [], refused: false },
  {
    message_id: "m02", case_id: MOCK_CASE_ID, role: "agent", agent: "PESHKAR",
    text: "Custody: 167 days [date_calc from arrest 20.08.2024]; s.479 not yet reached (852 days for a first-time offender, 1,278 otherwise).",
    chips: [{ tool: "date_calc", store: "case.timeline" }, { tool: "rights_check", store: null }], refused: false,
  },
  { message_id: "m03", case_id: MOCK_CASE_ID, role: "counsel", agent: null, text: "BNS equivalent of 420 IPC?", chips: [], refused: false },
  {
    message_id: "m04", case_id: MOCK_CASE_ID, role: "agent", agent: "SUTRADHAR",
    text: "IPC 420 → BNS 318(4), carried over with the same text (maximum 7 years, non-bailable). Precedents under IPC 420 apply without qualification.",
    chips: [{ tool: "map_section", store: "law.concordance" }, { tool: "transfer_check", store: "law.concordance" }], refused: false,
  },
  { message_id: "m05", case_id: MOCK_CASE_ID, role: "counsel", agent: null, text: "He is the sole earning member of his family.", chips: [], refused: false },
  {
    message_id: "m06", case_id: MOCK_CASE_ID, role: "agent", agent: "MUNSHI",
    text: "Noted as stated by counsel, not on record: personal circumstances → “sole earning member” (USER_STATED, chat turn 3). The brief will label it “per counsel”.",
    chips: [{ tool: "file_item", store: "case.facts" }], refused: false,
  },
  { message_id: "m07", case_id: MOCK_CASE_ID, role: "counsel", agent: null, text: "Any SC case on parity in a cheating case?", chips: [], refused: false },
  {
    message_id: "m08", case_id: MOCK_CASE_ID, role: "agent", agent: "SUTRADHAR",
    text: "Parity → case ▸ precedents ▸ citations ▸ objections. DLHC-2022-1187 ¶14 (IPC 420, granted on parity) rests on SC-2014-0463 ¶9; both are good law. Expect the objection that the applicant's role differs (DLHC-2023-0911 ¶6).",
    chips: [
      { tool: "search_case_docs", store: "case.docs" }, { tool: "search_reasoning", store: "caselaw.reasoning" },
      { tool: "citations", store: "caselaw.citations" }, { tool: "search_objections", store: "advocacy.objections" },
    ],
    refused: false,
  },
  { message_id: "m09", case_id: MOCK_CASE_ID, role: "counsel", agent: null, text: "What are his chances of getting bail?", chips: [], refused: false },
  {
    message_id: "m10", case_id: MOCK_CASE_ID, role: "agent", agent: "SUTRADHAR",
    text: "I can't predict outcomes or give grant rates. I can show the grounds with their sources, the likely objections and the hearing-prep card.",
    chips: [], refused: true,
  },
  { message_id: "m11", case_id: MOCK_CASE_ID, role: "counsel", agent: null, text: "What did the Sessions Court say about antecedents?", chips: [], refused: false },
  {
    message_id: "m12", case_id: MOCK_CASE_ID, role: "agent", agent: "SUTRADHAR",
    text: "The Sessions Court order of 30.09.2024 (d4, p.10) does not mention antecedents. It rejected bail on the seriousness of the allegations and because investigation was at a nascent stage.",
    chips: [{ tool: "search_case_docs", store: "case.docs" }], refused: false,
  },
];

/* ── Budget (plan §6.2) ─────────────────────────────────────────────────────────────────────────────────────────── */

export const MOCK_BUDGET: BudgetState = {
  tokens_spent: 61840,
  tokens_cap: 150000,
  store_calls: {
    "case.docs": 9, "case.timeline": 6, "case.facts": 7, "law.statutes": 4, "law.concordance": 3,
    "caselaw.reasoning": 12, "caselaw.citations": 6, "caselaw.similar": 3, "advocacy.arguments": 2, "advocacy.objections": 5,
  },
};

/* ── Flow 4 (plan §13.6): the custody certificate arrives and settles antecedents ───────────────────────────────── */

export const CUSTODY_CERTIFICATE_DOC = {
  doc_id: "d7",
  type: "CUSTODY_CERTIFICATE" as const,
  pages: [1, 1],
  lang: "en",
  type_confidence: 0.95,
  page_routes: [{ page: 1, kind: "scanned, table", route: ["clean_image: deskew", "ocr: surya-en", "layout: docling"], ocr_conf: 0.86, status: "OK" as const }],
};

export const ANTECEDENTS_FROM_CERTIFICATE = {
  value: ["No other case pending (jail custody certificate)"],
  source: {
    doc: "d7 (custody certificate)", page: 1, box: [60, 330, 535, 356] as [number, number, number, number], lang: "en", route: "layout: docling",
    quote: "Involvement in other cases: Nil.",
  },
  status: "VERIFIED" as const,
};

export const G6_AFTER_CERTIFICATE =
  "The jail custody certificate records no other case against the applicant [F:antecedents]; he is a first-time offender, and the absence of antecedents weighs in favour of bail [A:DLHC-2020-0733#8].";
