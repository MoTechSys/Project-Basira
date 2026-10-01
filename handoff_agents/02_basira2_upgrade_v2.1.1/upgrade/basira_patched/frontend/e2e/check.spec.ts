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
  const badges = page.getByRole("status");
  await expect(badges).toHaveCount(2);
  await expect(badges.nth(0)).toContainText("يحتاج مراجعة");
  await expect(badges.nth(1)).toContainText("وُجد");
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
