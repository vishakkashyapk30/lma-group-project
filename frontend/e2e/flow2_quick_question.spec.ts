/**
 * Plan §13.6 flow 2: quick questions. At any point counsel asks the chat and gets a short, cited answer with store/tool chips
 * (plan §13.5 centre pane, §6.4). Requests for outcome predictions or lay advice are refused and show no chips and no probability.
 * The backend is mocked (e2e/mockBackend.ts); the answer text and chips come from e2e/fixtures/chat_message.json.
 *
 * RECONCILED (docs/handoff/workspace-redesign.md): the chat is a drawer opened from the case header (chat-button), not a
 * centre pane; it may already hold Munshi's question about the file, so the new exchange is counted from the moment counsel asks.
 */
import { expect, test } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { expectNoUnmatched } from "./helpers";
import { fx } from "./fixtures";
import { TID } from "./testids";

const QUESTION = "How many days in custody?";

async function openChat(page: import("@playwright/test").Page) {
  await page.getByTestId(TID.chatButton).click();
  await expect(page.getByTestId(TID.paneChat)).toBeVisible();
}

async function ask(page: import("@playwright/test").Page, text: string) {
  if (!(await page.getByTestId(TID.paneChat).isVisible().catch(() => false))) await openChat(page);
  await page.getByTestId(TID.chatInput).fill(text);
  await page.getByTestId(TID.chatSend).click();
}

test("flow 2: a custody question gets a one-line cited answer with tool chips", async ({ page }) => {
  const mock = await MockBackend.install(page, { gate1Approved: true });
  await page.goto("/case/case-0007");

  await openChat(page);
  const messages = page.getByTestId(TID.paneChat).getByTestId(TID.chatMessage);
  const before = await messages.count();
  await ask(page, QUESTION);
  await expect.poll(() => mock.chatCalls).toEqual([QUESTION]);

  await expect(messages).toHaveCount(before + 2);
  const roles = await messages.evaluateAll((els) => els.map((e) => e.getAttribute("data-role")));
  expect(roles.slice(-2)).toEqual(["counsel", "agent"]);

  const answer = messages.nth(before + 1);
  const expected = fx.chatMessage();
  await expect(answer).toContainText("Custody: 167 days");
  await expect(answer).toContainText("date_calc");
  await expect(answer).toHaveAttribute("data-agent", expected.agent as string);

  const chips = answer.getByTestId(TID.toolChip);
  await expect(chips).toHaveCount(expected.chips.length);
  const names = await chips.evaluateAll((els) => els.map((e) => (e.textContent ?? "").trim()));
  expect(names.join(" ")).toContain("date_calc");
  await expectNoUnmatched(mock);
});

test("flow 2: counsel can ask before Gate 1 is approved ('at any point')", async ({ page }) => {
  const mock = await MockBackend.install(page, { gate1Approved: false });
  await page.goto("/case/case-0007");
  await ask(page, QUESTION);
  await expect.poll(() => mock.chatCalls.length).toBe(1);
  await expect(page.getByTestId(TID.chatMessage).filter({ hasText: "Custody: 167 days" })).toHaveCount(1);
});

test("flow 2: an outcome prediction request is refused, with no chips and no probability", async ({ page }) => {
  const mock = await MockBackend.install(page, { gate1Approved: true });
  // Registered after the mock, so it answers chat POSTs first.
  await page.route("**/api/cases/*/chat", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    mock.chatCalls.push((route.request().postDataJSON() as { text: string }).text);
    return route.fulfill({
      status: 200,
      headers: { "access-control-allow-origin": "*" },
      contentType: "application/json",
      body: JSON.stringify({
        message_id: "m-900", case_id: "case-0007", role: "agent", agent: "SUTRADHAR", chips: [], refused: true,
        text: "I can't predict outcomes or give grant rates. I can show the reasoning courts gave in comparable orders.",
      }),
    });
  });
  await page.goto("/case/case-0007");
  await ask(page, "Will my client get bail?");

  const answer = page.getByTestId(TID.chatMessage).filter({ hasText: "can't predict outcomes" });
  await expect(answer).toHaveCount(1);
  await expect(answer.getByTestId(TID.toolChip)).toHaveCount(0);
  const text = (await answer.textContent()) ?? "";
  expect(text).not.toMatch(/\d+(\.\d+)?\s*%/);
});

test("flow 2: the chat input is reachable by keyboard and Enter-free send button has an accessible name", async ({ page }) => {
  await MockBackend.install(page, { gate1Approved: true });
  await page.goto("/case/case-0007");
  await openChat(page);
  await page.getByTestId(TID.chatInput).focus();
  await expect(page.getByTestId(TID.chatInput)).toBeFocused();
  await expect(page.getByTestId(TID.chatSend)).toBeVisible();
  const name = await page.getByTestId(TID.chatSend).evaluate((el) => (el.getAttribute("aria-label") ?? el.textContent ?? "").trim());
  expect(name.length).toBeGreaterThan(0);
});
