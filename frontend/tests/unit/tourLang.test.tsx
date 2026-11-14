// The tour in two languages: English by default; with the Hindi toggle the bar and the demo list show the optional `hi`
// text of the tour file (title, story, variant lines, caption, filled lines), field by field, with the English as the fallback
// where a field has no Hindi.
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "@/lib/i18n";
import { localizedStep, localizedTour, parseTour, parseTourList, TOUR_STAGES } from "@/lib/tour";

const apiMock = vi.hoisted(() => ({ listTours: vi.fn(), getTour: vi.fn(), approveGate: vi.fn(), getGate: vi.fn() }));
vi.mock("@/lib/api", () => apiMock);
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/case/case-demo-01",
}));
vi.mock("@/lib/workspace", () => ({
  useWorkspace: () => ({
    loading: { summary: false, gates: false },
    setStage: () => true,
    refresh: async () => {},
    gates: { approvals: { gate1: true, gate2: false }, checklists: { GATE_2_EXPORT: { items: [] } } },
  }),
}));

import { GuidedDemos } from "@/components/tour/GuidedDemos";
import { TourBar } from "@/components/tour/TourBar";

const HI_TOUR = { title: "डेमो · धोखाधड़ी", story: "अभियुक्त-1 हिरासत में है।", variant: { offence: "धोखाधड़ी, BNS 318(4)", custody: "167 दिन" }, src: { title: "abc" } };
const HI_STEP = { title: "शीर्षक INTAKE", caption: "INTAKE का विवरण: 11 PDF।", filled: [{ label: "सलाहकार का उत्तर", value: "कोई अन्य मामला नहीं" }], src: { caption: "x" } };

const base = {
  slug: "01-cheating-parity", case_id: "case-demo-01", title: "Demo · Cheating with parity", story: "Accused-1 is in custody.",
  variant: { offence: "Cheating, BNS 318(4)", custody: "167 days", record: "Clean scans", parity: "Co-accused on bail" },
  recorded: { date: "2026-11-14", backend: "sarvam", model: "sarvam-m", cost_inr: 1 },
  steps: TOUR_STAGES.map((stage) => ({
    stage, tab: "dossier", title: `Title ${stage}`, caption: `Caption for ${stage}.`, agent: null,
    filled: [{ label: "Counsel's answer", value: "No other pending case" }], action: stage === "GATE_2" ? "approve_gate_2" : null,
    ...(stage === "INTAKE" ? { hi: HI_STEP } : {}),
  })),
};

function renderIn(lang: "en" | "hi", ui: React.ReactElement) {
  window.localStorage.setItem("vs-lang", lang);
  return render(<I18nProvider>{ui}</I18nProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});
afterEach(() => window.localStorage.clear());

describe("parsing the optional Hindi text", () => {
  it("keeps hi on the tour and the steps, and ignores a malformed or empty hi", () => {
    const tour = parseTour({ ...base, hi: HI_TOUR })!;
    expect(tour.hi?.title).toBe("डेमो · धोखाधड़ी");
    expect(tour.hi?.variant).toEqual({ offence: "धोखाधड़ी, BNS 318(4)", custody: "167 दिन" });
    expect(tour.steps[0].hi?.caption).toBe("INTAKE का विवरण: 11 PDF।");
    expect(tour.steps[1].hi).toBeUndefined();
    expect(parseTour({ ...base, hi: "x", steps: base.steps.map((s) => ({ ...s, hi: { title: "", filled: "no" } })) })!.hi).toBeUndefined();
    expect(parseTourList([{ ...base, hi: HI_TOUR }])[0].hi?.story).toBe("अभियुक्त-1 हिरासत में है।");
  });

  it("falls back to English field by field", () => {
    const tour = parseTour({ ...base, hi: HI_TOUR })!;
    expect(localizedTour(tour, "en").title).toBe(base.title);
    const hi = localizedTour(tour, "hi");
    expect(hi.title).toBe(HI_TOUR.title);
    expect(hi.variant).toEqual({ offence: HI_TOUR.variant.offence, custody: HI_TOUR.variant.custody, record: "Clean scans", parity: "Co-accused on bail" });
    expect(localizedStep(tour.steps[1], "hi").caption).toBe("Caption for DOSSIER.");
    expect(localizedStep(tour.steps[0], "hi").filled).toEqual([{ label: "सलाहकार का उत्तर", value: "कोई अन्य मामला नहीं" }]);
    expect(localizedStep(tour.steps[0], "en").title).toBe("Title INTAKE");
  });
});

describe("the demo list", () => {
  it("shows English by default and the Hindi text, with an English fallback per line, in Hindi", async () => {
    apiMock.listTours.mockResolvedValue([parseTourList([{ ...base, hi: HI_TOUR }])[0]]);
    const en = renderIn("en", <GuidedDemos />);
    expect(await screen.findByText(base.title)).toBeTruthy();
    expect(screen.getByText(base.story)).toBeTruthy();
    en.unmount();
    renderIn("hi", <GuidedDemos />);
    expect(await screen.findByText(HI_TOUR.title)).toBeTruthy();
    expect(screen.getByText(HI_TOUR.story)).toBeTruthy();
    expect(screen.getByText(HI_TOUR.variant.offence)).toBeTruthy();
    expect(screen.getByText("Clean scans")).toBeTruthy(); // no Hindi for this line: the English shows
    expect(screen.queryByText(base.title)).toBeNull();
  });

  it("shows the English in Hindi mode when the tour has no hi at all", async () => {
    apiMock.listTours.mockResolvedValue(parseTourList([base]));
    renderIn("hi", <GuidedDemos />);
    expect(await screen.findByText(base.title)).toBeTruthy();
    expect(screen.getByText(base.story)).toBeTruthy();
  });
});

describe("the tour bar", () => {
  it("shows the English text by default", async () => {
    apiMock.getTour.mockResolvedValue(parseTour({ ...base, hi: HI_TOUR }));
    renderIn("en", <TourBar slug={base.slug} caseId={base.case_id} />);
    expect((await screen.findByTestId("tour-caption")).textContent).toBe("Caption for INTAKE.");
    expect(screen.getByRole("heading", { name: "Title INTAKE" })).toBeTruthy();
    expect(screen.getByText("No other pending case")).toBeTruthy();
  });

  it("shows the Hindi title, caption and filled lines when the step has them", async () => {
    apiMock.getTour.mockResolvedValue(parseTour({ ...base, hi: HI_TOUR }));
    renderIn("hi", <TourBar slug={base.slug} caseId={base.case_id} />);
    expect((await screen.findByTestId("tour-caption")).textContent).toBe(HI_STEP.caption);
    expect(screen.getByRole("heading", { name: HI_STEP.title })).toBeTruthy();
    expect(screen.getByText("कोई अन्य मामला नहीं")).toBeTruthy();
    expect(screen.getByText("सलाहकार का उत्तर")).toBeTruthy();
  });

  it("shows the English caption in Hindi mode when the step has no hi", async () => {
    apiMock.getTour.mockResolvedValue(parseTour({ ...base, steps: base.steps.map(({ hi: _hi, ...s }: { hi?: unknown }) => s) }));
    renderIn("hi", <TourBar slug={base.slug} caseId={base.case_id} />);
    expect((await screen.findByTestId("tour-caption")).textContent).toBe("Caption for INTAKE.");
    expect(screen.getByText("No other pending case")).toBeTruthy();
  });
});
