/**
 * Tapping a product must open a full-screen product page (gallery + sticky buy).
 *
 *   npm run test:pdp
 *   BASE=https://ai-stylist.fly.dev npm run test:pdp
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
await page.waitForTimeout(2800);

const card = page.locator("#cf-results-panel .card").first();
await card.waitFor({ state: "visible", timeout: 15000 });
await card.click();

const panel = page.locator(".qv-panel");
await panel.waitFor({ state: "visible", timeout: 8000 });
await page.waitForTimeout(450);

const gallery = page.locator(".qv-gallery");
const sticky = page.locator(".qv-sticky");
const shop = page.locator(".qv-sticky-shop");
const img = page.locator(".qv-gallery .qv-img").first();

const pdpOpen = await panel.isVisible();
const galleryOpen = await gallery.isVisible();
const stickyOpen = await sticky.isVisible();
const shopOpen = await shop.isVisible();
const fit = await img.evaluate((el) => getComputedStyle(el).objectFit).catch(() => "");
const layout = await page.evaluate(() => {
  const g = document.querySelector(".qv-gallery");
  const s = document.querySelector(".qv-sticky");
  const p = document.querySelector(".qv-panel");
  return {
    innerH: window.innerHeight,
    panelTop: p?.getBoundingClientRect().top,
    galleryTop: g?.getBoundingClientRect().top,
    stickyBottom: s?.getBoundingClientRect().bottom,
  };
});
const stickyOnScreen = (layout.stickyBottom ?? 9999) <= layout.innerH + 12;
const galleryAboveFold = (layout.galleryTop ?? 9999) < layout.innerH * 0.55;

console.log("PDP open:", pdpOpen);
console.log("swipe gallery:", galleryOpen);
console.log("sticky buy bar:", stickyOpen, `(bottom=${Math.round(layout.stickyBottom ?? -1)} / ${layout.innerH})`);
console.log("sticky shop CTA:", shopOpen);
console.log("photo object-fit:", fit, "— contain:", fit === "contain");
console.log("gallery above fold:", galleryAboveFold, `(top=${Math.round(layout.galleryTop ?? -1)})`);
console.log("sticky bar on screen:", stickyOnScreen);

const tryOnBtn = page.getByRole("button", { name: "Try on" });
const tryOnVisible = await tryOnBtn.isVisible();
console.log("PDP Try on button:", tryOnVisible);
await tryOnBtn.click();
await page.waitForTimeout(500);
const pdpClosedForVto = !(await panel.isVisible());
const vtoModal = page.locator(".tryon-overlay");
const signInGate = page.getByRole("heading", { name: /sign in to try/i });
const vtoLaunched = (await vtoModal.isVisible()) || (await signInGate.isVisible());
console.log("Try on closed the PDP:", pdpClosedForVto);
console.log("VTO launched (modal or sign-in gate):", vtoLaunched);

await page.screenshot({ path: "/tmp/pdp_verified.png" });
if (await signInGate.isVisible()) {
  await page.locator(".delete-overlay").click({ position: { x: 8, y: 8 } });
  await page.waitForTimeout(300);
} else if (await vtoModal.isVisible()) {
  await page.locator(".tryon-close").click();
  await page.waitForTimeout(300);
} else {
  await page.getByRole("button", { name: "Close" }).click();
  await page.waitForTimeout(400);
}
const closed = !(await panel.isVisible()) && !(await vtoModal.isVisible());
console.log("close returns to browse:", closed);

await browser.close();

const failures = [];
if (!pdpOpen) failures.push("PDP did not open");
if (!galleryOpen) failures.push("swipe gallery missing");
if (!stickyOpen || !shopOpen) failures.push("sticky buy bar missing");
if (fit !== "contain") failures.push(`photo is cropped (object-fit=${fit})`);
if (!stickyOnScreen) failures.push("sticky buy bar is off-screen");
if (!tryOnVisible) failures.push("PDP has no Try on button");
if (!vtoLaunched) failures.push("Try on did not open VTO or the sign-in gate");
if (!closed) failures.push("Close did not dismiss the PDP");
if (failures.length) {
  console.error("FAIL:", failures.join("; "));
  process.exit(1);
}
