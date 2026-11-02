/**
 * Dossier gaps by factor and sentence types (lib/factorGaps.ts), and the grouping of likely objections by ground.
 * The factor table must equal the drafter's (agents/vakeel/facts.py FACTOR_FIELDS), and the sentence rule must give the same
 * class as the M6a metric's classify (eval/scoring/split_metric.py) on the cases below.
 */
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { groupByGround } from "@/components/workspace/tabs/SparTab";
import { briefSentences, classifySentence, FACTOR_FIELDS, factorGaps, splitSentences } from "@/lib/factorGaps";
import { MOCK_BRIEF, MOCK_DOSSIER, MOCK_SPAR } from "@/lib/mock/case0007";
import type { CaseDossier, Objection } from "@/lib/types";
import { FACTORS } from "@/lib/types";
import { REPO_ROOT } from "./_helpers";

/** FACTOR_FIELDS of agents/vakeel/facts.py as {factor: [fields]}. */
function pythonFactorFields(): Record<string, string[]> {
  const src = fs.readFileSync(path.join(REPO_ROOT, "src/vakeel_sahayak/agents/vakeel/facts.py"), "utf8");
  const block = src.match(/FACTOR_FIELDS[^=]*=\s*\{([\s\S]*?)\n\}/);
  if (!block) throw new Error("FACTOR_FIELDS not found in facts.py");
  const out: Record<string, string[]> = {};
  for (const m of block[1].matchAll(/"([a-z_]+)":\s*\(([^)]*)\)/g)) out[m[1]] = [...m[2].matchAll(/"([a-z_]+)"/g)].map((x) => x[1]);
  return out;
}

describe("FACTOR_FIELDS", () => {
  it("equals the drafter's table in agents/vakeel/facts.py", () => {
    const ts = Object.fromEntries(Object.entries(FACTOR_FIELDS).map(([k, v]) => [k, [...v]]));
    expect(ts).toEqual(pythonFactorFields());
  });
  it("covers the twelve factors", () => {
    expect(Object.keys(FACTOR_FIELDS).sort()).toEqual([...FACTORS].sort());
  });
});

describe("factorGaps", () => {
  it("is empty without a dossier", () => {
    expect(factorGaps(null)).toEqual([]);
  });
  it("on the sample case only antecedents has nothing in the file", () => {
    const gaps = factorGaps(MOCK_DOSSIER);
    expect(gaps.map((g) => g.factor)).toEqual([...FACTORS]);
    expect(gaps.filter((g) => g.coverage === "none").map((g) => g.factor)).toEqual(["antecedents"]);
    expect(gaps.find((g) => g.factor === "antecedents")?.missing).toEqual(["antecedents"]);
  });
  it("counts a found field with an empty value as missing, a disputed one as unclear, and gives partial coverage", () => {
    const d: CaseDossier = structuredClone(MOCK_DOSSIER);
    d.fields.trial_stage = { value: "", source: null, status: "VERIFIED" };
    d.fields.charge_sheet = { ...d.fields.charge_sheet, status: "AMBIGUOUS" };
    const witness = factorGaps(d).find((g) => g.factor === "witness_tampering");
    expect(witness).toMatchObject({ coverage: "partial", missing: ["trial_stage"], unclear: ["charge_sheet"], present: [] });
  });
  it("a fact counsel entered counts as present", () => {
    const flight = factorGaps(MOCK_DOSSIER).find((g) => g.factor === "flight_risk");
    expect(flight).toMatchObject({ coverage: "full", present: ["personal"] });
  });
});

describe("sentence types (the M6a marker rule)", () => {
  it.each([
    ["The applicant was arrested on 20.08.2024 [F:arrest_date].", "case_fact"],
    ["Parity applies [A:SC-2014-0463#9] to a co-accused on the same footing [F:co_accused_bail].", "legal"],
    ["Bail is the rule and jail the exception.", "not_in_record"],
    ["The record is silent on the applicant's antecedents [F:antecedents].", "absence"],
    ["Qualification: BNS 316(2) now prescribes a higher maximum [A:DLHC-2021-0388#9].", "note"],
  ])("%s -> %s", (sentence, kind) => {
    expect(classifySentence(sentence)).toBe(kind);
  });
  it("splits like the backend: not after abbreviations such as Sec. or a single initial", () => {
    expect(splitSentences("Under Sec. 37 the bar applies. Mr. A. Kumar was arrested. Bail follows.")).toEqual([
      "Under Sec. 37 the bar applies.",
      "Mr. A. Kumar was arrested.",
      "Bail follows.",
    ]);
  });
  it("collects each sentence's facts and authorities once", () => {
    const g3 = MOCK_BRIEF.grounds.find((g) => g.id === "G3");
    const s = briefSentences(g3?.argument ?? "");
    expect(s.map((x) => x.kind)).toEqual(["case_fact", "legal"]);
    expect(s[0].facts).toEqual(["custody_days", "arrest_date"]);
    expect(s[1].authorities).toEqual([{ doc_id: "SC-2012-0040", para: 24 }]);
  });
});

describe("groupByGround", () => {
  const obj = (id: string, against: string, verdict: Objection["verdict"]): Objection => ({ id, against, factor: "custody_period", objection: id, grounds: [], reply: null, verdict });
  it("orders groups by the draft, general last, unanswered first inside a group", () => {
    const groups = groupByGround([obj("O1", "general", "ANSWERED"), obj("O2", "G3", "ANSWERED"), obj("O3", "G1", "ANSWERED"), obj("O4", "G3", "UNANSWERED")], MOCK_BRIEF.grounds);
    expect(groups.map((g) => g.key)).toEqual(["G1", "G3", "general"]);
    expect(groups[1].objections.map((o) => o.id)).toEqual(["O4", "O2"]);
    expect(groups[2].title).toBe("General");
  });
  it("keeps every objection of the sample record", () => {
    const groups = groupByGround(MOCK_SPAR.objections, MOCK_BRIEF.grounds);
    expect(groups.flatMap((g) => g.objections).length).toBe(MOCK_SPAR.objections.length);
  });
});
