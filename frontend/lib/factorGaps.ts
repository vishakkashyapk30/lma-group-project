// Dossier gaps by bail factor, and the type of each brief sentence. Pure functions over the case data, so the steps and tests
// read the same answer.
//
// FACTOR_FIELDS mirrors src/vakeel_sahayak/agents/vakeel/facts.py FACTOR_FIELDS (the dossier facts the drafter reads for each
// factor); tests/unit/factorGaps.test.ts fails when the two differ. Sentence types follow the marker rule of the M6a metric
// (eval/scoring/split_metric.py classify): an [A:] marker is a legal principle, an [F:] marker alone a case fact, neither is
// not in the record. No model is involved.
import type { CaseDossier, DossierFieldName, Factor, FieldStatus } from "./types";
import { FACTORS } from "./types";

export const FACTOR_FIELDS: Record<Factor, readonly DossierFieldName[]> = {
  gravity_and_punishment: ["sections", "fir"],
  custody_period: ["custody_days", "arrest_date", "first_remand", "sections"],
  charge_sheet_filed: ["charge_sheet", "custody_days", "sections"],
  trial_delay: ["trial_stage", "charge_sheet", "custody_days"],
  parity_with_co_accused: ["co_accused_bail", "sections"],
  antecedents: ["antecedents"],
  flight_risk: ["personal"],
  witness_tampering: ["trial_stage", "charge_sheet"],
  weak_prima_facie: ["fir", "sections", "offence_date"],
  health_age_family: ["personal"],
  statutory_bar: ["sections"],
  undertrial_period: ["custody_days", "arrest_date", "sections"],
};

/** How much of what a factor needs the file gives: none of its facts, some, or all. */
export type Coverage = "none" | "partial" | "full";

export interface FactorGap {
  factor: Factor;
  coverage: Coverage;
  /** Facts the factor reads that the papers do not give (not found, or empty). */
  missing: DossierFieldName[];
  /** Facts the documents disagree on. */
  unclear: DossierFieldName[];
  /** Facts that are present (from the documents, calculated or entered by counsel). */
  present: DossierFieldName[];
}

function isEmpty(value: unknown): boolean {
  return value === null || value === undefined || value === "" || (Array.isArray(value) && value.length === 0);
}

/** Whether a dossier field counts as missing for a factor: not found, or found with no value. */
export function isMissing(field: { value: unknown; status: FieldStatus } | null | undefined): boolean {
  return !field || field.status === "UNSUPPORTED" || isEmpty(field.value);
}

/** One row per bail factor, in the plan's factor order. A factor whose facts are all missing has coverage "none". */
export function factorGaps(dossier: CaseDossier | null | undefined): FactorGap[] {
  if (!dossier) return [];
  return FACTORS.map((factor) => {
    const missing: DossierFieldName[] = [];
    const unclear: DossierFieldName[] = [];
    const present: DossierFieldName[] = [];
    for (const name of FACTOR_FIELDS[factor]) {
      const field = dossier.fields?.[name];
      if (isMissing(field)) missing.push(name);
      else if (field?.status === "AMBIGUOUS") unclear.push(name);
      else present.push(name);
    }
    const total = FACTOR_FIELDS[factor].length;
    const coverage: Coverage = missing.length === total ? "none" : missing.length > 0 ? "partial" : "full";
    return { factor, coverage, missing, unclear, present };
  });
}

/* ── Sentence types ──────────────────────────────────────────────────────────────────────────────────────────────── */

export type SentenceKind = "case_fact" | "legal" | "not_in_record" | "absence" | "note";

export interface BriefSentence {
  /** The sentence with its markers, as written. */
  text: string;
  kind: SentenceKind;
  /** Dossier fields it cites ([F:field]). */
  facts: string[];
  /** Authorities it cites ([A:doc#para]). */
  authorities: Array<{ doc_id: string; para: number | null }>;
}

const MARKER = /\[\s*(F|A)\s*:\s*([^\]]+)\]/g;
const NOTE_PREFIXES = ["Qualification:", "Warning:"];
// agents/vakeel/agent.ABSENCE: a sentence that only says the record is silent.
const ABSENCE = new RegExp(
  String.raw`\b(?:record|file|papers|documents?|dossier|facts?|material|application)\s+(?:does|do|did|is|are|has|have)\s+(?:not|no|silent)\b` +
    String.raw`|\bno\s+(?:facts?|material|information|details?|record|evidence)\s+(?:is|are|was|were)?\s*(?:about|on|regarding|of|stated|available|on record|recorded|provided)\b` +
    String.raw`|\b(?:not|nowhere)\s+(?:been\s+)?(?:stated|established|disclosed|mentioned|specified|recorded)\b|\bsilent\s+on\b|\bnothing\s+(?:is\s+)?(?:stated|recorded|on record|shown)\b` +
    String.raw`|\bunknown\b|\bcannot\s+be\s+(?:determined|assessed)\b`,
  "i",
);

// pipelines/text_utils.split_sentences: split after . ! ? before a capital, digit, quote or bracket, except after abbreviations.
const SENTENCE_END = /(?<=[.!?])\s+(?=["'(\[]?[A-Z0-9])/g;
const ABBREVIATIONS = /\b(?:Mr|Mrs|Ms|Dr|Shri|Smt|Sh|Hon|Addl|Adv|Co|Ltd|No|Nos|Sec|Secs|Art|Cr|P|S|U|Vs|v|Ors|Anr|St|Jr|Sr|Dy)\.$/i;

/** Sentences of a ground's argument, split as the backend splits them. */
export function splitSentences(text: string): string[] {
  const out: string[] = [];
  let start = 0;
  for (const m of text.matchAll(SENTENCE_END)) {
    const at = m.index ?? 0;
    const head = text.slice(start, at).trimEnd();
    if (ABBREVIATIONS.test(head) || /\b[A-Z]\.$/.test(head)) continue;
    out.push(text.slice(start, at).trim());
    start = at + m[0].length;
  }
  out.push(text.slice(start).trim());
  return out.filter(Boolean);
}

/** The type of one sentence, read from its markers. */
export function classifySentence(sentence: string): SentenceKind {
  if (NOTE_PREFIXES.some((p) => sentence.trimStart().startsWith(p))) return "note";
  const kinds = new Set([...sentence.matchAll(MARKER)].map((m) => m[1]));
  if (kinds.has("A")) return "legal";
  if (kinds.has("F")) return ABSENCE.test(sentence.replace(MARKER, "")) ? "absence" : "case_fact";
  return "not_in_record";
}

/** Each sentence of an argument with its type and what it cites. */
export function briefSentences(argument: string): BriefSentence[] {
  return splitSentences(argument).map((text) => {
    const facts: string[] = [];
    const authorities: BriefSentence["authorities"] = [];
    for (const m of text.matchAll(MARKER)) {
      const body = m[2].trim();
      if (m[1] === "F") {
        if (!facts.includes(body)) facts.push(body);
      } else {
        const [doc, para] = body.split("#");
        const p = para ? Number(para) : null;
        if (!authorities.some((a) => a.doc_id === doc.trim() && a.para === p)) authorities.push({ doc_id: doc.trim(), para: p });
      }
    }
    return { text, kind: classifySentence(text), facts, authorities };
  });
}

/** Plain words for each type, as the step shows them. */
export const SENTENCE_KIND_LABELS: Record<SentenceKind, string> = {
  case_fact: "Case fact",
  legal: "Legal principle",
  not_in_record: "Not in the record",
  absence: "Says the record is silent",
  note: "Note",
};
