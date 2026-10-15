// Demo data for the precedent explorer (plan §5.2-§5.4, §13.5 /library). Synthetic corpus ids and pseudonymised,
// synthetic paragraph text; citations are rendered from metadata. Statute text is the bare-act wording.
import { diffWords, toUnifiedDiff } from "../diff";
import type { BridgeData, CitationEdge, CitationGraphData, CitationNode, LibrarySearchHit } from "../types";
import { MOCK_CITATIONS } from "./case0007";

const FAMILY_420 = ["IPC 420", "BNS 318(4)"];
const FAMILY_406 = ["IPC 406", "BNS 316(2)"];

export const MOCK_LIBRARY_RESULTS: LibrarySearchHit[] = [
  {
    doc_id: "DLHC-2022-1187", para: 14, court: "Delhi HC", date: "2022-06-03", outcome: "granted", part: "reasoning",
    sections: ["IPC 420", "IPC 406"], section_family: [...FAMILY_420, ...FAMILY_406],
    factors: ["parity_with_co_accused", "charge_sheet_filed"], cites: ["SC-2014-0463"], authority: 0.71,
    text: "The co-accused, whose role as described in the charge sheet is identical, has already been enlarged on bail. The applicant cannot be treated differently merely because a part of the amount was credited to his account, when the allegation against both is of the same transaction. Parity is attracted.",
    good_law: "OK", citation: `${MOCK_CITATIONS["DLHC-2022-1187"]}, ¶14`, transfer: "SAME_TEXT",
  },
  {
    doc_id: "SC-2014-0463", para: 9, court: "Supreme Court", date: "2014-07-02", outcome: "granted", part: "reasoning",
    sections: ["IPC 420", "IPC 120B"], section_family: [...FAMILY_420, "IPC 120B", "BNS 61(2)"],
    factors: ["parity_with_co_accused", "gravity_and_punishment"], cites: [], authority: 0.93,
    text: "Where the case against two accused rests on the same evidence and their roles are not shown to be different, the grant of bail to one is a relevant consideration for the other. Consistency in the exercise of discretion is part of fairness to the accused.",
    good_law: "OK", citation: `${MOCK_CITATIONS["SC-2014-0463"]}, ¶9`, transfer: "SAME_TEXT",
  },
  {
    doc_id: "DLHC-2023-0412", para: 11, court: "Delhi HC", date: "2023-04-17", outcome: "granted", part: "reasoning",
    sections: ["IPC 420"], section_family: FAMILY_420,
    factors: ["charge_sheet_filed", "custody_period"], cites: ["SC-2012-0040"], authority: 0.64,
    text: "The investigation is complete and the charge sheet has been filed. The evidence is documentary and already in the custody of the prosecution. No purpose would be served by keeping the applicant in custody.",
    good_law: "OK", citation: `${MOCK_CITATIONS["DLHC-2023-0412"]}, ¶11`, transfer: "SAME_TEXT",
  },
  {
    doc_id: "SC-2012-0040", para: 24, court: "Supreme Court", date: "2012-01-05", outcome: "granted", part: "reasoning",
    sections: ["IPC 420", "IPC 120B"], section_family: FAMILY_420,
    factors: ["custody_period", "trial_delay", "gravity_and_punishment"], cites: [], authority: 0.95,
    text: "The object of bail is to secure the appearance of the accused at the trial. Detention before conviction is not meant to be punitive, and the seriousness of the charge is one consideration among others, not the only one.",
    good_law: "OK", citation: `${MOCK_CITATIONS["SC-2012-0040"]}, ¶24`, transfer: null,
  },
  {
    doc_id: "SC-2022-0577", para: 73, court: "Supreme Court", date: "2022-07-11", outcome: null, part: "reasoning",
    sections: [], section_family: [],
    factors: ["gravity_and_punishment", "antecedents"], cites: ["SC-2012-0040"], authority: 0.97,
    text: "Offences are placed in categories for the purpose of bail. For offences punishable with imprisonment of seven years or less, which do not fall in the other categories, the normal rule is bail, subject to conditions.",
    good_law: "OK", citation: `${MOCK_CITATIONS["SC-2022-0577"]}, ¶73`, transfer: null,
  },
  {
    doc_id: "DLHC-2021-0388", para: 9, court: "Delhi HC", date: "2021-03-09", outcome: "granted", part: "reasoning",
    sections: ["IPC 406", "IPC 420"], section_family: [...FAMILY_406, ...FAMILY_420],
    factors: ["gravity_and_punishment"], cites: ["SC-2012-0040"], authority: 0.52,
    text: "The offence under section 406 IPC is punishable with imprisonment up to three years. The applicant has been in custody for a substantial part of that period, which weighs in favour of bail.",
    good_law: "OK", citation: `${MOCK_CITATIONS["DLHC-2021-0388"]}, ¶9`, transfer: "CHANGED",
  },
  {
    doc_id: "PHHC-2023-1120", para: 17, court: "Punjab & Haryana HC", date: "2023-08-22", outcome: "granted", part: "reasoning",
    sections: ["IPC 420", "IPC 467"], section_family: [...FAMILY_420, "IPC 467", "BNS 338"],
    factors: ["trial_delay", "custody_period"], cites: ["SC-2012-0040"], authority: 0.48,
    text: "Charges are yet to be framed and the prosecution has cited forty witnesses. The trial is not likely to conclude in the near future, and the right to a speedy trial under Article 21 must weigh.",
    good_law: "DISTINGUISHED", citation: `${MOCK_CITATIONS["PHHC-2023-1120"]}, ¶17`, transfer: "SAME_TEXT",
  },
  {
    doc_id: "BHC-2024-0871", para: 21, court: "Bombay HC", date: "2024-11-19", outcome: "granted", part: "reasoning",
    sections: ["BNS 318(4)"], section_family: FAMILY_420,
    factors: ["parity_with_co_accused", "charge_sheet_filed"], cites: ["DLHC-2022-1187", "SC-2014-0463"], authority: 0.58,
    text: "Section 318(4) of the BNS reproduces section 420 of the IPC. The principles governing bail under the earlier provision therefore apply. The co-accused stands on the same footing and has been released.",
    good_law: "OK", citation: `${MOCK_CITATIONS["BHC-2024-0871"]}, ¶21`, transfer: "SAME_TEXT",
  },
  {
    doc_id: "DLHC-2019-0310", para: 12, court: "Delhi HC", date: "2019-02-05", outcome: "rejected", part: "reasoning",
    sections: ["IPC 420"], section_family: FAMILY_420,
    factors: ["gravity_and_punishment"], cites: [], authority: 0.31,
    text: "In offences of cheating involving public money, the gravity of the offence alone is sufficient to decline bail at this stage.",
    good_law: "OVERRULED", citation: `${MOCK_CITATIONS["DLHC-2019-0310"]}, ¶12`, transfer: "SAME_TEXT",
  },
  {
    doc_id: "DLHC-2023-0911", para: 6, court: "Delhi HC", date: "2023-09-11", outcome: "rejected", part: "prosecution_submissions",
    sections: ["IPC 420"], section_family: FAMILY_420,
    factors: ["parity_with_co_accused", "witness_tampering"], cites: [], authority: 0.4,
    text: "The learned APP submits that the applicant, unlike the co-accused, received the money in his own account and is the main beneficiary; the complainant is yet to be examined.",
    good_law: "OK", citation: `${MOCK_CITATIONS["DLHC-2023-0911"]}, ¶6`, transfer: "SAME_TEXT",
  },
];

const node = (doc_id: string, court: string, court_level: string, date: string, good_law: CitationNode["good_law"], authority: number, extra?: Partial<CitationNode>): CitationNode => ({
  doc_id, citation: MOCK_CITATIONS[doc_id] ?? doc_id, court, court_level, date, good_law, authority, ...extra,
});

const NODES: CitationNode[] = [
  node("DLHC-2022-1187", "Delhi HC", "HC", "2022-06-03", "OK", 0.71, { sc_root: "SC-2014-0463", outcome: "granted" }),
  node("SC-2014-0463", "Supreme Court", "SC", "2014-07-02", "OK", 0.93, { outcome: "granted" }),
  node("SC-2012-0040", "Supreme Court", "SC", "2012-01-05", "OK", 0.95, { outcome: "granted" }),
  node("DLHC-2019-0310", "Delhi HC", "HC", "2019-02-05", "OVERRULED", 0.31, { overruled_by: "SC-2023-0112", outcome: "rejected" }),
  node("SC-2023-0112", "Supreme Court", "SC", "2023-03-14", "OK", 0.88, { outcome: "granted" }),
  node("DLHC-2023-0911", "Delhi HC", "HC", "2023-09-11", "OK", 0.4, { outcome: "rejected" }),
  node("BHC-2024-0871", "Bombay HC", "HC", "2024-11-19", "OK", 0.58, { sc_root: "SC-2014-0463", outcome: "granted" }),
  node("PHHC-2023-1120", "Punjab & Haryana HC", "HC", "2023-08-22", "DISTINGUISHED", 0.48, { sc_root: "SC-2012-0040", outcome: "granted" }),
  node("DLHC-2023-0412", "Delhi HC", "HC", "2023-04-17", "OK", 0.64, { sc_root: "SC-2012-0040", outcome: "granted" }),
];

const EDGES: CitationEdge[] = [
  { citing_doc_id: "DLHC-2022-1187", cited_doc_id: "SC-2014-0463", treatment: "FOLLOWED", court_level: "SC", sentence: "...the principle laid down in SC-2014-0463 is followed..." },
  { citing_doc_id: "DLHC-2022-1187", cited_doc_id: "SC-2012-0040", treatment: "RELIED_ON", court_level: "SC", sentence: "Reliance is placed on SC-2012-0040." },
  { citing_doc_id: "DLHC-2022-1187", cited_doc_id: "DLHC-2019-0310", treatment: "DISTINGUISHED", court_level: "HC", sentence: "DLHC-2019-0310 is distinguishable on facts." },
  { citing_doc_id: "SC-2023-0112", cited_doc_id: "DLHC-2019-0310", treatment: "OVERRULED", court_level: "SC", sentence: "The view taken in DLHC-2019-0310 is overruled." },
  { citing_doc_id: "DLHC-2023-0911", cited_doc_id: "DLHC-2022-1187", treatment: "DISTINGUISHED", court_level: "HC", sentence: "DLHC-2022-1187 does not help the applicant, whose role is different." },
  { citing_doc_id: "BHC-2024-0871", cited_doc_id: "DLHC-2022-1187", treatment: "FOLLOWED", court_level: "HC", sentence: "We respectfully agree with DLHC-2022-1187." },
  { citing_doc_id: "BHC-2024-0871", cited_doc_id: "SC-2014-0463", treatment: "RELIED_ON", court_level: "SC", sentence: null },
  { citing_doc_id: "PHHC-2023-1120", cited_doc_id: "DLHC-2022-1187", treatment: "REFERRED", court_level: "HC", sentence: null },
  { citing_doc_id: "DLHC-2023-0412", cited_doc_id: "SC-2012-0040", treatment: "FOLLOWED", court_level: "SC", sentence: null },
];

/** The citation graph around DLHC-2022-1187 (the parity authority of G1). */
export const MOCK_CITATION_GRAPH: CitationGraphData = { root: "DLHC-2022-1187", nodes: NODES, edges: EDGES };

/** Citation graph around any demo judgment: the node, its neighbours and the edges between them. */
export function mockCitationGraphFor(docId: string): CitationGraphData | null {
  if (!NODES.some((n) => n.doc_id === docId)) return null;
  const ids = new Set<string>([docId]);
  for (const e of EDGES) {
    if (e.citing_doc_id === docId) ids.add(e.cited_doc_id);
    if (e.cited_doc_id === docId) ids.add(e.citing_doc_id);
  }
  // Keep the second ring small: add edges among the chosen nodes only.
  return {
    root: docId,
    nodes: NODES.filter((n) => ids.has(n.doc_id)),
    edges: EDGES.filter((e) => ids.has(e.citing_doc_id) && ids.has(e.cited_doc_id)),
  };
}

/* ── The recodification bridge (plan §5.4) ──────────────────────────────────────────────────────────────────────── */

const IPC_420 =
  "Whoever cheats and thereby dishonestly induces the person deceived to deliver any property to any person, or to make, alter or destroy the whole or any part of a valuable security, or anything which is signed or sealed, and which is capable of being converted into a valuable security, shall be punished with imprisonment of either description for a term which may extend to seven years, and shall also be liable to fine.";
const BNS_318_4 =
  "Whoever cheats and thereby dishonestly induces the person deceived to deliver any property to any person, or to make, alter or destroy the whole or any part of a valuable security, or anything which is signed or sealed, and which is capable of being converted into a valuable security, shall be punished with imprisonment of either description for a term which may extend to seven years, and shall also be liable to fine.";
const IPC_406 =
  "Whoever commits criminal breach of trust shall be punished with imprisonment of either description for a term which may extend to three years, or with fine, or with both.";
const BNS_316_2 =
  "Whoever commits criminal breach of trust shall be punished with imprisonment of either description for a term which may extend to five years, or with fine, or with both.";

function bridge(b: Omit<BridgeData, "diff" | "text_diff">): BridgeData {
  const diff = diffWords(b.old_text, b.new_text);
  return { ...b, diff, text_diff: toUnifiedDiff(b.old_ref, b.new_ref, diff) };
}

/** IPC 420 ↔ BNS 318(4): carried over word for word (SAME_TEXT). */
export const MOCK_BRIDGE: BridgeData = bridge({
  query: "IPC 420",
  old_ref: "IPC 420",
  new_ref: "BNS 318(4)",
  edge_type: "SAME",
  flag: "SAME_TEXT",
  old_heading: "Cheating and dishonestly inducing delivery of property.",
  new_heading: "Cheating.",
  old_text: IPC_420,
  new_text: BNS_318_4,
  old_max_punishment: "7 years and fine",
  new_max_punishment: "7 years and fine",
  qualification: null,
  related: [
    { old_ref: "IPC 415", new_ref: "BNS 318(1)", type: "SAME", text_diff: null },
    { old_ref: "IPC 417", new_ref: "BNS 318(2)", type: "REWORDED", text_diff: "- one year\n+ three years" },
    { old_ref: "IPC 418", new_ref: "BNS 318(3)", type: "REWORDED", text_diff: "- three years\n+ five years" },
  ],
});

/** IPC 406 ↔ BNS 316(2): the maximum rises from three to five years (CHANGED). */
export const MOCK_BRIDGE_406: BridgeData = bridge({
  query: "IPC 406",
  old_ref: "IPC 406",
  new_ref: "BNS 316(2)",
  edge_type: "REWORDED",
  flag: "CHANGED",
  old_heading: "Punishment for criminal breach of trust.",
  new_heading: "Criminal breach of trust.",
  old_text: IPC_406,
  new_text: BNS_316_2,
  old_max_punishment: "3 years, or fine, or both",
  new_max_punishment: "5 years, or fine, or both",
  qualification: "Precedents under IPC 406 were decided when the maximum was three years; BNS 316(2) prescribes five. State the qualification when relying on them.",
  related: [{ old_ref: "IPC 405", new_ref: "BNS 316(1)", type: "SAME", text_diff: null }],
});

export const MOCK_BRIDGES: BridgeData[] = [MOCK_BRIDGE, MOCK_BRIDGE_406];

function normSection(s: string): string {
  return s.replace(/\s+/g, "").toLowerCase();
}

/** Bridge for a code and section in either direction ("IPC","420" or "BNS","318(4)"); null when not in the demo. */
export function mockBridgeFor(code: string, section: string): BridgeData | null {
  const ref = `${code.toUpperCase()} ${normSection(section)}`;
  for (const b of MOCK_BRIDGES) {
    const [oc, os] = b.old_ref.split(" ");
    const [nc, ns] = b.new_ref.split(" ");
    if (ref === `${oc} ${normSection(os)}` || ref === `${nc} ${normSection(ns)}`) return { ...b, query: `${code.toUpperCase()} ${section}` };
  }
  return null;
}

/** Demo search: rank paragraphs by query-term overlap with text, sections and factors; all of them for an empty query. */
export function mockSearchLibrary(q: string): LibrarySearchHit[] {
  const terms = q.toLowerCase().split(/[\s,]+/).filter((t) => t.length > 1);
  if (terms.length === 0) return [...MOCK_LIBRARY_RESULTS].sort((a, b) => b.authority - a.authority);
  const scored = MOCK_LIBRARY_RESULTS.map((hit) => {
    const hay = [hit.text, hit.court, hit.doc_id, ...hit.sections, ...hit.section_family, ...hit.factors.map((f) => f.replace(/_/g, " "))]
      .join(" ")
      .toLowerCase();
    const score = terms.reduce((s, t) => s + (hay.includes(t) ? 1 : 0), 0);
    return { hit, score };
  }).filter((x) => x.score > 0);
  return scored.sort((a, b) => b.score - a.score || b.hit.authority - a.hit.authority).map((x) => x.hit);
}
