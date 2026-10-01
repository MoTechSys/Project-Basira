import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const TYPO = "قال تعالى: إن الله علي كل شيء قدير. وقال ﷺ: «إنما الأعمال بالنيات» رواه مسلم";

test("rtl shell, real check against the backend, axe clean", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", "ar");
  await expect(page.getByText("جاهز")).toBeVisible({ timeout: 45_000 });
  await page.locator("#text").fill(TYPO);
  await page.getByRole("button", { name: "افحص" }).click();
  // results workspace (E-042): both quotes highlighted IN the user's text; the panel shows the selected one
  // 3 highlights: the ayah, the matn, and its claimed source «رواه مسلم» (dotted, no tint)
  const hls = page.locator(".hl:not([data-seg='claimed_source']):not([data-seg='isnad'])");
  // real providers (LLM extraction) can take >5 s; the backend caps at PROVIDER_TIMEOUT
  await expect(hls).toHaveCount(2, { timeout: 45_000 });
  await expect(page.locator(".hl[data-seg='claimed_source']")).toHaveText("رواه مسلم");
  await expect(hls.nth(0)).toHaveAttribute("data-status", "needs_review");
  await expect(hls.nth(1)).toHaveAttribute("data-status", "found");
  // the annotated block is the input, character for character
  expect(await page.locator(".annotated").evaluate((el) => el.textContent)).toBe(TYPO);
  // desktop: the attention quote is pre-selected; clicking the other switches the panel
  const badge = page.getByRole("status");
  await expect(badge).toHaveCount(1);
  await expect(badge).toContainText("يحتاج مراجعة");
  await hls.nth(1).click();
  await expect(badge).toContainText("وُجد");
  await hls.nth(0).click();
  await expect(badge).toContainText("يحتاج مراجعة");
  // the user's typo is highlighted, and the source pane is byte-exact Uthmani text (no transform)
  await expect(page.locator("mark.d-quote").first()).toHaveText("علي");
  const src = page.getByTestId("source-text").first();
  const style = await src.evaluate((el) => ({ ls: getComputedStyle(el).letterSpacing, tt: getComputedStyle(el).textTransform }));
  expect(style).toEqual({ ls: "normal", tt: "none" });
  // targets ≥ 24px (WCAG 2.2 SC 2.5.8)
  for (const b of await page.locator("button, a").all()) {
    const box = await b.boundingBox();
    if (box) expect(Math.min(box.width, box.height)).toBeGreaterThanOrEqual(24);
  }
  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  expect(axe.violations, JSON.stringify(axe.violations.map((v) => [v.id, v.nodes.length]), null, 1)).toEqual([]);
  await page.screenshot({ path: "e2e/screenshot-ar.png", fullPage: true });
  // language switch flips direction
  await page.getByRole("button", { name: "English" }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
});

test("mobile: highlight opens a bottom sheet; Escape closes and restores focus", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByText("جاهز")).toBeVisible({ timeout: 45_000 });
  await page.locator("#text").fill(TYPO);
  await page.getByRole("button", { name: "افحص" }).click();
  const hls = page.locator(".hl:not([data-seg='claimed_source']):not([data-seg='isnad'])");
  await expect(hls).toHaveCount(2, { timeout: 45_000 });
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await hls.nth(1).click();
  const sheet = page.getByRole("dialog");
  await expect(sheet).toBeVisible();
  await expect(sheet.getByRole("status")).toContainText("وُجد");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(hls.nth(1)).toBeFocused();
  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  expect(axe.violations, JSON.stringify(axe.violations.map((v) => [v.id, v.nodes.length]), null, 1)).toEqual([]);
});
