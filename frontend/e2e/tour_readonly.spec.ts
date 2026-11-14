/**
 * A guided demo must not change the shared recorded case (docs/handoff/evaluator-demo.md). Runs on the sample case with the API
 * unreachable (the demo backend answers; every request to localhost:8000 is aborted and counted): in tour mode every input,
 * editor, upload, dictation and chat control is disabled, a note says so, and an attempt to use them sends no request and
 * changes nothing; outside tour mode the same controls work.
 */
import { expect, test, type Page } from "@playwright/test";

const TOUR = "/case/case-0007?tour=00-sample-cheating-parity";

/** Requests the page tried to send to the API: any write is a failure. */
function watchApi(page: Page) {
  const seen: string[] = [];
  return {
    seen,
    install: async () => {
      await page.route("http://localhost:8000/**", (route) => {
        seen.push(`${route.request().method()} ${new URL(route.request().url()).pathname}`);
        return route.abort();
      });
    },
    writes: () => seen.filter((s) => !s.startsWith("GET ")),
  };
}

async function next(page: Page) {
  await page.getByTestId("tour-next").click();
  await page.waitForTimeout(350); // the step's slide settles
}


test("in tour mode the workspace is read-only: controls are disabled and an attempt sends nothing", async ({ page }) => {
  test.setTimeout(90_000);
  const api = watchApi(page);
  await api.install();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(TOUR);
  const bar = page.getByTestId("tour-bar");
  await expect(bar.getByTestId("tour-readonly")).toHaveText("This is a recorded demo; fields are read-only.");

  // Add documents: the drop zone, the file inputs and dictation are disabled.
  await expect(page.locator("#add-files")).toBeDisabled();
  await expect(page.getByTestId("upload-input")).toBeDisabled();
  await expect(page.getByTestId("mic-button")).toBeDisabled();
  await expect(page.getByRole("button", { name: "Upload audio" })).toBeDisabled();

  // Review facts: every Edit/Add button is disabled; forcing a click opens no editor.
  await next(page);
  const edits = page.getByTestId("dossier-field-edit");
  await expect(edits.first()).toBeVisible();
  const n = await edits.count();
  for (let i = 0; i < n; i++) await expect(edits.nth(i)).toBeDisabled();
  await edits.first().click({ force: true });
  await expect(page.getByTestId("dossier-field-save")).toHaveCount(0);
  const enabledFields = page.locator('[data-testid="pane-main"] :is(input:not([type=file]), textarea, select):not([disabled])');
  await expect(enabledFields).toHaveCount(0);
  await expect(page.getByTestId("confirm-facts-button")).toHaveCount(0);

  // The chat: the box, Send, attach and dictation are disabled.
  await page.getByTestId("chat-button").click();
  await expect(page.getByTestId("chat-input")).toBeDisabled();
  await expect(page.getByTestId("chat-send")).toBeDisabled();
  await expect(page.getByRole("button", { name: "Attach files to the case" })).toBeDisabled();
  await page.getByTestId("chat-input").click({ force: true });
  await page.keyboard.type("hello");
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("chat-input")).toHaveValue("");
  await page.getByTestId("chat-button").click();

  // Dates, grounds and objections: edit, reword and resolve controls are disabled.
  for (const [stage, selector] of [
    ["RIGHTS", null],
    ["BRIEF", 'button[aria-label^="Reword "], button[aria-label^="Accept "]'],
    ["SPAR", 'button[aria-label^="Resolve unanswered objection"]'],
  ] as const) {
    while ((await bar.getByTestId("tour-step").getAttribute("data-stage")) !== stage) await next(page);
    if (!selector) continue;
    const controls = page.locator(`[data-testid="pane-main"] ${selector}`);
    const count = await controls.count();
    for (let i = 0; i < count; i++) await expect(controls.nth(i)).toBeDisabled();
  }
  // Nothing was sent: no write of any kind reached the API.
  expect(api.writes(), "writes sent in tour mode").toEqual([]);
});

test("outside tour mode the same controls work", async ({ page }) => {
  await page.route("http://localhost:8000/**", (route) => route.abort());
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/case/case-0007");
  await page.getByTestId("stage-II").click();
  await expect(page.getByTestId("dossier-field-edit").first()).toBeEnabled();
  await page.getByTestId("chat-button").click();
  await expect(page.getByTestId("chat-input")).toBeEnabled();
  await expect(page.getByTestId("tour-readonly")).toHaveCount(0);
});

