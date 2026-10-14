/**
 * Stage rail (plan §13.5): seven stages numbered like the Parts of the Constitution; Gate 1 follows the dossier, Gate 2
 * comes before export; counsel can jump to any open stage; later stages unlock after Gate 1.
 */
import type { ComponentType } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { STAGES } from "@/lib/stages";
import { StageRail } from "@/components/workspace/StageRail";
import type { Stage } from "@/lib/types";
import { tsUnion } from "./_helpers";

describe("STAGES table (plan §13.5)", () => {
  it("lists I-VII in order with the plan's labels", () => {
    expect(STAGES.map((s) => [s.id, s.numeral, s.label])).toEqual([
      ["INTAKE", "I", "Intake"],
      ["DOSSIER", "II", "Dossier"],
      ["RIGHTS", "III", "Rights"],
      ["BRIEF", "IV", "Brief"],
      ["SPAR", "V", "Spar"],
      ["HEARING_PREP", "VI", "Hearing prep"],
      ["FILE", "VII", "File"],
    ]);
  });
  it("Gate 1 (GATE_1_DOSSIER) follows Dossier; Gate 2 (GATE_2_EXPORT) is attached to File; exactly two gates", () => {
    const gated = STAGES.filter((s) => s.gate);
    expect(gated.map((s) => [s.id, s.gate])).toEqual([
      ["DOSSIER", "GATE_1_DOSSIER"],
      ["FILE", "GATE_2_EXPORT"],
    ]);
    expect(STAGES.findIndex((s) => s.gate === "GATE_1_DOSSIER")).toBe(1); // right after stage II's position
    expect(STAGES[STAGES.length - 1].gate).toBe("GATE_2_EXPORT"); // before export, the last step
  });
  it("stage ids equal the Stage union of lib/types.ts, in order", () => {
    expect(STAGES.map((s) => s.id)).toEqual(tsUnion("Stage"));
  });
  it("gate ids belong to the GateId union", () => {
    const ids = tsUnion("GateId");
    for (const s of STAGES) if (s.gate) expect(ids).toContain(s.gate);
  });
});

// ASSUMPTION: StageRail props beyond the skeleton: onSelect(stage) and gate1Approved (default false); each stage item
// (data-testid stage-I..stage-VII) is the interactive element and carries aria-disabled="true" while locked;
// approval diamonds are data-testid gate-diamond-1 / gate-diamond-2.
interface RailProps { current?: Stage; onSelect?: (s: Stage) => void; gate1Approved?: boolean; className?: string }
const Rail = StageRail as unknown as ComponentType<RailProps>;
const NUMERALS = ["I", "II", "III", "IV", "V", "VI", "VII"];

describe("<StageRail /> (fails until implemented)", () => {
  it("renders seven items in order with numerals I..VII", () => {
    const { container } = render(<Rail current="INTAKE" />);
    const items = NUMERALS.map((n) => screen.getByTestId(`stage-${n}`));
    items.forEach((el, i) => {
      expect(el).toHaveTextContent(new RegExp(`\\b${NUMERALS[i]}\\b`));
      expect(el).toHaveTextContent(STAGES[i].label);
    });
    // DOM order == plan order
    const all = [...container.querySelectorAll("[data-testid^='stage-']")].map((e) => e.getAttribute("data-testid"));
    expect(all.filter((t) => /^stage-[IVX]+$/.test(t!))).toEqual(NUMERALS.map((n) => `stage-${n}`));
  });

  it("shows exactly two approval diamonds (Gate 1 on Dossier, Gate 2 on File)", () => {
    render(<Rail current="INTAKE" />);
    expect(screen.getAllByTestId(/^gate-diamond-/)).toHaveLength(2);
    expect(screen.getByTestId("gate-diamond-1")).toBeInTheDocument();
    expect(screen.getByTestId("gate-diamond-2")).toBeInTheDocument();
  });

  it("locks III..VII (aria-disabled) until Gate 1 is approved; I and II stay open", () => {
    render(<Rail current="DOSSIER" gate1Approved={false} />);
    for (const n of ["I", "II"]) expect(screen.getByTestId(`stage-${n}`)).not.toHaveAttribute("aria-disabled", "true");
    for (const n of ["III", "IV", "V", "VI", "VII"]) {
      expect(screen.getByTestId(`stage-${n}`)).toHaveAttribute("aria-disabled", "true");
    }
  });

  it("unlocks every stage once Gate 1 is approved", () => {
    render(<Rail current="RIGHTS" gate1Approved />);
    for (const n of NUMERALS) expect(screen.getByTestId(`stage-${n}`)).not.toHaveAttribute("aria-disabled", "true");
  });

  it("marks the current stage with aria-current=step", () => {
    render(<Rail current="BRIEF" gate1Approved />);
    expect(screen.getByTestId("stage-IV")).toHaveAttribute("aria-current", "step");
    expect(screen.getByTestId("stage-III")).not.toHaveAttribute("aria-current");
  });

  it("clicking an open stage calls onSelect with its id; a locked stage does not", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(<Rail current="INTAKE" onSelect={onSelect} gate1Approved={false} />);
    await user.click(screen.getByTestId("stage-II"));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith("DOSSIER");
    onSelect.mockClear();
    await user.click(screen.getByTestId("stage-V"));
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("is keyboard operable: an open stage activates with Enter", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(<Rail current="INTAKE" onSelect={onSelect} />);
    screen.getByTestId("stage-II").focus();
    await user.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledWith("DOSSIER");
  });

  it("is a navigation landmark exposing the stage list", () => {
    render(<Rail current="INTAKE" />);
    const nav = screen.getByTestId("stage-rail");
    expect(within(nav).getAllByTestId(/^stage-[IVX]+$/)).toHaveLength(7);
  });
});
