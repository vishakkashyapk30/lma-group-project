// What the draft left out (strict abstention, X4 of c1457): the reasons in plain words, the per-ground "Removed from the argument"
// list and the grounds left for counsel to draft. The brief's `withheld` field comes from GET /api/cases/{id}/brief.
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DroppedGrounds, RemovedSentences } from "@/components/workspace/tabs/Withheld";
import { MOCK_BRIEF } from "@/lib/mock/case0007";
import type { BailBrief, WithheldGround } from "@/lib/types";
import { droppedGrounds, plainReason, reasonSentence, withheldFor } from "@/lib/withheld";

describe("plainReason", () => {
  it("reads the checker's phrases in plain words and drops the bracketed scores", () => {
    expect(plainReason("not supported by the dossier quote (fact support 0.31)")).toBe("not supported by the record");
    expect(plainReason("not supported by the cited paragraph (PHHC-2023-1120#17 entailment 0.22)")).toBe("the cited paragraph does not say this");
    expect(plainReason("cites an overruled authority")).toBe("relies on a judgment that has been overruled");
    expect(plainReason("flagged by the model's own re-reading (no outside check)")).toBe("flagged on re-reading, with no outside check");
  });

  it("names the factor when the sentence only said the record is silent", () => {
    expect(plainReason("only says the record is silent", "trial_delay")).toBe("the record is silent on trial delay");
    expect(plainReason("only says the record is silent")).toBe("the record is silent on this point");
  });

  it("joins several problems and keeps an unknown reason without its scores", () => {
    expect(plainReason("not supported by the dossier quote, cites no fact or authority (fact support 0.1)")).toBe(
      "not supported by the record; cites no fact or authority",
    );
    expect(plainReason("something new (score 0.5)")).toBe("something new");
  });

  it("reasonSentence capitalises and ends with a full stop", () => {
    expect(reasonSentence("only says the record is silent", "parity_with_co_accused")).toBe("The record is silent on parity with co-accused.");
  });
});

describe("withheld per ground", () => {
  it("finds a ground's removed sentences and the grounds that lost every sentence", () => {
    expect(withheldFor(MOCK_BRIEF, "G5")?.sentences).toHaveLength(2);
    expect(withheldFor(MOCK_BRIEF, "G3")).toBeNull();
    expect(droppedGrounds(MOCK_BRIEF).map((g) => g.ground)).toEqual(["G8"]);
  });

  it("treats a brief without the field (an older API, or no strict abstention) as nothing withheld", () => {
    const brief: BailBrief = { ...MOCK_BRIEF, withheld: undefined };
    expect(withheldFor(brief, "G5")).toBeNull();
    expect(droppedGrounds(brief)).toEqual([]);
  });

  it("lists a ground missing from the brief even when it is not marked dropped", () => {
    const brief: BailBrief = { ...MOCK_BRIEF, withheld: [{ ground: "G9", factor: "flight_risk", dropped: false, sentences: [{ sentence: "x", reason: "could not be checked" }] }] };
    expect(droppedGrounds(brief).map((g) => g.ground)).toEqual(["G9"]);
  });
});

const G5: WithheldGround = MOCK_BRIEF.withheld!.find((w) => w.ground === "G5")!;

describe("RemovedSentences", () => {
  it("shows every removed sentence with its reason in plain words, behind a closed disclosure", () => {
    const { container } = render(<RemovedSentences group={G5} />);
    const details = container.querySelector("details")!;
    expect(details.open).toBe(false);
    expect(screen.getByText("Removed from the argument (2 sentences)")).toBeTruthy();
    const items = screen.getAllByTestId("withheld-sentence");
    expect(items).toHaveLength(2);
    expect(within(items[0]).getByText(G5.sentences[0].sentence)).toBeTruthy();
    expect(within(items[0]).getByText("The record is silent on trial delay.")).toBeTruthy();
    expect(within(items[1]).getByText("The cited paragraph does not say this.")).toBeTruthy();
    expect(container.textContent).not.toMatch(/0\.22|entailment/);
  });

  it("renders nothing when nothing was removed", () => {
    const { container } = render(<RemovedSentences group={null} />);
    expect(container.innerHTML).toBe("");
    const empty = render(<RemovedSentences group={{ ...G5, sentences: [] }} />);
    expect(empty.container.innerHTML).toBe("");
  });
});

describe("DroppedGrounds", () => {
  it("lists each ground left for counsel under its factor, with the removed sentences open", () => {
    render(<DroppedGrounds groups={droppedGrounds(MOCK_BRIEF)} />);
    expect(screen.getByRole("heading", { name: "Grounds left for you to draft" })).toBeTruthy();
    const row = screen.getByTestId("dropped-ground");
    expect(row.getAttribute("data-ground")).toBe("G8");
    expect(within(row).getByText("Weak prima facie case")).toBeTruthy();
    expect(within(row).getAllByTestId("withheld-sentence")).toHaveLength(2);
    expect(within(row).getByText("Not supported by the record.")).toBeTruthy();
    expect(within(row).getByText("The record is silent on weak prima facie case.")).toBeTruthy();
  });

  it("renders nothing when every ground kept a sentence", () => {
    const { container } = render(<DroppedGrounds groups={[]} />);
    expect(container.innerHTML).toBe("");
  });
});
