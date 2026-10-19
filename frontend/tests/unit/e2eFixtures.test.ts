/**
 * Guards the Playwright mock fixtures (e2e/fixtures/*.json): the three case-0007 files must equal the Python test fixtures, and the
 * hand-built ones must use only enum values the backend defines (src/vakeel_sahayak/schemas/enums.py), so the e2e mocks cannot drift
 * from the real API contract.
 */
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { fx } from "../../e2e/fixtures";
import { FRONTEND_ROOT, REPO_ROOT, pyEnum } from "./_helpers";

const same = (name: string) => {
  const a = fs.readFileSync(path.join(FRONTEND_ROOT, "e2e/fixtures", name), "utf8");
  const b = fs.readFileSync(path.join(REPO_ROOT, "tests/fixtures/case_0007", name), "utf8");
  expect(JSON.parse(a)).toEqual(JSON.parse(b));
};

describe("e2e fixtures", () => {
  it.each(["dossier.json", "rights_report.json", "timeline.json"])("%s is a faithful copy of tests/fixtures/case_0007", same);

  it("dossier statuses are FieldStatus values and antecedents is the red field", () => {
    const d = fx.dossier();
    for (const f of Object.values(d.fields)) expect(pyEnum("FieldStatus")).toContain(f.status);
    expect(d.fields.antecedents.status).toBe("UNSUPPORTED");
    expect(Object.keys(d.fields)).toHaveLength(13);
  });

  it("rights report: seven checks with RightsStatus values; default bail is WINDOW_CLOSED", () => {
    const r = fx.rights();
    expect(r.checks).toHaveLength(7);
    for (const c of r.checks) {
      expect(pyEnum("RightsStatus")).toContain(c.status);
      expect(pyEnum("RightsCheckName")).toContain(c.check);
    }
    expect(r.checks.find((c) => c.check === "default_bail")!.status).toBe("WINDOW_CLOSED");
  });

  it("gates use GateId values and are consistent with each other", () => {
    for (const g of [fx.gate1Blocked(), fx.gate1Open(), fx.gate2Blocked(), fx.gate2Open()]) expect(pyEnum("GateId")).toContain(g.gate);
    expect(fx.gate1Blocked().unresolved_unsupported).toEqual(["antecedents"]);
    // RECONCILED: GateStatus.open is true while the gate has NOT been approved (record/gates.py: open=not gate_is_approved).
    expect(fx.gate2Blocked().open).toBe(true);
    expect(fx.gate2Open()).toMatchObject({ open: false, unresolved_needs_review: [], unresolved_unanswered: [] });
  });

  it("brief: claim checks and states are enum values; grounds G1 SUPPORTED, G2 REPAIRED, G3 NEEDS_REVIEW", () => {
    const b = fx.brief();
    for (const g of b.grounds) {
      expect(pyEnum("ClaimCheck")).toContain(g.check);
      expect(pyEnum("ClaimState")).toContain(g.state);
      expect(pyEnum("Factor")).toContain(g.factor);
      expect(pyEnum("FactorStance")).toContain(g.stance);
      for (const a of g.authorities) expect(pyEnum("GoodLawStatus")).toContain(a.good_law);
    }
    expect(b.grounds.map((g) => [g.id, g.check])).toEqual([["G1", "SUPPORTED"], ["G2", "REPAIRED"], ["G3", "NEEDS_REVIEW"]]);
  });

  it("spar record: verdicts are SparringVerdict values; an UNANSWERED objection has no reply", () => {
    const s = fx.spar();
    for (const o of s.objections) expect(pyEnum("SparringVerdict")).toContain(o.verdict);
    expect(s.objections.map((o) => o.verdict)).toEqual(["ANSWERED", "PARTLY", "UNANSWERED"]);
    expect(s.objections[2].reply).toBeNull();
  });

  it("ingestion bundle: 14 pages, four documents, routes and types come from the backend enums, one unreadable page", () => {
    const r = fx.ingestionBundle();
    expect(r.documents.map((d) => d.type)).toEqual(["FIR", "REMAND_ORDER", "REMAND_ORDER", "BAIL_ORDER"]);
    const pages = r.documents.flatMap((d) => d.page_routes);
    expect(pages).toHaveLength(14);
    for (const d of r.documents) expect(pyEnum("DocumentType")).toContain(d.type);
    for (const p of pages) for (const route of p.route) expect(pyEnum("ParseRoute")).toContain(route);
    expect(new Set(pages.flatMap((p) => p.route))).toEqual(new Set(["text_layer", "layout", "ocr", "vision", "ask_counsel"]));
    expect(pages.filter((p) => p.status === "UNREADABLE")).toHaveLength(1);
    expect(r.questions).toHaveLength(1);
  });

  it("triage cards are delivered unsorted so the UI's sort is exercised", () => {
    const ranks = fx.triageCards().map((c) => c.urgency_rank);
    expect(ranks).not.toEqual([...ranks].sort((a, b) => a - b));
    expect(new Set(ranks).size).toBe(ranks.length);
  });

  it("draft events: valid kinds and actors, four Sutradhar TOOL_CALLs, tools are Sutradhar's allowed tools", () => {
    const tools = fs.readFileSync(path.join(REPO_ROOT, "configs/tools.yaml"), "utf8");
    const sutradhar = tools.split(/^[a-z]+:\s*$/m)[3]; // munshi, peshkar, sutradhar...
    const evs = fx.draftEvents();
    for (const e of evs) {
      expect(pyEnum("EventKind")).toContain(e.kind);
      expect(pyEnum("AgentName")).toContain(e.actor);
    }
    const calls = evs.filter((e) => e.actor === "SUTRADHAR" && e.kind === "TOOL_CALL");
    expect(calls).toHaveLength(4);
    for (const c of calls) expect(sutradhar).toContain(`- ${c.tool}`);
  });

  it("chat messages and case summary use valid enums", () => {
    expect(pyEnum("AgentName")).toContain(fx.chatMessage().agent);
    expect(pyEnum("StoreName")).toContain(fx.chatMessage().chips[0].store);
    expect(pyEnum("Stage")).toContain(fx.caseSummary().stage);
    expect(fx.munshiQuestion().agent).toBe("MUNSHI");
  });

  // ---- flow 4 (the case moves on) and flow 5 (a dictated case)
  it("flow 4: the dossier differs from before to after only in charge_sheet; the brief differs in G2 only", () => {
    const before = fx.dossierBeforeChange(), after = fx.dossierAfterChange();
    const af = after.fields as unknown as Record<string, unknown>, bf = before.fields as unknown as Record<string, unknown>;
    const changed = Object.keys(af).filter((k) => JSON.stringify(af[k]) !== JSON.stringify(bf[k]));
    expect(changed).toEqual(["charge_sheet"]);
    expect((before.fields.charge_sheet.value as { filed: boolean }).filed).toBe(false);
    expect((after.fields.charge_sheet.value as { filed: boolean; date: string }).date).toBe("2024-11-02");
    for (const f of Object.values(before.fields)) expect(pyEnum("FieldStatus")).toContain(f.status);
    expect(Object.values(before.fields).filter((f) => f.status === "UNSUPPORTED")).toHaveLength(0); // re-approval needs no acknowledgement
    const b = fx.briefBeforeChange(), a = fx.briefAfterChange();
    expect(b.grounds.map((g) => g.id)).toEqual(["G1", "G2", "G3"]);
    expect(a.grounds.filter((g, i) => JSON.stringify(g) !== JSON.stringify(b.grounds[i])).map((g) => g.id)).toEqual(["G2"]);
    for (const g of [...a.grounds, ...b.grounds]) {
      expect(pyEnum("ClaimCheck")).toContain(g.check);
      expect(pyEnum("Factor")).toContain(g.factor);
    }
    expect(b.grounds[1].depends_on.facts).toHaveProperty("charge_sheet"); // G2 depends on the field that changes
  });

  it("flow 4: change events use backend event kinds; ch001 carries the change set; only G2 is redrafted", () => {
    const evs = fx.changeEvents();
    for (const e of evs) {
      expect(pyEnum("EventKind")).toContain(e.kind);
      expect([...pyEnum("AgentName"), "counsel"]).toContain(e.actor);
    }
    expect(evs.map((e) => e.kind)).toEqual(["STORE_WRITE", "CHANGE_SET_APPROVED", "CLAIM_STALED", "AGENT_MESSAGE", "STORE_WRITE"]);
    const cs = (evs[0].outputs as { change_set: { fields: { field: string }[]; rights_changed: string[] } }).change_set;
    expect(cs.fields.map((f) => f.field)).toEqual(["charge_sheet"]);
    for (const r of cs.rights_changed) expect(pyEnum("RightsCheckName")).toContain(r);
    expect((evs[4].outputs as { redrafted: string[] }).redrafted).toEqual(["G2"]);
    expect(new Set(evs.map((e) => e.event_id)).size).toBe(evs.length);
  });

  it("flow 5: the read-back names the dictated date and section; dictated fields are USER_STATED; the brief says 'per counsel'", () => {
    const rb = fx.dictationReadback();
    expect(rb.questions.join(" ")).toContain("20.08.2024");
    expect(rb.questions.join(" ")).toContain("318(4)");
    expect(rb.questions.join(" ")).toMatch(/confirm/i);
    const d = fx.dossierDictated();
    for (const f of Object.values(d.fields)) {
      expect(f.status).toBe("USER_STATED");
      expect(f.source?.chat).toBeTruthy();
    }
    const g = fx.briefDictated().grounds[0];
    expect(g.argument).toContain("per counsel, not on record");
    expect(pyEnum("Factor")).toContain(g.factor);
  });
});
