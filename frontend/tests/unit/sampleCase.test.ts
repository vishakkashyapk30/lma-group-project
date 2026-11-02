import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("lib/sampleCase agrees with lib/api on the mode (without importing it)", () => {
  for (const env of [{}, { NEXT_PUBLIC_API_MODE: "live" }, { NEXT_PUBLIC_API_MODE: "demo" }, { NEXT_PUBLIC_API_MODE: "auto" }, { NEXT_PUBLIC_DEMO_FALLBACK: "strict" }, { NODE_ENV: "production" }]) {
    it(JSON.stringify(env), async () => {
      vi.resetModules();
      for (const [k, v] of Object.entries(env)) vi.stubEnv(k, v as string);
      const api = await import("@/lib/api");
      const sample = await import("@/lib/sampleCase");
      expect(sample.SAMPLE_CASE_OPENS).toBe(api.API_SETTING !== "live");
      expect(sample.sampleCaseHref("/cases")).toBe(api.API_SETTING !== "live" ? "/case/case-0007" : "/cases");
    });
  }
});
