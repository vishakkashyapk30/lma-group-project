/** Library page smoke (plan §13.5 /library, flow 7): precedent search and the IPC<->BNS bridge are present and accessible. */
import { expect, test } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { seriousAxeViolations } from "./helpers";
import { TID } from "./testids";

test("library exposes the precedent search and the IPC-BNS bridge view", async ({ page }) => {
  const mock = await MockBackend.install(page);
  await page.goto("/library");
  await expect(page.getByTestId(TID.librarySearch)).toBeVisible();
  await expect(page.getByTestId(TID.bridgeView)).toBeVisible();
  expect(await seriousAxeViolations(page)).toEqual([]);
  expect(mock.unmatched).toEqual([]);
});
