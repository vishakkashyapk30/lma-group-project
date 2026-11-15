// An objection that got no reply because the sparring budget was spent keeps the verdict UNANSWERED (so Gate 2 lists it for counsel); its reason
// carries the stable prefix NOT_REPLIED_BUDGET:, which the interface shows in plain words.
import { describe, expect, it } from "vitest";
import { isNotRepliedBudget, plainReason } from "@/lib/format";
import { rawChecklistItems } from "@/lib/workspace/checklist";

const REASON = "NOT_REPLIED_BUDGET: no reply was drafted because the sparring budget was spent; counsel answers this one.";

describe("plainReason", () => {
  it("drops the code and capitalises the sentence", () => {
    expect(isNotRepliedBudget(REASON)).toBe(true);
    expect(plainReason(REASON)).toBe("No reply was drafted because the sparring budget was spent; counsel answers this one.");
  });
  it("leaves every other reason, and none, unchanged", () => {
    expect(plainReason("The reply could not be judged; counsel to read it.")).toBe("The reply could not be judged; counsel to read it.");
    expect(plainReason(null)).toBeNull();
    expect(isNotRepliedBudget(null)).toBe(false);
  });
});

describe("Gate 2 checklist", () => {
  it("lists the objection as unanswered with the plain reason", () => {
    const items = rawChecklistItems("GATE_2_EXPORT", {
      dossier: null, brief: null, spar: { case_id: "c", rounds: 2, discarded: [], objections: [{ id: "O7", against: "general", factor: "antecedents", objection: "Antecedents", grounds: [{ fact: "antecedents" }], reply: null, verdict: "UNANSWERED", reason: REASON }] },
    } as never);
    const hit = items.find((i) => i.ref === "O7");
    expect(hit?.kind).toBe("UNANSWERED");
    expect(hit?.detail).toBe("No reply was drafted because the sparring budget was spent; counsel answers this one.");
  });
});
