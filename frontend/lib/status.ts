// Status presentation map (plan §13.2): every status ALWAYS shows an icon and a label with its colour, never colour
// alone. Colours follow the §13.2 table; statuses the table does not list are mapped by meaning (noted per entry).
import type {
  ClaimCheck, ClaimState, FieldStatus, GoodLawStatus, OpenIssueType, PageStatus, RightsCheckResult, RightsStatus,
  SlotStatus, SparringVerdict, TransferFlag, Treatment,
} from "./types";
import { RIGHTS_STATUSES } from "./types";
import { RIGHTS_CHECK_LABELS } from "./labels";

/** Colour family. "ink" is the neutral family for statuses that carry no judgement (NOT_APPLICABLE, LOCKED). */
export type StatusTone = "neem" | "indigo" | "sindoor" | "haldi" | "clay" | "ink";

/** Icon vocabulary; components/common/StatusBadge maps these to lucide icons (and "function"/"letter" to text). */
export type StatusIconName =
  | "check" | "function" | "cross" | "question" | "pencil" | "clock" | "lock" | "dash" | "alert" | "wrench"
  | "half" | "plus" | "refresh" | "letter" | "flag";

export interface StatusMeta {
  tone: StatusTone;
  /** CSS variable of the colour, e.g. "--color-neem". */
  colorVar: string;
  /** The text icon shown beside the label (plan §13.2: ✔ ƒ ✖ ? ✎ and their neighbours). Never the only cue: the label always shows. */
  icon: string;
  /** Semantic icon name (for callers that draw their own icon). */
  iconName: StatusIconName;
  /** Visible label. */
  label: string;
  /** One sentence for tooltips and screen readers. */
  description: string;
}

/** Which family of statuses a value belongs to; disambiguates shared names (OK, UNKNOWN, NEW...). */
export type StatusKind =
  | "field" | "claim" | "verdict" | "rights" | "slot" | "state" | "transfer" | "goodLaw" | "page" | "gate"
  | "openIssue" | "treatment";

/** UI-only gate states shown in the stepper tooltips and the confirm dialog. */
export type GateUiStatus = "LOCKED" | "BLOCKED" | "READY" | "APPROVED";

const COLOR_VAR: Record<StatusTone, string> = {
  neem: "--color-neem",
  indigo: "--color-indigo",
  sindoor: "--color-sindoor",
  haldi: "--color-haldi",
  clay: "--color-clay",
  ink: "--color-ink-soft",
};

const GLYPH: Record<StatusIconName, string> = {
  check: "✔",
  function: "ƒ",
  cross: "✖",
  question: "?",
  pencil: "✎",
  clock: "◷",
  lock: "⊘",
  dash: "–",
  alert: "!",
  wrench: "✓",
  half: "◐",
  plus: "+",
  refresh: "↻",
  letter: "",
  flag: "⚑",
};

function meta(tone: StatusTone, icon: StatusIconName, label: string, description: string, glyph?: string): StatusMeta {
  return { tone, colorVar: COLOR_VAR[tone], icon: glyph ?? GLYPH[icon], iconName: icon, label, description };
}

/** Dossier field statuses (plan §7.1, table §13.2). */
export const FIELD_STATUS_META: Record<FieldStatus, StatusMeta> = {
  VERIFIED: meta("neem", "check", "Confirmed from the documents", "The quoted page supports this value."),
  COMPUTED: meta("indigo", "function", "Calculated", "Worked out from confirmed values."),
  UNSUPPORTED: meta("sindoor", "cross", "Not found", "Not found in the file, or the check failed."),
  AMBIGUOUS: meta("haldi", "question", "Conflicting documents", "The documents disagree, or the section mapping is unclear."),
  USER_STATED: meta("clay", "pencil", "Entered by you", "Typed or dictated by you; no court record behind it."),
  USER_EDITED: meta("clay", "pencil", "Corrected by you", "Corrected by you; no court record behind it."),
};

/** Claim checks (plan §8.1). REPAIRED is not in the §13.2 table: it is supported after rewording, so neem. */
export const CLAIM_CHECK_META: Record<ClaimCheck, StatusMeta> = {
  SUPPORTED: meta("neem", "check", "Supported", "The facts and authorities support the claim."),
  REPAIRED: meta("neem", "wrench", "Reworded to fit the record", "Reworded until the source supports it."),
  NEEDS_REVIEW: meta("haldi", "question", "Needs your review", "The check failed after two repair rounds; you need to review it."),
};

/** Sparring verdicts (plan §9). PARTLY is between answered and unanswered: haldi. */
export const VERDICT_META: Record<SparringVerdict, StatusMeta> = {
  ANSWERED: meta("neem", "check", "Answered", "The reply answers the objection."),
  PARTLY: meta("haldi", "half", "Partly answered", "The reply answers part of the objection."),
  UNANSWERED: meta("sindoor", "cross", "No answer yet", "There is no adequate reply yet; you need to resolve it."),
};

/**
 * Rights Radar statuses (plan §7.3). Outputs are possible entitlements to check, never advice.
 * ELIGIBLE: neem (a possible entitlement); NOT_YET: haldi (a date ahead, keep watching); WINDOW_CLOSED: sindoor (the window
 * has passed; check whether an application was made); NOT_APPLICABLE: clay (neutral); BAR_APPLIES: sindoor; Antil A-D: clay
 * (neutral categories).
 */
export const RIGHTS_STATUS_META: Record<RightsStatus, StatusMeta> = {
  ELIGIBLE: meta("neem", "check", "Possibly open", "A possible entitlement to check now."),
  NOT_YET: meta("haldi", "clock", "Not yet", "The threshold has not been reached; see the date."),
  WINDOW_CLOSED: meta("sindoor", "lock", "Window closed", "The window has passed; check whether an application was made."),
  CHECK: meta("haldi", "question", "Needs your check", "Unsettled law or missing facts; check it."),
  NOT_APPLICABLE: meta("clay", "dash", "Does not apply", "This rule does not apply to the case."),
  FLAG: meta("sindoor", "cross", "Possible lapse", "A possible procedural lapse on the record."),
  OK: meta("neem", "check", "Met", "The record shows this requirement was met."),
  UNKNOWN: meta("haldi", "question", "Not known", "The file does not say."),
  BAR_APPLIES: meta("sindoor", "alert", "Statutory bar applies", "Twin conditions under a special act apply."),
  A: meta("clay", "letter", "Category A", "Antil category A: punishable up to 7 years.", "A"),
  B: meta("clay", "letter", "Category B", "Antil category B: death, life, or more than 7 years.", "B"),
  C: meta("clay", "letter", "Category C", "Antil category C: special acts with strict bail conditions.", "C"),
  D: meta("clay", "letter", "Category D", "Antil category D: economic offences not under special acts.", "D"),
};

/** Retrieval slot assessments (plan §6.2). */
export const SLOT_STATUS_META: Record<SlotStatus, StatusMeta> = {
  FILLED: meta("neem", "check", "Filled", "The slot has enough evidence."),
  WEAK: meta("haldi", "question", "Weak", "Some evidence, below what the contract needs."),
  MISSING: meta("sindoor", "cross", "Missing", "No evidence found within the budget."),
};

/** Truth-maintenance state (plan §10). */
export const CLAIM_STATE_META: Record<ClaimState, StatusMeta> = {
  CURRENT: meta("neem", "check", "Current", "No dependency has changed."),
  STALE: meta("haldi", "refresh", "Being redrafted", "Something it depends on changed; this ground is being redrafted."),
};

/** Transfer flags (plan §5.4). */
export const TRANSFER_META: Record<TransferFlag, StatusMeta> = {
  SAME_TEXT: meta("neem", "check", "Same text", "Carried over unchanged; the precedent applies."),
  CHANGED: meta("haldi", "question", "Changed: qualify", "Split, merged or reworded; usable only with a qualification."),
  NEW: meta("indigo", "plus", "New provision", "No IPC equivalent."),
};

/** Good-law flags (plan §5.3). DISTINGUISHED is shown but does not block. */
export const GOOD_LAW_META: Record<GoodLawStatus, StatusMeta> = {
  OK: meta("neem", "check", "Good law", "Not overruled by a later SC judgment or a larger bench."),
  OVERRULED: meta("sindoor", "cross", "Overruled", "Cannot be cited without a warning."),
  DISTINGUISHED: meta("haldi", "question", "Distinguished", "Distinguished later; shown, does not block."),
  UNKNOWN: meta("haldi", "question", "Treatment unknown", "Labelers did not agree on how later cases treat it."),
};

/** Page status after routing (plan §4.6). */
export const PAGE_STATUS_META: Record<PageStatus, StatusMeta> = {
  OK: meta("neem", "check", "Read", "The page was read."),
  UNREADABLE: meta("sindoor", "cross", "Could not be read", "The page could not be read; a clearer copy is needed."),
};

/** Gate states for the stepper and the confirm dialog (plan §13.5). */
export const GATE_STATUS_META: Record<GateUiStatus, StatusMeta> = {
  LOCKED: meta("ink", "lock", "Locked", "Opens after the earlier step is confirmed."),
  BLOCKED: meta("sindoor", "cross", "Needs you", "Some items still need you."),
  READY: meta("haldi", "question", "Ready to confirm", "Nothing is outstanding; you can confirm."),
  APPROVED: meta("neem", "check", "Confirmed", "You confirmed this step."),
};

/** Open issues in a brief (plan §8.1). */
export const OPEN_ISSUE_META: Record<OpenIssueType, StatusMeta> = {
  NEEDS_REVIEW: meta("haldi", "question", "Needs your check", "Check this before export."),
  CHANGED_PROVISION: meta("haldi", "question", "Changed provision", "The old and new sections differ: qualify."),
  MISSING_EVIDENCE: meta("sindoor", "cross", "Missing evidence", "Nothing was found for a required point."),
};

/** Citation treatments (plan §5.3). */
export const TREATMENT_META: Record<Treatment, StatusMeta> = {
  FOLLOWED: meta("neem", "check", "Followed", "The citing court followed it."),
  RELIED_ON: meta("neem", "check", "Relied on", "The citing court relied on it."),
  DISTINGUISHED: meta("haldi", "question", "Distinguished", "The citing court distinguished it."),
  OVERRULED: meta("sindoor", "cross", "Overruled", "The citing court overruled it."),
  REFERRED: meta("ink", "dash", "Referred", "Mentioned without a treatment."),
  UNKNOWN: meta("haldi", "question", "Treatment unknown", "Labelers did not agree."),
};

export const STATUS_BY_KIND = {
  field: FIELD_STATUS_META,
  claim: CLAIM_CHECK_META,
  verdict: VERDICT_META,
  rights: RIGHTS_STATUS_META,
  slot: SLOT_STATUS_META,
  state: CLAIM_STATE_META,
  transfer: TRANSFER_META,
  goodLaw: GOOD_LAW_META,
  page: PAGE_STATUS_META,
  gate: GATE_STATUS_META,
  openIssue: OPEN_ISSUE_META,
  treatment: TREATMENT_META,
} as const satisfies Record<StatusKind, Record<string, StatusMeta>>;

/** Lookup order when no kind is given: the first family that defines a name wins (OK -> Rights "OK"). */
const LOOKUP_ORDER: StatusKind[] = [
  "field", "claim", "verdict", "rights", "slot", "state", "transfer", "goodLaw", "openIssue", "gate", "page", "treatment",
];

function flatten(kinds: readonly StatusKind[]): Record<string, StatusMeta> {
  const out: Record<string, StatusMeta> = {};
  for (const kind of kinds) {
    for (const [name, m] of Object.entries(STATUS_BY_KIND[kind] as Record<string, StatusMeta>)) {
      if (!(name in out)) out[name] = m;
    }
  }
  return out;
}

/** Flat map of the plan's status vocabulary (fields, claims, verdicts, rights, claim state, good law); first family wins for shared names. */
export const STATUS_META: Readonly<Record<string, StatusMeta>> = flatten(["field", "claim", "verdict", "rights", "state", "goodLaw"]);

/** Every family, for getStatusMeta without a kind (slots, transfers, gates, pages, issues, treatments included). */
const EVERY_STATUS: Readonly<Record<string, StatusMeta>> = flatten(LOOKUP_ORDER);

/** Every status name the UI knows. */
export const ALL_STATUS_NAMES: readonly string[] = Object.keys(EVERY_STATUS);

/** Presentation for a status; unknown names get a neutral badge with the raw name as label (never colour only). */
export function getStatusMeta(status: string, kind?: StatusKind): StatusMeta {
  const key = status.trim();
  if (kind) {
    const fam = STATUS_BY_KIND[kind] as Record<string, StatusMeta>;
    if (fam[key]) return fam[key];
  }
  return EVERY_STATUS[key] ?? EVERY_STATUS[key.toUpperCase()] ?? meta("ink", "dash", humanizeStatus(key), key);
}

function humanizeStatus(s: string): string {
  const t = s.replace(/_/g, " ").toLowerCase();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

/** Tailwind classes per tone. Text colour meets AA on cream and parchment (see styles/tokens.css). */
export const TONE_CLASSES: Record<StatusTone, { text: string; border: string; bg: string; solid: string; dot: string; ring: string }> = {
  neem: { text: "text-neem", border: "border-neem/50", bg: "bg-neem/[0.07]", solid: "bg-neem text-cream", dot: "bg-neem", ring: "ring-neem" },
  indigo: { text: "text-indigo", border: "border-indigo/45", bg: "bg-indigo/[0.06]", solid: "bg-indigo text-cream", dot: "bg-indigo", ring: "ring-indigo" },
  sindoor: { text: "text-sindoor", border: "border-sindoor/50", bg: "bg-sindoor/[0.06]", solid: "bg-sindoor text-cream", dot: "bg-sindoor", ring: "ring-sindoor" },
  haldi: { text: "text-haldi", border: "border-haldi/50", bg: "bg-haldi/[0.07]", solid: "bg-haldi text-cream", dot: "bg-haldi", ring: "ring-haldi" },
  clay: { text: "text-clay", border: "border-clay/50", bg: "bg-clay/[0.07]", solid: "bg-clay text-cream", dot: "bg-clay", ring: "ring-clay" },
  ink: { text: "text-ink-soft", border: "border-line-strong/60", bg: "bg-ink/[0.03]", solid: "bg-ink-soft text-cream", dot: "bg-ink-soft", ring: "ring-ink-soft" },
};

/* ── Rights Radar chips (cause list: urgent first) ───────────────────────────────────────────────────────────────── */

/** Urgency of a rights status for sorting chips: lower is more urgent (plan §11 urgency rule, §13.5). */
export const RIGHTS_URGENCY: Record<RightsStatus, number> = {
  ELIGIBLE: 0,
  FLAG: 1,
  NOT_YET: 2,
  BAR_APPLIES: 3,
  CHECK: 4,
  UNKNOWN: 5,
  WINDOW_CLOSED: 6,
  D: 7,
  C: 7,
  B: 7,
  A: 7,
  OK: 8,
  NOT_APPLICABLE: 9,
};

export interface ParsedRightsChip {
  status: RightsStatus | null;
  label: string;
  raw: string;
}

const RIGHTS_SET = new Set<string>(RIGHTS_STATUSES);

/** Parse a CaseSummary.rights_chips / TriageCard.flags entry: "STATUS · label" or "STATUS: label". */
export function parseRightsChip(chip: string): ParsedRightsChip {
  const m = /^\s*([A-Z_]+)\s*(?:·|:|-|—)\s*(.+)$/.exec(chip);
  if (m && RIGHTS_SET.has(m[1])) return { status: m[1] as RightsStatus, label: m[2].trim(), raw: chip };
  return { status: null, label: chip.trim(), raw: chip };
}

/** Sort chips most urgent first (unknown statuses last, stable). */
export function sortRightsChips(chips: readonly string[]): ParsedRightsChip[] {
  return chips
    .map(parseRightsChip)
    .map((c, i) => ({ c, i }))
    .sort((a, b) => {
      const ua = a.c.status ? RIGHTS_URGENCY[a.c.status] : 99;
      const ub = b.c.status ? RIGHTS_URGENCY[b.c.status] : 99;
      return ua - ub || a.i - b.i;
    })
    .map(({ c }) => c);
}

/** Build the chip string for a rights check result: "NOT_YET · Default bail: 6 days left". */
export function rightsChipFromCheck(result: RightsCheckResult, detail?: string): string {
  const label = RIGHTS_CHECK_LABELS[result.check];
  return `${result.status} · ${detail ? `${label}: ${detail}` : label}`;
}

/** Parse a RetrievalPlan.assessment value: "WEAK (1 of 2)" -> {status: "WEAK", note: "1 of 2"}. */
export function parseSlotAssessment(value: string): { status: SlotStatus | null; note: string | null } {
  const m = /^\s*(FILLED|WEAK|MISSING)\b\s*(?:\((.*)\))?/.exec(value);
  if (!m) return { status: null, note: value };
  return { status: m[1] as SlotStatus, note: m[2] ?? null };
}

/** Statuses that block a gate until counsel resolves or acknowledges them (plan §13.5). */
export const BLOCKING_STATUSES: ReadonlySet<string> = new Set(["UNSUPPORTED", "NEEDS_REVIEW", "UNANSWERED"]);
