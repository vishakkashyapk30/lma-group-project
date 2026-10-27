// What the landing demos show, taken from the built-in sample case (lib/mock/case0007.ts, State v. Accused-1,
// FIR 112/2024) and the sample batch desk, so the page shows the product's real output and cannot drift from it.
import { MOCK_BRIEF, MOCK_DOSSIER, MOCK_INGESTION, MOCK_RIGHTS, MOCK_SPAR, MOCK_TIMELINE } from "@/lib/mock/case0007";
import { MOCK_DESK_TITLES, MOCK_TRIAGE_CARDS } from "@/lib/mock/desk";
import { MOCK_LIBRARY_RESULTS } from "@/lib/mock/library";
import type { SourceRef } from "@/lib/types";

export const SAMPLE_TITLE = "State v. Accused-1, FIR 112/2024, PS-1";

const f = MOCK_DOSSIER.fields;

/** dd.mm.yyyy, as courts write dates. */
export function courtDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

export interface FactRow {
  key: string;
  label: string;
  value: string | null;
  status: "VERIFIED" | "UNSUPPORTED" | "COMPUTED";
  source: SourceRef | null;
  /** Why it is missing, when it is. */
  note?: string;
}

const fir = f.fir!.value as { number: string; police_station: string; date: string };
const sections = (f.sections!.value as { code: string; section: string }[]).map((s) => `${s.code} ${s.section}`).join(", ");

/** The FIR (document d1, pages 1 to 3), as Munshi reads it. */
export const FIR_DOC = {
  title: "FIR No. 112/2024, PS-1",
  lang: "Hindi",
  pages: MOCK_INGESTION.documents[0]!.page_routes.map((p) => ({ page: p.page, status: p.status, kind: p.kind })),
  question: MOCK_INGESTION.questions[0]!,
};

/** What the FIR alone gives, and what it does not. */
export const FIR_FACTS: FactRow[] = [
  { key: "fir", label: "FIR", value: `${fir.number}, ${fir.police_station}, dated ${courtDate(fir.date)}`, status: "VERIFIED", source: f.fir!.source as SourceRef },
  { key: "offence_date", label: "Date of occurrence", value: courtDate(f.offence_date!.value as string), status: "VERIFIED", source: f.offence_date!.source as SourceRef },
  { key: "sections", label: "Sections", value: sections, status: "VERIFIED", source: f.sections!.source as SourceRef },
  { key: "arrest_date", label: "Date of arrest", value: null, status: "UNSUPPORTED", source: null, note: "Not in the FIR. The remand order gives it." },
  { key: "antecedents", label: "Antecedents", value: null, status: "UNSUPPORTED", source: null, note: "Not in any of the papers." },
];

/** Rows for "open a fact and see the words behind it": every fact read from the Hindi FIR, with its quote. */
export const READ_FACTS = (["fir", "offence_date", "sections", "parties"] as const).map((key) => {
  const field = f[key]!;
  const src = field.source as SourceRef;
  const value =
    key === "fir" ? `${fir.number}, ${fir.police_station}` : key === "offence_date" ? courtDate(field.value as string) : key === "sections" ? sections : (field.value as string[]).join(", ");
  const label = key === "fir" ? "FIR" : key === "offence_date" ? "Date of occurrence" : key === "sections" ? "Sections" : "Parties";
  return { key, label, value, quote: src.quote ?? "", quoteEn: src.quote_en ?? "", page: src.page ?? 1 };
});

/** The dates the rights checks use (MOCK_RIGHTS, MOCK_DOSSIER). */
export const RIGHTS_DATES = {
  arrest: f.arrest_date!.value as string,
  firstRemand: f.first_remand!.value as string,
  chargeSheet: (f.charge_sheet!.value as { date: string }).date,
  asOf: MOCK_RIGHTS.as_of,
  day60: MOCK_RIGHTS.checks.find((c) => c.check === "default_bail")!.dates!.day_60!,
  oneThird: MOCK_RIGHTS.checks.find((c) => c.check === "undertrial_limit")!.dates!.one_third!,
  oneHalf: MOCK_RIGHTS.checks.find((c) => c.check === "undertrial_limit")!.dates!.one_half!,
  nextHearing: MOCK_TIMELINE.find((e) => e.event_id === "e15")!.date,
};

export const DEFAULT_BAIL = MOCK_RIGHTS.checks.find((c) => c.check === "default_bail")!;
export const UNDERTRIAL = MOCK_RIGHTS.checks.find((c) => c.check === "undertrial_limit")!;

/** Two Gate 1 items of the sample case: a fact the papers do not give, and two documents that disagree. */
export const FIR_CONFLICT = {
  fir: MOCK_TIMELINE.find((e) => e.event_id === "e02")!,
  remand: MOCK_TIMELINE.find((e) => e.event_id === "e02b")!,
};

const g1 = MOCK_BRIEF.grounds.find((g) => g.id === "G1")!;
const g5 = MOCK_BRIEF.grounds.find((g) => g.id === "G5")!;
const para = (doc: string) => MOCK_LIBRARY_RESULTS.find((r) => r.doc_id === doc);

/** Turn "[F:x]" and "[A:doc#p]" markers into plain text and numbered authorities. */
function splitArgument(text: string): { text: string; cites: string[] } {
  const cites: string[] = [];
  const out = text
    .replace(/\s*\[F:[^\]]+\]/g, "")
    .replace(/\s*\[A:([^#\]]+)#(\d+)\]/g, (_m, doc: string) => {
      if (!cites.includes(doc)) cites.push(doc);
      return ` [${cites.indexOf(doc) + 1}]`;
    });
  return { text: out, cites };
}

export const GROUNDS = [g1, g5].map((g) => {
  const { text, cites } = splitArgument(g.argument);
  return {
    id: g.id,
    check: g.check,
    text,
    authorities: cites.map((doc) => {
      const a = g.authorities.find((x) => x.doc_id === doc)!;
      const p = para(doc);
      return { doc, citation: a.citation, goodLaw: a.good_law, paragraph: p?.text ?? null, court: p?.court ?? null };
    }),
  };
});

export const OBJECTIONS = MOCK_SPAR.objections.map((o) => ({
  id: o.id,
  against: o.against,
  objection: o.objection,
  verdict: o.verdict,
  reason: o.reason,
  reply: o.reply ? splitArgument(o.reply.text).text : null,
}));

export const DESK_CARDS = MOCK_TRIAGE_CARDS.slice(0, 6).map((c) => ({
  id: c.case_id,
  rank: c.urgency_rank,
  title: MOCK_DESK_TITLES[c.case_id] ?? c.case_id,
  reason: c.reasons[0] ?? "",
  missing: c.missing_docs,
}));
