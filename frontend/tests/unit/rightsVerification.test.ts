/**
 * Rights rule verification (docs/handoff/code-final.md §6): `verification` is "unverified" until a person re-checks the rule
 * text against the bare act, then the ISO date; `unverified_checks` names the open ones. Both are additive.
 */
import { describe, expect, it } from "vitest";
import { MOCK_RIGHTS } from "@/lib/mock/case0007";
import { ruleVerifiedOn, unverifiedChecks } from "@/lib/status";
import type { RightsCheckResult } from "@/lib/types";

const base: RightsCheckResult = { check: "default_bail", status: "NOT_YET", uses: [] };

describe("ruleVerifiedOn", () => {
  it("reads the API's verification field", () => {
    expect(ruleVerifiedOn({ ...base, verification: "unverified" })).toBeNull();
    expect(ruleVerifiedOn({ ...base, verification: "2026-10-27" })).toBe("2026-10-27");
  });

  it("prefers verification over last_verified", () => {
    expect(ruleVerifiedOn({ ...base, verification: "unverified", last_verified: "2026-10-27" })).toBeNull();
  });

  it("falls back to last_verified on an older backend, and treats neither as unverified", () => {
    expect(ruleVerifiedOn({ ...base, last_verified: "2026-10-27" })).toBe("2026-10-27");
    expect(ruleVerifiedOn({ ...base, last_verified: null })).toBeNull();
    expect(ruleVerifiedOn(base)).toBeNull();
  });
});

describe("unverifiedChecks", () => {
  const checks: RightsCheckResult[] = [
    { ...base, check: "default_bail", verification: "unverified" },
    { ...base, check: "grounds_of_arrest", verification: "2026-10-27" },
  ];

  it("uses unverified_checks when the API sends it", () => {
    expect(unverifiedChecks({ checks, unverified_checks: ["grounds_of_arrest"] }).map((c) => c.check)).toEqual(["grounds_of_arrest"]);
  });

  it("derives the list from each check when the field is absent", () => {
    expect(unverifiedChecks({ checks }).map((c) => c.check)).toEqual(["default_bail"]);
  });

  it("the sample case mirrors configs/rights_rules.yaml: four of seven rule texts unverified", () => {
    expect(unverifiedChecks(MOCK_RIGHTS).map((c) => c.check)).toEqual(["default_bail", "undertrial_limit", "antil_category", "statutory_bar"]);
  });
});
