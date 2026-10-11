/**
 * Complete the Look is its own page, and the bottom piece swaps with the selection.
 *
 *   BASE=https://127.0.0.1:5173 node tests/complete-look.spec.mjs
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";

const BASE = process.env.BASE || "https://127.0.0.1:5173";

function swatch(color, label) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="480" height="640"><rect width="100%" height="100%" fill="${color}"/><text x="24" y="320" font-size="36" fill="#1a1410">${label}</text></svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

const browser = await chromium.launch({ channel: "chrome", headless: true });
const ctx = await browser.newContext({
  ignoreHTTPSErrors: true,
  viewport: { width: 1280, height: 800 },
});
const page = await ctx.newPage();
page.on("pageerror", (err) => console.log("pageerror:", err.message));
await page.goto(BASE, { waitUntil: "domcontentloaded" });

await page.evaluate(async (images) => {
  const { renderLook } = await import("/src/completeLookHarness.jsx");
  const piece = (id, name, category, image_url, price) => ({
    id, name, category, image_url, price, currency: "INR", color: "black",
  });
  const look = {
    title: "Complete the Look",
    currency: "INR",
    hero: piece("top1", "Fuzzy Bomber Jacket", "outerwear", images.jacket, 3499),
    pinned: piece("top1", "Fuzzy Bomber Jacket", "outerwear", images.jacket, 3499),
    bottoms: [
      piece("b1", "Marks & Spencer Solid Black Trousers", "bottoms", images.black, 1999),
      piece("b2", "Wide Leg Cream Trousers", "bottoms", images.cream, 2299),
    ],
    accents: [
      piece("s1", "Leather Loafers", "shoes", images.shoe, 2499),
      piece("g1", "Structured Tote", "bags", images.bag, 1899),
    ],
    items: [],
  };
  look.items = [look.hero, ...look.bottoms, ...look.accents];
  renderLook(look);
}, {
  jacket: swatch("#c4a574", "JACKET"),
  black: swatch("#1c1c1c", "BLACK TROUSERS"),
  cream: swatch("#f3ead7", "CREAM TROUSERS"),
  shoe: swatch("#6b4f3a", "LOAFERS"),
  bag: swatch("#8d6e63", "TOTE"),
});

await page.waitForSelector("[data-slot='bottom']");
const before = await page.evaluate(() => {
  const panel = document.querySelector(".full-look-panel");
  const cs = getComputedStyle(panel);
  const rect = panel.getBoundingClientRect();
  const footer = document.querySelector(".privacy-link, .app-footer");
  const bottom = document.querySelector("[data-slot='bottom']");
  const hit = document.elementFromPoint(window.innerWidth / 2, window.innerHeight - 8);
  return {
    position: cs.position,
    covers: rect.width >= window.innerWidth - 2 && rect.height >= window.innerHeight - 2,
    z: cs.zIndex,
    bottomId: bottom?.dataset.productId || "",
    bottomAlt: bottom?.querySelector("img")?.alt || "",
    footerCovered: !!panel.contains(hit) || !footer,
    footerTextVisible: footer ? footer.getBoundingClientRect().top < window.innerHeight && getComputedStyle(footer).visibility !== "hidden" : false,
  };
});
console.log("before", JSON.stringify(before));
assert.equal(before.position, "fixed", "Complete the Look should be a full page, not a strip in the chat");
assert.equal(before.covers, true);
assert.equal(before.bottomId, "b1");
assert.equal(before.footerCovered, true);

await page.screenshot({ path: "/tmp/complete-look-before.png" });
await page.getByRole("button", { name: /Wide Leg Cream Trousers/ }).click();
await page.waitForFunction(() => document.querySelector("[data-slot='bottom']")?.dataset.productId === "b2");
const after = await page.evaluate(() => {
  const bottom = document.querySelector("[data-slot='bottom']");
  const img = bottom?.querySelector("img");
  const slot = document.querySelector(".flp-slot.is-current img");
  return {
    bottomId: bottom?.dataset.productId || "",
    alt: img?.alt || "",
    srcHasCream: (img?.getAttribute("src") || "").includes("CREAM"),
    chosenRow: document.querySelector(".flp-row.is-chosen .flp-row-name")?.textContent || "",
  };
});
console.log("after", JSON.stringify(after));
assert.equal(after.bottomId, "b2");
assert.match(after.alt, /Cream/);
assert.equal(after.srcHasCream, true);
assert.match(after.chosenRow, /Cream/);
await page.screenshot({ path: "/tmp/complete-look-after.png" });

await page.setViewportSize({ width: 390, height: 844 });
await page.waitForTimeout(200);
const mobile = await page.evaluate(() => {
  const panel = document.querySelector(".full-look-panel");
  const rect = panel.getBoundingClientRect();
  const bottom = document.querySelector("[data-slot='bottom']");
  return {
    covers: rect.height >= window.innerHeight - 2,
    bottomId: bottom?.dataset.productId || "",
    bottomVisible: bottom.getBoundingClientRect().height > 40,
  };
});
console.log("mobile", JSON.stringify(mobile));
assert.equal(mobile.covers, true);
assert.equal(mobile.bottomId, "b2");
assert.equal(mobile.bottomVisible, true);
await page.screenshot({ path: "/tmp/complete-look-mobile.png" });

await browser.close();
console.log("complete look ok");
