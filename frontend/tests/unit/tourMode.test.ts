// Read-only tour mode: while a guided demo runs (?tour=<slug> on a case page) the API client refuses every write except the
// tour's own two (Gate 2 approve, export), with a clear message; outside a tour nothing is blocked. fetch is mocked; no network.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetchMock = vi.fn(async () => json({}));
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllEnvs();
  window.history.replaceState(null, "", "/");
});

async function load() {
  vi.resetModules();
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  const tourMode = await import("@/lib/tourMode");
  const api = await import("@/lib/api");
  return { api, tourMode };
}

describe("tourAllows", () => {
  it("allows reads and exactly the Gate 2 approval and the export", async () => {
    const { tourMode } = await load();
    const ok = tourMode.tourAllows;
    expect(ok("GET", "/api/cases/c1/dossier")).toBe(true);
    expect(ok("POST", "/api/cases/c1/gates/GATE_2_EXPORT/approve")).toBe(true);
    expect(ok("POST", "/api/cases/c1/export")).toBe(true);
    expect(ok("POST", "/api/cases/c1/gates/GATE_1_DOSSIER/approve")).toBe(false);
    expect(ok("POST", "/api/cases/c1/chat")).toBe(false);
    expect(ok("POST", "/api/cases/c1/upload")).toBe(false);
    expect(ok("POST", "/api/cases/c1/audio")).toBe(false);
    expect(ok("POST", "/api/cases/c1/gates/answers")).toBe(false);
    expect(ok("POST", "/api/cases/c1/draft")).toBe(false);
    expect(ok("POST", "/api/cases")).toBe(false);
    expect(ok("PATCH", "/api/cases/c1/dossier/bail_status")).toBe(false);
    expect(ok("PUT", "/api/cases/c1/export")).toBe(false);
    expect(ok("DELETE", "/api/cases/c1")).toBe(false);
    expect(ok("POST", "/api/demo/tours/x/reset")).toBe(false);
  });
});

describe("the API client in tour mode", () => {
  it("refuses each write with a 423 and a clear message, sending nothing", async () => {
    const { api, tourMode } = await load();
    tourMode.setTourMode(true);
    const calls: Array<() => Promise<unknown>> = [
      () => api.editField("c1", "bail_status", "x"),
      () => api.createCase("t"),
      () => api.startDraft("c1"),
      () => api.uploadFiles("c1", [new File(["x"], "a.pdf")]),
      () => api.uploadAudio("c1", new Blob(["x"])),
      () => api.answerCounselQuestion("c1", "q", "a"),
      () => api.confirmDictationReadback("c1", ["x"]),
      () => api.postChat("c1", "hello"),
      () => api.approveGate("c1", "GATE_1_DOSSIER", []),
      () => api.deskUpload(new File(["x"], "a.zip")),
      () => api.openDeskCase("c1"),
    ];
    for (const run of calls) {
      await expect(run()).rejects.toMatchObject({ status: 423, message: tourMode.TOUR_REFUSED_MESSAGE });
    }
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("lets the tour's own Gate 2 approval and the export through, and reads", async () => {
    const { api, tourMode } = await load();
    tourMode.setTourMode(true);
    fetchMock.mockResolvedValueOnce(json({ gate: "GATE_2_EXPORT", open: false }));
    await api.approveGate("c1", "GATE_2_EXPORT", ["a"]);
    expect(fetchMock.mock.calls.at(-1)?.[1]).toMatchObject({ method: "POST" });
    expect(String(fetchMock.mock.calls.at(-1)?.[0])).toContain("/gates/GATE_2_EXPORT/approve");
    fetchMock.mockResolvedValueOnce(json(["/data/a.docx"]));
    await api.exportCase("c1", "DOCX");
    expect(String(fetchMock.mock.calls.at(-1)?.[0])).toMatch(/\/api\/cases\/c1\/export$/);
    fetchMock.mockResolvedValueOnce(json({ fields: {} }));
    await api.getDossier("c1");
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("refuses in the in-browser demo backend too (no network involved)", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "demo");
    const { api, tourMode } = await load();
    tourMode.setTourMode(true);
    await expect(api.editField("case-0007", "bail_status", "x")).rejects.toMatchObject({ status: 423 });
    await expect(api.postChat("case-0007", "hi")).rejects.toMatchObject({ status: 423 });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("blocks nothing outside tour mode", async () => {
    const { api, tourMode } = await load();
    expect(tourMode.isTourMode()).toBe(false);
    fetchMock.mockImplementation(async () => json({ fields: {}, case_id: "c1", checks: [] }));
    await api.editField("c1", "bail_status", "x");
    await api.approveGate("c1", "GATE_1_DOSSIER", []);
    await api.postChat("c1", "hello");
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("reads tour mode from the URL on a case page, and not elsewhere", async () => {
    const { tourMode } = await load();
    window.history.replaceState(null, "", "/case/c1?tour=01-cheating-parity");
    expect(tourMode.isTourMode()).toBe(true);
    window.history.replaceState(null, "", "/case/c1");
    expect(tourMode.isTourMode()).toBe(false);
    window.history.replaceState(null, "", "/cases?tour=x");
    expect(tourMode.isTourMode()).toBe(false);
    tourMode.setTourMode(null);
  });
});
