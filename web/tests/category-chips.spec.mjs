/**
 * Tapping a category on a phone must show the results, not a wall of facets.
 *
 *   npm run test:chips
 *   BASE=https://ai-stylist.fly.dev npm run test:chips
 */
import { chromium } from "playwright";

const BASE = process.env.BASE || "https://127.0.0.1:5173";
const browser = await chromium.launch();
const ctx = await browser.newContext({
  ignoreHTTPSErrors: true,
  viewport: { width: 390, height: 844 },
  isMobile: true,
  hasTouch: true,
});
const page = await ctx.newPage();
await page.goto(BASE, { waitUntil: "networkidle" });
await page.getByRole("button", { name: "Start styling" }).click();
await page.waitForTimeout(2500);

await page.locator(".filter-chip", { hasText: /^SHOES$/i }).first().click();
await page.waitForTimeout(2500);

const pillsBox = await page.locator(".cf-pills").boundingBox();
const panelBox = await page.locator("#cf-results-panel").boundingBox();
const revealBox = await page.locator(".cf-filters-reveal").boundingBox();
const vh = 844, vw = 390;

console.log("facet pills collapsed:", !pillsBox || pillsBox.height < 8, `(h=${pillsBox?.height ?? 0})`);
console.log("results panel top:", Math.round(panelBox?.y ?? -1), "— above the fold:", (panelBox?.y ?? 9999) < vh * 0.6);
console.log("Filters button on screen:", !!revealBox && revealBox.x >= 0 && revealBox.x + revealBox.width <= vw + 1,
  `(x=${Math.round(revealBox?.x ?? -1)} w=${Math.round(revealBox?.width ?? 0)})`);

// Tapping Filters must still open the facets.
await page.locator(".cf-filters-reveal").click();
await page.waitForTimeout(900);
const pillsOpen = await page.locator(".cf-pills").boundingBox();
console.log("Filters tap opens facets:", (pillsOpen?.height ?? 0) > 40, `(h=${Math.round(pillsOpen?.height ?? 0)})`);

await page.screenshot({ path: "/tmp/chips_verified.png" });
await browser.close();
