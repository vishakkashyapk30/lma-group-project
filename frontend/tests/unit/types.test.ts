/**
 * lib/types.ts mirrors src/vakeel_sahayak/schemas/enums.py (README: "keep them in sync"; plan §4.6, §6.3, §7, §8, §9, §13.5).
 * A drift here is a finding for the implementers, not something to patch silently.
 */
import { describe, expect, it } from "vitest";
import { pyEnum, tsUnion } from "./_helpers";

// [TypeScript union name, Python enum class name]
const MIRRORED: [string, string][] = [
  ["FieldStatus", "FieldStatus"],
  ["RightsStatus", "RightsStatus"],
  ["ClaimCheck", "ClaimCheck"],
  ["SparringVerdict", "SparringVerdict"],
  ["Stage", "Stage"],
  ["GateId", "GateId"],
  ["SlotStatus", "SlotStatus"],
  ["ClaimState", "ClaimState"],
  ["TransferFlag", "TransferFlag"],
  ["GoodLawStatus", "GoodLawStatus"],
  ["AgentName", "AgentName"],
  ["StoreName", "StoreName"],
  ["Factor", "Factor"],
  ["EventKind", "EventKind"],
  ["RightsCheckName", "RightsCheckName"],
];

describe("lib/types.ts mirrors the Python enums", () => {
  it.each(MIRRORED)("%s has exactly the members of enums.%s", (ts, py) => {
    const tsMembers = tsUnion(ts);
    const pyMembers = pyEnum(py);
    expect(pyMembers.length).toBeGreaterThan(0);
    expect(new Set(tsMembers).size).toBe(tsMembers.length); // no duplicates
    expect([...tsMembers].sort()).toEqual([...pyMembers].sort());
  });

  it("the parser really sees the plan's values (guards against a vacuous regex)", () => {
    expect(tsUnion("FieldStatus")).toEqual(
      expect.arrayContaining(["VERIFIED", "COMPUTED", "UNSUPPORTED", "AMBIGUOUS", "USER_STATED", "USER_EDITED"]),
    );
    expect(pyEnum("GateId")).toEqual(["GATE_1_DOSSIER", "GATE_2_EXPORT"]);
    expect(tsUnion("Stage")).toHaveLength(7);
    expect(tsUnion("RightsStatus")).toHaveLength(13);
  });
});
