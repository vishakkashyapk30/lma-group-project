/**
 * Stage rail (plan §13.5): seven stages; Gate 1 follows the dossier, Gate 2 comes before export; counsel can jump to any open
 * stage; later stages unlock after Gate 1.
 *
 * RECONCILED (workspace redesign, docs/handoff/workspace-redesign.md and frontend/DESIGN.md "Things we do not do"): the rail is a
 * stepper of six plain-language steps. Sparring keeps its stage id (SPAR) but is shown inside "Draft grounds", so it has no step
 * button; no numerals are shown (DESIGN.md bans Constitution-style stage numerals); the gates are confirm dialogs inside their
 * steps, not diamonds. The stepper buttons keep the test ids stage-I..stage-VII (stage-V absent), and the lock, current-step,
 * click and keyboard behaviour below is unchanged.
 */
import type { ComponentType } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { STAGES, STEPPER_STAGES, stepOf } from "@/lib/stages";
import { StageRail } from "@/components/workspace/StageRail";
import type { Stage } from "@/lib/types";
import { tsUnion } from "./_helpers";

describe("STAGES table (plan §13.5)", () => {
  it("lists the seven stages in the plan's order with their plain-language labels", () => {
    expect(STAGES.map((s) => [s.id, s.key, s.label])).toEqual([
      ["INTAKE", "I", "Add documents"],
      ["DOSSIER", "II", "Review facts"],
      ["RIGHTS", "III", "Check rights"],
      ["BRIEF", "IV", "Draft grounds"],
      ["SPAR", "V", "Likely objections"],
      ["HEARING_PREP", "VI", "Prepare for the hearing"],
      ["FILE", "VII", "Export"],
    ]);
  });
  it("the stepper has six steps: Likely objections (SPAR) is shown inside Draft grounds", () => {
    expect(STEPPER_STAGES.map((s) => s.id)).toEqual(["INTAKE", "DOSSIER", "RIGHTS", "BRIEF", "HEARING_PREP", "FILE"]);
    expect(stepOf("SPAR")).toBe("BRIEF");
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

// ASSUMPTION: StageRail props beyond the skeleton: onSelect(stage) and gate1Approved (default false); each step button
// (data-testid stage-<key>) is the interactive element and carries aria-disabled="true" while locked.
interface RailProps { current?: Stage; onSelect?: (s: Stage) => void; gate1Approved?: boolean; className?: string }
const Rail = StageRail as unknown as ComponentType<RailProps>;
const KEYS = ["I", "II", "III", "IV", "VI", "VII"]; // the six steps; V (SPAR) has no button

describe("<StageRail /> (fails until implemented)", () => {
  it("renders the six steps in order with their labels and no numerals", () => {
    const { container } = render(<Rail current="INTAKE" />);
    KEYS.forEach((k, i) => {
      const el = screen.getByTestId(`stage-${k}`);
      expect(el).toHaveTextContent(STEPPER_STAGES[i].label);
      expect(el.textContent).not.toMatch(/\b(?:II|III|IV|VI|VII)\b/);
    });
    // DOM order == plan order
    const all = [...container.querySelectorAll("[data-testid^='stage-']")].map((e) => e.getAttribute("data-testid"));
    expect(all.filter((t) => /^stage-[IVX]+$/.test(t!))).toEqual(KEYS.map((k) => `stage-${k}`));
  });

  it("has no separate gate controls: the gates are confirm dialogs inside their steps", () => {
    render(<Rail current="INTAKE" />);
    expect(screen.queryAllByTestId(/^gate-diamond-/)).toHaveLength(0);
  });

  it("locks III..VII (aria-disabled) until Gate 1 is approved; I and II stay open", () => {
    render(<Rail current="DOSSIER" gate1Approved={false} />);
    for (const n of ["I", "II"]) expect(screen.getByTestId(`stage-${n}`)).not.toHaveAttribute("aria-disabled", "true");
    for (const n of ["III", "IV", "VI", "VII"]) {
      expect(screen.getByTestId(`stage-${n}`)).toHaveAttribute("aria-disabled", "true");
    }
  });

  it("unlocks every stage once Gate 1 is approved", () => {
    render(<Rail current="RIGHTS" gate1Approved />);
    for (const n of KEYS) expect(screen.getByTestId(`stage-${n}`)).not.toHaveAttribute("aria-disabled", "true");
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
    await user.click(screen.getByTestId("stage-VI"));
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
    expect(within(nav).getAllByTestId(/^stage-[IVX]+$/)).toHaveLength(6);
  });
});
