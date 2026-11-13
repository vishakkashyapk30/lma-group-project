// Every objection Abhiyojak raised is listed in "Likely objections", whatever its verdict: answered, partly answered, not answered
// yet, and not judged yet. With X7 (c1457) grounded objections are no longer discarded, so the list must not show a subset.
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MOCK_SPAR } from "@/lib/mock/case0007";
import type { Objection, SparringRecord } from "@/lib/types";

const state = vi.hoisted(() => ({ spar: null as unknown }));

vi.mock("@/lib/workspace", () => {
  const data = () => ({ spar: state.spar, dossier: null, ingestion: null, loading: { spar: false }, errors: { spar: null }, refresh: () => undefined });
  const ws = () => ({ data: data(), focusTarget: null, focusItem: () => undefined, clearSource: () => undefined, openDetail: () => undefined, selectSource: () => undefined });
  return {
    useWorkspace: ws,
    useCaseData: data,
    useGates: () => ({ resolutions: { resolved: {} }, resolveItem: () => undefined, unresolveItem: () => undefined }),
    useStageNav: () => ({ focusItem: () => undefined }),
    checklistKey: (kind: string, id: string) => `${kind}:${id}`,
  };
});

const { ObjectionsSection, objectionSummary } = await import("@/components/workspace/tabs/SparTab");

const unjudged: Objection = {
  id: "O4", against: "G3", factor: "custody_period", objection: "Custody is short for an offence of this gravity.", grounds: [{ fact: "custody_days" }], reply: null, verdict: null, reason: null,
};
const record: SparringRecord = { ...MOCK_SPAR, objections: [...MOCK_SPAR.objections, unjudged] };

describe("objectionSummary", () => {
  it("counts every verdict, and the ones not judged yet only when there are some", () => {
    expect(objectionSummary(MOCK_SPAR.objections)).toBe("3 objections: 1 answered, 1 partly answered, 1 not answered yet.");
    expect(objectionSummary(record.objections)).toBe("4 objections: 1 answered, 1 partly answered, 1 not answered yet, 1 not judged yet.");
  });
});

describe("ObjectionsSection", () => {
  beforeEach(() => {
    state.spar = record;
  });

  it("lists every objection raised, whatever its verdict", () => {
    render(<ObjectionsSection />);
    const items = screen.getAllByTestId("spar-objection");
    // RECONCILED: objections are grouped under the ground they answer (lib: groupByGround), unanswered ones first within a group,
    // so the order is by ground (O1 and O4 are in different groups from O2 and O3) rather than the order raised. Every one is still listed.
    expect(items.map((i) => i.getAttribute("data-objection"))).toEqual(["O1", "O4", "O3", "O2"]);
    expect(items.map((i) => i.getAttribute("data-verdict"))).toEqual(["ANSWERED", null, "PARTLY", "UNANSWERED"]);
    expect([...items.map((i) => i.getAttribute("data-objection"))].sort()).toEqual(["O1", "O2", "O3", "O4"]);
    for (const o of record.objections) expect(screen.getByText(o.objection)).toBeTruthy();
    expect(screen.getByText("4 objections: 1 answered, 1 partly answered, 1 not answered yet, 1 not judged yet.")).toBeTruthy();
    expect(screen.getByText("Not judged yet")).toBeTruthy();
  });

  it("opens only the unanswered ones and the unjudged one stays listed", () => {
    render(<ObjectionsSection />);
    const opened = screen.getAllByTestId("spar-objection").filter((i) => i.querySelector('[aria-expanded="true"]'));
    expect(opened.map((i) => i.getAttribute("data-objection"))).toEqual(["O2"]);
  });
});
