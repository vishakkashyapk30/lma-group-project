import { defineConfig, devices } from "@playwright/test";

// E2E (plan §13.7: Playwright runs flows 1-7, axe-core, reduced-motion path). The backend is mocked in every spec with
// page.route (e2e/mockBackend.ts), so only the Next dev server is started.
// E2E_PORT lets a second checkout run its own dev server without reusing another one on 3000.
const PORT = Number(process.env.E2E_PORT ?? 3000);

export default defineConfig({
  testDir: "e2e",
  testMatch: /.*\.spec\.ts/,
  retries: 0,
  fullyParallel: true,
  reporter: [["list"]],
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "on-first-retry",
  },
  webServer: {
    command: `npx next dev -p ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: true,
    timeout: 120_000,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    {
      // Re-runs the workspace and the dedicated reduced-motion spec with prefers-reduced-motion: reduce (plan §13.7).
      name: "reduced-motion",
      testMatch: /(workspace|reduced-motion)\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], contextOptions: { reducedMotion: "reduce" } },
    },
  ],
});
