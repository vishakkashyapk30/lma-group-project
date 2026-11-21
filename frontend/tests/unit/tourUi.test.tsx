// Guided demos in the interface: the list on the cases page (title, story, the four facets, a start link into tour mode;
// nothing at all when the server has no demos) and the tour bar in the workspace (step k of n, caption, filled fields, Next
// moving the workspace, the Gate 2 approval sent once, an unknown slug, the keyboard).
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TOUR_STAGES } from "@/lib/tour";

const apiMock = vi.hoisted(() => ({
  listTours: vi.fn(),
  getTour: vi.fn(),
  approveGate: vi.fn(),
  getGate: vi.fn(),
}));
vi.mock("@/lib/api", () => apiMock);

const nav = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: nav.replace, push: vi.fn() }),
  usePathname: () => "/case/case-demo-01",
}));

const wsState = vi.hoisted(() => ({
  gate1: true,
  gate2: false,
  setStage: vi.fn(() => true),
  refresh: vi.fn(async () => {}),
  exportCase: vi.fn(async () => ["/api/cases/case-demo-01/export/files/application.docx"]),
  exports: [] as string[],
}));
vi.mock("@/lib/workspace", () => ({
  useWorkspace: () => ({
    loading: { summary: false, gates: false },
    setStage: wsState.setStage,
    refresh: wsState.refresh,
    exportCase: wsState.exportCase,
    exports: wsState.exports,
    gates: {
      approvals: { gate1: wsState.gate1, gate2: wsState.gate2 },
      checklists: {
        GATE_2_EXPORT: {
          items: [
            { kind: "NEEDS_REVIEW", key: "NEEDS_REVIEW:G5", ref: "G5" },
            { kind: "UNANSWERED", key: "UNANSWERED:O2", ref: "O2" },
            { kind: "UNSUPPORTED", key: "UNSUPPORTED:antecedents", ref: "antecedents" },
          ],
        },
      },
    },
  }),
}));

import { GuidedDemos, tourHref } from "@/components/tour/GuidedDemos";
import { TourBar } from "@/components/tour/TourBar";

const SUMMARY = {
  slug: "01-cheating-parity", case_id: "case-demo-01", title: "Demo · Cheating with parity", story: "Accused-1 is in custody.",
  variant: { offence: "Cheating, BNS 318(4)", custody: "167 days", record: "Clean scans", parity: "Co-accused on bail" },
};

const TOUR = {
  ...SUMMARY,
  recorded: { date: "2026-11-14", backend: "sarvam", model: "sarvam-m", cost_inr: 1 },
  steps: TOUR_STAGES.map((stage) => ({
    stage,
    tab: stage === "RIGHTS" ? "rights" : "dossier",
    title: `Title ${stage}`,
    caption: `Caption for ${stage}.`,
    agent: stage === "INTAKE" ? "MUNSHI" : null,
    filled: stage === "DOSSIER" ? [{ label: "Counsel's answer", value: "No other pending case" }] : [],
    action: stage === "GATE_2" ? "approve_gate_2" : null,
  })),
};

beforeEach(() => {
  vi.clearAllMocks();
  wsState.gate1 = true;
  wsState.gate2 = false;
  wsState.setStage.mockImplementation(() => true);
  apiMock.getTour.mockResolvedValue(TOUR);
  apiMock.approveGate.mockImplementation(async () => {
    wsState.gate2 = true;
    return { gate: "GATE_2_EXPORT", open: false };
  });
  apiMock.getGate.mockResolvedValue({ gate: "GATE_2_EXPORT", open: true });
});

describe("GuidedDemos", () => {
  it("lists each tour with its title, story and four facets, and starts it in tour mode", async () => {
    apiMock.listTours.mockResolvedValue([SUMMARY]);
    render(<GuidedDemos />);
    expect(await screen.findByRole("heading", { name: "Guided demos" })).toBeTruthy();
    expect(screen.getByText(SUMMARY.title)).toBeTruthy();
    expect(screen.getByText(SUMMARY.story)).toBeTruthy();
    for (const v of Object.values(SUMMARY.variant)) expect(screen.getByText(v)).toBeTruthy();
    for (const label of ["Offence and law:", "Custody and rights:", "Record quality:", "Parity and history:"]) expect(screen.getByText(label)).toBeTruthy();
    const start = screen.getByTestId("guided-demo-start");
    expect(start.getAttribute("href")).toBe("/case/case-demo-01?tour=01-cheating-parity");
    expect(tourHref({ slug: "a b", case_id: "c/1" })).toBe("/case/c%2F1?tour=a%20b");
  });

  it("shows nothing when there are no demos or the request fails", async () => {
    apiMock.listTours.mockResolvedValueOnce([]);
    const { container, unmount } = render(<GuidedDemos />);
    await waitFor(() => expect(apiMock.listTours).toHaveBeenCalled());
    expect(container.innerHTML).toBe("");
    unmount();
    apiMock.listTours.mockRejectedValueOnce(new Error("down"));
    const second = render(<GuidedDemos />);
    await waitFor(() => expect(apiMock.listTours).toHaveBeenCalledTimes(2));
    expect(second.container.innerHTML).toBe("");
  });
});

describe("TourBar", () => {
  const renderBar = async () => {
    render(<TourBar slug="01-cheating-parity" caseId="case-demo-01" />);
    await screen.findByTestId("tour-step");
  };
  const progress = () => screen.getByTestId("tour-progress").textContent;
  const clickNext = async () => {
    await act(async () => {
      fireEvent.click(screen.getByTestId("tour-next"));
    });
  };

  it("shows step 1 of 9 with the caption (read out politely), the agent, and moves the workspace", async () => {
    await renderBar();
    expect(progress()).toBe("Step 1 of 9");
    expect(screen.getByTestId("tour-caption").textContent).toBe("Caption for INTAKE.");
    expect(screen.getByTestId("tour-caption").closest("[aria-live]")?.getAttribute("aria-live")).toBe("polite");
    expect(screen.getByTestId("tour-agent").textContent).toMatch(/Munshi/);
    expect(wsState.setStage).toHaveBeenLastCalledWith("INTAKE");
    expect((screen.getByTestId("tour-back") as HTMLButtonElement).disabled).toBe(true);
    expect(document.activeElement).toBe(screen.getByTestId("tour-next"));
  });

  it("walks every step with Next, shows the filled fields, opens the gates in their steps, and approves Gate 2 once", async () => {
    await renderBar();
    await clickNext();
    expect(progress()).toBe("Step 2 of 9");
    expect(wsState.setStage).toHaveBeenLastCalledWith("DOSSIER");
    const field = screen.getByTestId("tour-field");
    expect(field.textContent).toContain("Counsel's answer");
    expect(field.textContent).toContain("No other pending case");
    await clickNext();
    expect(screen.getByTestId("tour-gate").getAttribute("data-approved")).toBe("true");
    expect(wsState.setStage).toHaveBeenLastCalledWith("DOSSIER");
    for (let i = 0; i < 4; i++) await clickNext();
    expect(progress()).toBe("Step 7 of 9");
    await clickNext();
    expect(progress()).toBe("Step 8 of 9");
    expect(wsState.setStage).toHaveBeenLastCalledWith("FILE");
    expect(screen.getByTestId("tour-next").textContent).toMatch(/Approve and continue/);
    expect(apiMock.approveGate).not.toHaveBeenCalled();
    await clickNext();
    await waitFor(() => expect(progress()).toBe("Step 9 of 9"));
    expect(apiMock.approveGate).toHaveBeenCalledTimes(1);
    expect(apiMock.approveGate).toHaveBeenCalledWith("case-demo-01", "GATE_2_EXPORT", ["NEEDS_REVIEW:G5", "UNANSWERED:O2", "antecedents"]);
    expect(wsState.refresh).toHaveBeenCalledWith(["summary", "gates"]);
    expect(screen.getByTestId("tour-next").textContent).toMatch(/Finish/);
    // The last step exports by itself once Gate 2 is approved, once, so the evaluator only finds the download links.
    await waitFor(() => expect(wsState.exportCase).toHaveBeenCalledWith("DOCX"));
    expect(wsState.exportCase).toHaveBeenCalledTimes(1);
    // Back to the gate and on again: the gate is approved, nothing is sent twice.
    await act(async () => {
      fireEvent.click(screen.getByTestId("tour-back"));
    });
    expect(screen.getByTestId("tour-gate").getAttribute("data-approved")).toBe("true");
    await clickNext();
    expect(apiMock.approveGate).toHaveBeenCalledTimes(1);
    // Finish leaves tour mode and stays in the case.
    await clickNext();
    expect(nav.replace).toHaveBeenCalledWith("/case/case-demo-01");
  });

  it("passes an already-approved Gate 2 without calling the route", async () => {
    wsState.gate2 = true;
    await renderBar();
    for (let i = 0; i < 8; i++) await clickNext();
    expect(progress()).toBe("Step 9 of 9");
    expect(apiMock.approveGate).not.toHaveBeenCalled();
    await waitFor(() => expect(wsState.exportCase).toHaveBeenCalledTimes(1));
  });

  it("stays on Gate 2 and shows the server's message when the approval is refused", async () => {
    apiMock.approveGate.mockRejectedValueOnce(new Error("2 checklist item(s) are unresolved."));
    await renderBar();
    for (let i = 0; i < 8; i++) await clickNext();
    await waitFor(() => expect(screen.getByTestId("tour-error").textContent).toBe("2 checklist item(s) are unresolved."));
    expect(progress()).toBe("Step 8 of 9");
  });

  it("says so for an unknown slug and offers to leave", async () => {
    apiMock.getTour.mockResolvedValueOnce(null);
    render(<TourBar slug="missing" caseId="case-demo-01" />);
    expect(await screen.findByText("This guided demo was not found.")).toBeTruthy();
    fireEvent.click(screen.getByTestId("tour-exit"));
    expect(nav.replace).toHaveBeenCalledWith("/case/case-demo-01");
  });

  it("points to the right case when the tour belongs to another one", async () => {
    render(<TourBar slug="01-cheating-parity" caseId="case-0007" />);
    expect(await screen.findByText("This guided demo belongs to another case.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Open its case" }).getAttribute("href")).toBe("/case/case-demo-01?tour=01-cheating-parity");
  });

  it("Right and Enter go on, Left goes back, Escape leaves; typing in a field does not move the tour", async () => {
    await renderBar();
    (document.activeElement as HTMLElement | null)?.blur();
    await act(async () => {
      fireEvent.keyDown(document.body, { key: "ArrowRight" });
    });
    expect(progress()).toBe("Step 2 of 9");
    await act(async () => {
      fireEvent.keyDown(document.body, { key: "Enter" });
    });
    expect(progress()).toBe("Step 3 of 9");
    await act(async () => {
      fireEvent.keyDown(document.body, { key: "ArrowLeft" });
    });
    expect(progress()).toBe("Step 2 of 9");
    const input = document.createElement("input");
    document.body.appendChild(input);
    await act(async () => {
      fireEvent.keyDown(input, { key: "ArrowRight" });
    });
    expect(progress()).toBe("Step 2 of 9");
    input.remove();
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(nav.replace).toHaveBeenCalledWith("/case/case-demo-01");
  });
});
