// Guided demos (docs/handoff/evaluator-demo.md): parsing GET /api/demo/tours[/slug], the step order, the Back and Next
// bounds, and the Gate 2 action (called once; an approved gate is passed through; a failed approval stays on the step).
import { describe, expect, it, vi } from "vitest";
import { MOCK_TOUR, MOCK_TOUR_SLUG } from "@/lib/mock/tours";
import {
  createTourMachine, gateOfStep, parseTour, parseTourList, TOUR_STAGES, workspaceStageFor, workspaceTabFor, type TourDeps,
} from "@/lib/tour";

const STEP = (stage: string, extra: Record<string, unknown> = {}) => ({
  stage, tab: "dossier", title: `${stage} title`, caption: `${stage} caption`, agent: null, filled: [], action: null, ...extra,
});

const RAW = {
  slug: "01-cheating-parity",
  case_id: "case-demo-01",
  title: "Demo · Cheating",
  story: "Two sentences.",
  variant: { offence: "Cheating", custody: "167 days", record: "Clean", parity: "Co-accused on bail" },
  recorded: { date: "2026-11-14", backend: "sarvam", model: "sarvam-m", cost_inr: 1.5 },
  steps: TOUR_STAGES.map((s) => STEP(s, s === "GATE_2" ? { action: "approve_gate_2" } : {})),
};

function deps(over: Partial<TourDeps> = {}): TourDeps & { approveGate2: ReturnType<typeof vi.fn> } {
  return { isGate2Approved: () => false, approveGate2: vi.fn(async () => {}), ...over } as TourDeps & { approveGate2: ReturnType<typeof vi.fn> };
}

const tour = parseTour(RAW)!;
const GATE2 = TOUR_STAGES.indexOf("GATE_2");

describe("parsing", () => {
  it("keeps the summary, the variant and the recording", () => {
    expect(tour.slug).toBe("01-cheating-parity");
    expect(tour.case_id).toBe("case-demo-01");
    expect(tour.variant).toEqual(RAW.variant);
    expect(tour.recorded).toEqual({ date: "2026-11-14", backend: "sarvam", model: "sarvam-m", cost_inr: 1.5 });
    expect(tour.steps).toHaveLength(9);
  });

  it("puts the steps in workflow order whatever order the file has, and drops unknown stages", () => {
    const shuffled = parseTour({ ...RAW, steps: [...RAW.steps].reverse().concat([STEP("LUNCH")]) })!;
    expect(shuffled.steps.map((s) => s.stage)).toEqual([...TOUR_STAGES]);
  });

  it("gives the approve action to the Gate 2 step only", () => {
    const odd = parseTour({ ...RAW, steps: RAW.steps.map((s) => ({ ...s, action: "approve_gate_2" })) })!;
    expect(odd.steps.filter((s) => s.action === "approve_gate_2").map((s) => s.stage)).toEqual(["GATE_2"]);
  });

  it("reads agents, filled fields and tabs defensively", () => {
    const t = parseTour({
      ...RAW,
      steps: [
        STEP("INTAKE", { agent: "MUNSHI", filled: [{ label: "Documents", value: "FIR" }, { nonsense: true }, null] }),
        STEP("SPAR", { agent: "NOBODY", tab: "elsewhere" }),
      ],
    })!;
    expect(t.steps[0].agent).toBe("MUNSHI");
    expect(t.steps[0].filled).toEqual([{ label: "Documents", value: "FIR" }]);
    expect(t.steps[1].agent).toBeNull();
    expect(t.steps[1].tab).toBe("spar");
  });

  it("rejects a tour with no slug, no case or no usable step", () => {
    expect(parseTour({ ...RAW, slug: "" })).toBeNull();
    expect(parseTour({ ...RAW, case_id: undefined })).toBeNull();
    expect(parseTour({ ...RAW, steps: [STEP("LUNCH")] })).toBeNull();
    expect(parseTour(null)).toBeNull();
  });

  it("lists only usable tours; anything that is not a list is no tours", () => {
    expect(parseTourList([RAW, { slug: "x" }, 3]).map((t) => t.slug)).toEqual(["01-cheating-parity"]);
    expect(parseTourList({ detail: "Not Found" })).toEqual([]);
    expect(parseTourList(null)).toEqual([]);
  });

  it("parses the demo build's own tour over case-0007", () => {
    const t = parseTour(MOCK_TOUR)!;
    expect(t.slug).toBe(MOCK_TOUR_SLUG);
    expect(t.case_id).toBe("case-0007");
    expect(t.steps.map((s) => s.stage)).toEqual([...TOUR_STAGES]);
  });
});

describe("where a step opens in the workspace", () => {
  it("maps the gates into their steps and the objections into Draft grounds", () => {
    expect(workspaceStageFor("GATE_1")).toBe("DOSSIER");
    expect(workspaceStageFor("GATE_2")).toBe("FILE");
    expect(workspaceStageFor("RIGHTS")).toBe("RIGHTS");
    expect(workspaceStageFor("SPAR")).toBe("SPAR");
    expect(workspaceTabFor({ stage: "SPAR", tab: "brief" })).toBe("spar");
    expect(workspaceTabFor({ stage: "RIGHTS", tab: "rights" })).toBe("rights");
    expect(gateOfStep("GATE_1")).toBe("GATE_1_DOSSIER");
    expect(gateOfStep("GATE_2")).toBe("GATE_2_EXPORT");
    expect(gateOfStep("BRIEF")).toBeNull();
  });
});

describe("the step machine", () => {
  it("starts at the first step and stays inside the bounds", async () => {
    const m = createTourMachine(tour, deps({ isGate2Approved: () => true }));
    expect(m.getState()).toMatchObject({ index: 0, total: 9, busy: false, error: null });
    expect(m.back().index).toBe(0);
    for (let i = 0; i < 20; i++) await m.next();
    expect(m.getState().index).toBe(8);
    expect(m.goTo(-5).index).toBe(0);
    expect(m.goTo(99).index).toBe(8);
    expect(m.back().index).toBe(7);
  });

  it("walks the stages in order with Next", async () => {
    const m = createTourMachine(tour, deps());
    const seen = [tour.steps[m.getState().index].stage];
    while (m.getState().index < 8) seen.push(tour.steps[(await m.next()).index].stage);
    expect(seen).toEqual([...TOUR_STAGES]);
  });

  it("approves Gate 2 once, even when Next is pressed twice or the evaluator goes back and forth", async () => {
    let approved = false;
    const d = deps({ isGate2Approved: () => approved });
    d.approveGate2.mockImplementation(async () => {
      await new Promise((r) => setTimeout(r, 10));
      approved = true;
    });
    const m = createTourMachine(tour, d, GATE2);
    const first = m.next();
    expect(m.getState().busy).toBe(true);
    const second = m.next();
    await Promise.all([first, second]);
    expect(d.approveGate2).toHaveBeenCalledTimes(1);
    expect(m.getState()).toMatchObject({ index: GATE2 + 1, busy: false, error: null });
    m.back();
    await m.next();
    expect(d.approveGate2).toHaveBeenCalledTimes(1);
    expect(m.getState().index).toBe(GATE2 + 1);
  });

  it("moves on without calling the route when Gate 2 is already approved (a second evaluator)", async () => {
    const d = deps({ isGate2Approved: () => true });
    const m = createTourMachine(tour, d, GATE2);
    await m.next();
    expect(d.approveGate2).not.toHaveBeenCalled();
    expect(m.getState().index).toBe(GATE2 + 1);
  });

  it("moves on when the approval fails because someone approved it meanwhile", async () => {
    const d = deps({ recheckGate2: async () => true });
    d.approveGate2.mockRejectedValue(new Error("Gate already approved"));
    const m = createTourMachine(tour, d, GATE2);
    await m.next();
    expect(m.getState()).toMatchObject({ index: GATE2 + 1, error: null });
  });

  it("stays on the Gate 2 step with the server's message when the approval fails, and can try again", async () => {
    const d = deps({ recheckGate2: async () => false });
    d.approveGate2.mockRejectedValueOnce(new Error("2 checklist item(s) are unresolved."));
    const m = createTourMachine(tour, d, GATE2);
    await m.next();
    expect(m.getState()).toMatchObject({ index: GATE2, busy: false, error: "2 checklist item(s) are unresolved." });
    await m.next();
    expect(d.approveGate2).toHaveBeenCalledTimes(2);
    expect(m.getState()).toMatchObject({ index: GATE2 + 1, error: null });
  });

  it("does not call the Gate 2 route from any other step", async () => {
    const d = deps();
    const m = createTourMachine(tour, d);
    for (let i = 0; i < GATE2; i++) await m.next();
    expect(d.approveGate2).not.toHaveBeenCalled();
    expect(m.getState().index).toBe(GATE2);
  });

  it("tells subscribers about every move", async () => {
    const m = createTourMachine(tour, deps());
    const listener = vi.fn();
    const off = m.subscribe(listener);
    await m.next();
    m.back();
    off();
    await m.next();
    expect(listener).toHaveBeenCalledTimes(2);
  });
});
