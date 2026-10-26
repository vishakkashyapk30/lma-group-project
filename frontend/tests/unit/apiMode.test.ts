/**
 * Real-API mode (SA-02): NEXT_PUBLIC_API_MODE decides what the client does when the server cannot answer.
 * "live" (product builds) surfaces every failure as an ApiError and never answers from the sample cases; "auto" (development) falls back to
 * them for the session; "demo" never touches the network. fetch is mocked; no network.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type Api = typeof import("@/lib/api");

async function loadApi(env: Record<string, string>): Promise<Api> {
  vi.resetModules();
  vi.unstubAllEnvs();
  for (const [k, v] of Object.entries(env)) vi.stubEnv(k, v);
  return import("@/lib/api");
}

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetchMock = vi.fn(async () => json({}));
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllEnvs();
});

describe("API_SETTING", () => {
  it("is live in production builds and auto otherwise", async () => {
    expect((await loadApi({ NODE_ENV: "production" })).API_SETTING).toBe("live");
    expect((await loadApi({ NODE_ENV: "test" })).API_SETTING).toBe("auto");
  });
  it("follows NEXT_PUBLIC_API_MODE, and the older NEXT_PUBLIC_DEMO_FALLBACK=strict means live", async () => {
    expect((await loadApi({ NEXT_PUBLIC_API_MODE: "demo", NODE_ENV: "production" })).API_SETTING).toBe("demo");
    expect((await loadApi({ NEXT_PUBLIC_API_MODE: "auto", NODE_ENV: "production" })).API_SETTING).toBe("auto");
    expect((await loadApi({ NEXT_PUBLIC_DEMO_FALLBACK: "strict", NODE_ENV: "test" })).API_SETTING).toBe("live");
  });
});

describe("live mode never shows sample data", () => {
  it("a network failure rejects with a clear ApiError and stays live", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const m = await loadApi({ NEXT_PUBLIC_API_MODE: "live" });
    const err = await m.listCases().catch((e: unknown) => e);
    expect(err).toBeInstanceOf(m.ApiError);
    expect((err as InstanceType<Api["ApiError"]>).status).toBe(0);
    expect((err as Error).message).toMatch(/Cannot reach the server/);
    expect(m.getApiMode()).toBe("live");
    expect(m.getConnection()).toBe("down");
  });

  it("a 5xx rejects with an ApiError (no case-0007 in its place)", async () => {
    fetchMock.mockResolvedValue(json({ detail: "store missing" }, 500));
    const m = await loadApi({ NEXT_PUBLIC_API_MODE: "live" });
    const err = await m.getDossier("case-0042").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(m.ApiError);
    expect((err as InstanceType<Api["ApiError"]>).status).toBe(500);
    expect((err as Error).message).toMatch(/store missing/);
    expect(m.getApiMode()).toBe("live");
  });

  it("enterDemoMode is ignored, so the event stream cannot switch a live session to sample data", async () => {
    const m = await loadApi({ NEXT_PUBLIC_API_MODE: "live" });
    m.enterDemoMode("the event stream could not be opened");
    expect(m.getApiMode()).toBe("live");
  });

  it("the connection recovers once the server answers", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch")).mockResolvedValueOnce(json([]));
    const m = await loadApi({ NEXT_PUBLIC_API_MODE: "live" });
    await m.listCases().catch(() => undefined);
    expect(m.getConnection()).toBe("down");
    await m.listCases();
    expect(m.getConnection()).toBe("ok");
  });
});

describe("auto mode keeps the development fallback", () => {
  it("a network failure switches the session to the sample cases", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const m = await loadApi({ NEXT_PUBLIC_API_MODE: "auto" });
    const cases = await m.listCases();
    expect(m.getApiMode()).toBe("demo");
    expect(cases.some((c) => c.case_id === "case-0007")).toBe(true);
  });
});

describe("demo mode", () => {
  it("never calls the network", async () => {
    const m = await loadApi({ NEXT_PUBLIC_API_MODE: "demo" });
    await m.listCases();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(m.getApiMode()).toBe("demo");
  });
});

describe("getServerStatus", () => {
  it("reads GET /healthz", async () => {
    fetchMock.mockResolvedValueOnce(json({ status: "ok", api_implemented: true, models: "offline", external: "off" }));
    const m = await loadApi({ NEXT_PUBLIC_API_MODE: "live" });
    const s = await m.getServerStatus();
    expect(String(fetchMock.mock.calls[0][0])).toBe("http://localhost:8000/healthz");
    expect(s?.models).toBe("offline");
  });
  it("is null when the server does not answer in live mode, and in demo mode", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    expect(await (await loadApi({ NEXT_PUBLIC_API_MODE: "live" })).getServerStatus()).toBeNull();
    expect(await (await loadApi({ NEXT_PUBLIC_API_MODE: "demo" })).getServerStatus()).toBeNull();
  });
});

describe("normalizePrep (the backend's hearing card in the UI's shape)", () => {
  it("maps Vakeel's card: bench_concerns, ground ids, plain conditions with their sources", async () => {
    const m = await loadApi({ NEXT_PUBLIC_API_MODE: "live" });
    const card = m.normalizePrep({
      case_id: "case-0001", label: "AI-generated draft. Not legal advice.",
      bench_concerns: [{ factor: "parity_with_co_accused", concern: "Different role.", answer: "Same role on record.", ground: "G1", authority: "X v Y, para 14", source: "prosecution objection" }],
      lead_with: ["G2"], lead_points: [{ ground: "G2", factor: "custody_period", point: "167 days in custody.", check: "SUPPORTED" }],
      conditions: ["Surrender of passport"], condition_sources: [{ condition: "Surrender of passport", source: "DLHC-1#4" }],
      open_issues: ["Antecedents unknown."],
    });
    expect(card.likely_concerns[0]).toMatchObject({ concern: "Different role.", ground_id: "G1", authority: "X v Y, para 14", factor: "parity_with_co_accused" });
    expect(card.lead_points).toEqual([{ ground_id: "G2", point: "167 days in custody." }]);
    expect(card.conditions).toEqual([{ condition: "Surrender of passport", seen_in: ["DLHC-1#4"] }]);
    expect(card.open_issues).toEqual(["Antecedents unknown."]);
  });
  it("a concern that is only a paragraph number falls back to the factor", async () => {
    const m = await loadApi({ NEXT_PUBLIC_API_MODE: "live" });
    const card = m.normalizePrep({ bench_concerns: [{ factor: "witness_tampering", concern: "3.", answer: "a", ground: "G5" }], lead_points: [], conditions: [], open_issues: [] });
    expect(card.likely_concerns[0].concern).toBe("The bench may ask about witness tampering.");
  });
    it("passes a card in neither known shape through untouched", async () => {
    const m = await loadApi({ NEXT_PUBLIC_API_MODE: "live" });
    const other = { title: "Hearing prep card", likely_questions: ["Why?"] };
    expect(m.normalizePrep(other)).toBe(other);
  });
    it("leaves a card already in the UI's shape as it is", async () => {
    const m = await loadApi({ NEXT_PUBLIC_API_MODE: "live" });
    const ui = { case_id: "c", likely_concerns: [{ concern: "q", factor: "flight_risk", basis: "b", answer: "a", ground_id: "G1" }], lead_points: [{ ground_id: "G1", point: "p" }], conditions: [{ condition: "c", seen_in: ["s"] }], open_issues: [], label: "L" };
    expect(m.normalizePrep(ui)).toMatchObject(ui);
  });
});

describe("exportCase download links", () => {
  it("turns the server's file paths into GET .../export/files/{name} links", async () => {
    fetchMock.mockResolvedValueOnce(json(["/srv/data/cases/case-0001/export/application.docx", "/srv/data/cases/case-0001/export/hearing_card.docx"]));
    const m = await loadApi({ NEXT_PUBLIC_API_MODE: "live" });
    expect(await m.exportCase("case-0001")).toEqual([
      "http://localhost:8000/api/cases/case-0001/export/files/application.docx",
      "http://localhost:8000/api/cases/case-0001/export/files/hearing_card.docx",
    ]);
  });
});
