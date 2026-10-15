// Human labels for every enum the UI shows (plan §4, §5, §7, Appendix A). Keep wording short and non-advisory.
import type {
  ConcordanceEdgeType, DocumentType, DossierFieldName, Factor, InputKind, OpenIssueType, OrderPart, ParseRoute,
  RightsCheckName, Treatment,
} from "./types";

/** The 12 bail factors (Appendix A). */
export const FACTOR_LABELS: Record<Factor, string> = {
  gravity_and_punishment: "Gravity and punishment",
  custody_period: "Custody period",
  charge_sheet_filed: "Charge sheet filed / investigation complete",
  trial_delay: "Trial delay",
  parity_with_co_accused: "Parity with co-accused",
  antecedents: "Antecedents",
  flight_risk: "Flight risk",
  witness_tampering: "Witness tampering",
  weak_prima_facie: "Weak prima facie case",
  health_age_family: "Health, age, gender or family circumstances",
  statutory_bar: "Statutory bar (NDPS s.37, UAPA s.43D(5), PMLA s.45)",
  undertrial_period: "BNSS s.479 / CrPC s.436A undertrial period",
};

/** Short factor labels for chips and graph nodes. */
export const FACTOR_SHORT_LABELS: Record<Factor, string> = {
  gravity_and_punishment: "Gravity",
  custody_period: "Custody",
  charge_sheet_filed: "Charge sheet",
  trial_delay: "Trial delay",
  parity_with_co_accused: "Parity",
  antecedents: "Antecedents",
  flight_risk: "Flight risk",
  witness_tampering: "Witnesses",
  weak_prima_facie: "Prima facie",
  health_age_family: "Personal",
  statutory_bar: "Statutory bar",
  undertrial_period: "s.479",
};

export const DOC_TYPE_LABELS: Record<DocumentType, string> = {
  FIR: "FIR",
  ARREST_MEMO: "Arrest memo",
  REMAND_ORDER: "Remand order",
  BAIL_ORDER: "Bail order",
  ORDER_SHEET: "Order sheet",
  CHARGE_SHEET_COVER: "Charge-sheet cover",
  CUSTODY_CERTIFICATE: "Custody certificate",
  MEDICAL_RECORD: "Medical record",
  AFFIDAVIT: "Affidavit",
  OTHER: "Other",
};

export const INPUT_KIND_LABELS: Record<InputKind, string> = {
  K1_BORN_DIGITAL: "Born-digital",
  K2_SCANNED: "Scanned",
  K3_DEGRADED: "Degraded scan",
  K4_PHONE_PHOTO: "Phone photo",
  K5_HINDI_MIXED: "Hindi / mixed script",
  K6_LEGACY_HINDI_FONT: "Legacy Hindi font",
  K7_HANDWRITING: "Handwriting",
  K8_BUNDLE: "Bundle",
  K9_LOCKED_OR_BROKEN: "Locked or broken",
  K10_NOT_PDF: "Not a PDF",
};

/** Route badges on page cards (plan §4.2, §13.4: TEXT, LAYOUT, OCR, VISION). */
export const ROUTE_BADGES: Record<ParseRoute, { badge: string; label: string; step: number }> = {
  text_layer: { badge: "TEXT", label: "Text layer", step: 1 },
  layout: { badge: "LAYOUT", label: "Layout parser", step: 2 },
  ocr: { badge: "OCR", label: "Clean-up + OCR", step: 3 },
  vision: { badge: "VISION", label: "Vision model (transcribe only)", step: 4 },
  ask_counsel: { badge: "ASK", label: "Asked counsel", step: 5 },
};

/**
 * Which ladder rung a PageRoute step string reached, e.g. "ocr: surya-hi" -> "ocr", "text_layer: rejected (legacy font)"
 * -> "text_layer", "dewarp" -> null (a clean-up step, not a rung).
 */
export function routeStepRung(step: string): ParseRoute | null {
  const key = step.split(":")[0].trim().toLowerCase();
  if (key === "text_layer" || key === "text") return "text_layer";
  if (key === "layout" || key === "docling") return "layout";
  if (key === "ocr" || key.startsWith("ocr")) return "ocr";
  if (key === "vision" || key.startsWith("vision")) return "vision";
  if (key === "ask_counsel" || key === "ask") return "ask_counsel";
  return null;
}

/** The highest rung a page climbed to, from its route steps (rejected steps still count as attempted). */
export function finalRung(route: string[]): ParseRoute | null {
  let best: ParseRoute | null = null;
  for (const step of route) {
    const rung = routeStepRung(step);
    if (rung && (!best || ROUTE_BADGES[rung].step > ROUTE_BADGES[best].step)) best = rung;
  }
  return best;
}

export const RIGHTS_CHECK_LABELS: Record<RightsCheckName, string> = {
  default_bail: "Default bail",
  undertrial_limit: "Undertrial limit (s.479)",
  notice_of_appearance: "Notice of appearance",
  grounds_of_arrest: "Grounds of arrest",
  production_24h: "24-hour production",
  antil_category: "Antil category",
  statutory_bar: "Statutory bar",
};

export const DOSSIER_FIELD_LABELS: Record<DossierFieldName, string> = {
  fir: "FIR",
  offence_date: "Offence date",
  sections: "Sections",
  arrest_date: "Arrest",
  first_remand: "First remand",
  custody_days: "Days in custody",
  charge_sheet: "Charge sheet",
  trial_stage: "Trial stage",
  previous_bail: "Earlier bail applications",
  co_accused_bail: "Co-accused bail",
  antecedents: "Antecedents",
  personal: "Personal circumstances",
  parties: "Parties (pseudonymised)",
};

export const OPEN_ISSUE_LABELS: Record<OpenIssueType, string> = {
  NEEDS_REVIEW: "Needs review",
  CHANGED_PROVISION: "Changed provision",
  MISSING_EVIDENCE: "Missing evidence",
};

export const TREATMENT_LABELS: Record<Treatment, string> = {
  FOLLOWED: "Followed",
  RELIED_ON: "Relied on",
  DISTINGUISHED: "Distinguished",
  OVERRULED: "Overruled",
  REFERRED: "Referred",
  UNKNOWN: "Treatment unknown",
};

export const EDGE_TYPE_LABELS: Record<ConcordanceEdgeType, string> = {
  SAME: "Same",
  SPLIT: "Split",
  MERGED: "Merged",
  REWORDED: "Reworded",
  NEW: "New",
};

export const ORDER_PART_LABELS: Record<OrderPart, string> = {
  facts: "Facts",
  defense_submissions: "Defence submissions",
  prosecution_submissions: "Prosecution submissions",
  reasoning: "Reasoning",
  operative_order: "Operative order",
};

/** Language code -> label (documents and quotes). */
export function langLabel(lang: string | null | undefined): string {
  switch ((lang ?? "").toLowerCase()) {
    case "hi":
      return "Hindi";
    case "en":
      return "English";
    case "mixed":
      return "Mixed";
    default:
      return lang ?? "Unknown";
  }
}
