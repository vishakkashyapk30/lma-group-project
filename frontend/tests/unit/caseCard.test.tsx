import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CaseCard } from "@/components/cases/CaseCard";
import type { CaseSummary } from "@/lib/types";

const base: CaseSummary = { case_id: "case-0007", title: "State v. Accused-1", stage: "SPAR", rights_chips: [], needs_attention: 0 } as unknown as CaseSummary;

describe("CaseCard step line", () => {
  it("counts the six stepper steps and names a case at Likely objections by its step, Draft grounds", () => {
    render(<CaseCard summary={base} />);
    expect(screen.getByText("Draft grounds")).toBeTruthy();
    expect(screen.getByText("Step 4 of 6")).toBeTruthy();
    expect(screen.queryByText(/of 7/)).toBeNull();
    expect(screen.queryByText("Likely objections")).toBeNull();
  });

  it("puts Export last", () => {
    render(<CaseCard summary={{ ...base, stage: "FILE" }} />);
    expect(screen.getByText("Step 6 of 6")).toBeTruthy();
  });
});
