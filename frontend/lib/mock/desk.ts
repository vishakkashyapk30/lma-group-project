// Demo data for the batch desk (plan §11): about twelve TriageCards in urgency order. The urgency rule is fixed and
// explainable: legal deadlines first, then days past a threshold, then custody length; ties go to cases with no
// missing documents. A statutory bar moves a case down. No bulk export: every case needs its own approval.
import type { DeskBoard, TriageCard } from "../types";

export const MOCK_TRIAGE_CARDS: TriageCard[] = [
  {
    case_id: "case-0118",
    urgency_rank: 1,
    reasons: ["Default-bail window open now: day 63 of 60 from first remand, no charge sheet on record (BNSS s.187(3))"],
    flags: ["ELIGIBLE: default bail window open", "CHECK: confirm no charge sheet filed since the last order"],
    missing_docs: [],
    next_step: "flag default-bail window to counsel now; full brief queued",
  },
  {
    case_id: "case-0127",
    urgency_rank: 2,
    reasons: ["BNSS s.479 threshold crossed 41 days ago (one-half of the 7-year maximum)"],
    flags: ["ELIGIBLE: s.479 undertrial limit crossed", "OK: 24-hour production"],
    missing_docs: [],
    next_step: "flag s.479 entitlement to counsel; full brief queued",
  },
  {
    case_id: "case-0109",
    urgency_rank: 3,
    reasons: ["Default-bail window opens in 2 days (BNSS s.187(3))"],
    flags: ["NOT_YET: default bail in 2 days", "UNKNOWN: grounds of arrest"],
    missing_docs: [],
    next_step: "full brief queued; flag default-bail window to counsel",
  },
  {
    case_id: "case-0142",
    urgency_rank: 4,
    reasons: ["Default-bail window opens in 3 days (BNSS s.187(3))"],
    flags: ["CHECK: antecedents unknown"],
    missing_docs: ["custody certificate"],
    next_step: "full brief queued; flag default-bail window to counsel",
  },
  {
    case_id: "case-0131",
    urgency_rank: 5,
    reasons: ["BNSS s.479 one-third threshold (first-time offender) in 19 days"],
    flags: ["NOT_YET: s.479 in 19 days", "CHECK: first-time offender status"],
    missing_docs: [],
    next_step: "full brief queued",
  },
  {
    case_id: "case-0104",
    urgency_rank: 6,
    reasons: ["412 days in custody; trial not begun"],
    flags: ["FLAG: grounds of arrest not recorded", "CHECK: Antil category A or D"],
    missing_docs: [],
    next_step: "full brief queued; flag grounds-of-arrest lapse to counsel",
  },
  {
    case_id: "case-0150",
    urgency_rank: 7,
    reasons: ["298 days in custody"],
    flags: ["UNKNOWN: notice of appearance"],
    missing_docs: ["remand orders"],
    next_step: "ask for documents first: remand orders",
  },
  {
    case_id: "case-0113",
    urgency_rank: 8,
    reasons: ["240 days in custody; charges framed, two witnesses examined"],
    flags: ["OK: 24-hour production"],
    missing_docs: [],
    next_step: "full brief queued",
  },
  {
    case_id: "case-0122",
    urgency_rank: 9,
    reasons: ["190 days in custody"],
    flags: ["CHECK: FIR page 2 unreadable"],
    missing_docs: ["clearer copy of FIR page 2"],
    next_step: "ask for a clearer FIR copy first",
  },
  {
    case_id: "case-0137",
    urgency_rank: 10,
    reasons: ["96 days in custody; charge sheet filed"],
    flags: [],
    missing_docs: [],
    next_step: "full brief queued",
  },
  {
    case_id: "case-0146",
    urgency_rank: 11,
    reasons: ["Statutory bar applies (NDPS s.37): moved down; 130 days in custody"],
    flags: ["BAR_APPLIES: NDPS s.37 twin conditions"],
    missing_docs: [],
    next_step: "flag for counsel: twin conditions apply; no full run tonight",
  },
  {
    case_id: "case-0101",
    urgency_rank: 12,
    reasons: ["41 days in custody; charge sheet filed"],
    flags: [],
    missing_docs: ["custody certificate"],
    next_step: "full brief queued (low urgency)",
  },
];

export const MOCK_DESK_BOARD: DeskBoard = { cards: MOCK_TRIAGE_CARDS };

/** Files declined at intake (plan §16: sexual-offence, POCSO and juvenile matters), shown so nothing is silently lost. */
export const MOCK_DESK_DECLINED: { case_id: string; reason: string }[] = [
  { case_id: "case-0133", reason: "Declined at intake: POCSO matter (POCSO s.23 protects the child's identity). Nothing was filed." },
];

/** Batch progress shown while the board is being built (Pairokar's cause-list bars). */
export const MOCK_DESK_PROGRESS = {
  uploaded: 120,
  triaged: 120,
  full_runs_queued: 9,
  full_runs_done: 0,
  declined: 1,
  /** Shared retrieval cache (plan §11 stage 2): reported, not a grant rate. */
  cache_key: "factor · section family · before-date month · query",
};

/** Short titles for desk cases (pseudonymised). */
export const MOCK_DESK_TITLES: Record<string, string> = {
  "case-0118": "State v. Accused-21 · BNS 303(2) theft",
  "case-0127": "State v. Accused-22 · BNS 318(4) cheating",
  "case-0109": "State v. Accused-23 · BNS 316(2) breach of trust",
  "case-0142": "State v. Accused-24 · BNS 318(4) cheating",
  "case-0131": "State v. Accused-25 · BNS 305 theft in a dwelling",
  "case-0104": "State v. Accused-26 · BNS 318(4), 61(2)",
  "case-0150": "State v. Accused-27 · BNS 303(2) theft",
  "case-0113": "State v. Accused-28 · BNS 316(2) breach of trust",
  "case-0122": "State v. Accused-29 · BNS 318(4) cheating (Hindi FIR)",
  "case-0137": "State v. Accused-30 · BNS 303(2) theft",
  "case-0146": "State v. Accused-31 · NDPS s.21(c)",
  "case-0101": "State v. Accused-32 · BNS 318(2) cheating",
};
