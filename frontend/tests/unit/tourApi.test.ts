// The guided-demo routes in the API client: GET /api/demo/tours and /api/demo/tours/{slug}. A server with demos off answers
// 404 (or an empty list): no tours, and an unknown slug is null, never an error page. fetch is mocked; no network.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const BASE = "http://localhost:8000";
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetchMock = vi.fn(async () => json([]));
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllEnvs();
});

async function loadApi() {
  vi.resetModules();
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  return import("@/lib/api");
}

const SUMMARY = {
  slug: "01-cheating-parity", case_id: "case-demo-01", title: "Demo · Cheating", story: "Story.",
  variant: { offence: "Cheating", custody: "167 days", record: "Clean", parity: "Co-accused on bail" },
};

describe("listTours", () => {
  it("GET /api/demo/tours and keeps the usable entries", async () => {
    fetchMock.mockResolvedValueOnce(json([SUMMARY, { title: "no slug" }]));
    const api = await loadApi();
    const out = await api.listTours();
    expect(String(fetchMock.mock.calls.at(-1)?.[0])).toBe(`${BASE}/api/demo/tours`);
    expect(out).toEqual([SUMMARY]);
  });

  it("is empty when demos are off (404 or an empty list)", async () => {
    const api = await loadApi();
    fetchMock.mockResolvedValueOnce(json({ detail: "Not Found" }, 404));
    expect(await api.listTours()).toEqual([]);
    fetchMock.mockResolvedValueOnce(json([]));
    expect(await api.listTours()).toEqual([]);
  });

  it("passes other errors on (the cases page then shows no demos)", async () => {
    const api = await loadApi();
    fetchMock.mockResolvedValueOnce(json({ detail: "nope" }, 403));
    await expect(api.listTours()).rejects.toMatchObject({ status: 403 });
  });
});

describe("getTour", () => {
  it("GET /api/demo/tours/{slug}, with the steps in workflow order", async () => {
    fetchMock.mockResolvedValueOnce(json({
      ...SUMMARY,
      steps: [
        { stage: "FILE", tab: "prep", title: "Export", caption: "c", agent: null, filled: [], action: null },
        { stage: "INTAKE", tab: "dossier", title: "Papers", caption: "c", agent: "MUNSHI", filled: [], action: null },
      ],
    }));
    const api = await loadApi();
    const tour = await api.getTour("01 cheating/parity");
    expect(String(fetchMock.mock.calls.at(-1)?.[0])).toBe(`${BASE}/api/demo/tours/01%20cheating%2Fparity`);
    expect(tour?.steps.map((s) => s.stage)).toEqual(["INTAKE", "FILE"]);
  });

  it("is null for an unknown slug", async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: "No tour" }, 404));
    const api = await loadApi();
    expect(await api.getTour("missing")).toBeNull();
  });
});

describe("the demo build", () => {
  it("serves one tour over case-0007 and 404s an unknown slug", async () => {
    const demo = await import("@/lib/mock/server");
    const { parseTourList, parseTour } = await import("@/lib/tour");
    const list = parseTourList(await demo.listTours());
    expect(list).toHaveLength(1);
    expect(list[0].case_id).toBe("case-0007");
    expect(parseTour(await demo.getTour(list[0].slug))?.steps).toHaveLength(9);
    await expect(demo.getTour("missing")).rejects.toMatchObject({ status: 404 });
  });
});
