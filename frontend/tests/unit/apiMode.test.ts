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
