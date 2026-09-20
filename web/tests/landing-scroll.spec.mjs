/**
 * Landing page must scroll, and the hero photo must show the full model
 * (not a landscape cover crop through the face).
 *
 *   npm run test:landing
 *   BASE=https://ai-stylist.fly.dev npm run test:landing
 */
import { chromium } from "playwright";

const BASE = process.env.BASE || "https://127.0.0.1:5173";
const results = [];
const check = (name, pass, detail = "") => {
  results.push({ name, pass, detail });
  console.log(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const browser = await chromium.launch();
const ctx = await browser.newContext({
  ignoreHTTPSErrors: true,
  viewport: { width: 1280, height: 720 },
});
const page = await ctx.newPage();
await page.goto(BASE, { waitUntil: "networkidle" });
await page.waitForSelector(".mira-home", { timeout: 15000 });
await page.waitForTimeout(800);

const home = page.locator(".mira-home");
const metrics = await home.evaluate((el) => {
  const img = el.querySelector(".mira-style-hero img");
  const hero = el.querySelector(".mira-style-hero");
  const recs = el.querySelector("#mira-recommendations");
  const cs = img ? getComputedStyle(img) : {};
  const hs = hero ? getComputedStyle(hero) : {};
  return {
    scrollHeight: el.scrollHeight,
    clientHeight: el.clientHeight,
    overflowY: getComputedStyle(el).overflowY,
    imgFit: cs.objectFit,
    imgPos: cs.objectPosition,
    heroOverflow: hs.overflow,
    recsTop: recs ? recs.getBoundingClientRect().top : null,
  };
});

check(
  "landing is a bounded scrollport",
  metrics.scrollHeight > metrics.clientHeight + 80 && /auto|scroll/.test(metrics.overflowY),
  `scroll ${metrics.scrollHeight} / ${metrics.clientHeight} overflow-y=${metrics.overflowY}`,
);

await home.evaluate((el) => { el.scrollTop = el.scrollHeight; });
await page.waitForTimeout(250);
const after = await home.evaluate((el) => ({
  scrollTop: el.scrollTop,
  recsTop: el.querySelector("#mira-recommendations")?.getBoundingClientRect().top ?? null,
}));
check(
  "scrolling the landing reveals recommendations",
  after.scrollTop > 80 && after.recsTop != null && after.recsTop < 720,
  `scrollTop=${Math.round(after.scrollTop)} recsTop=${Math.round(after.recsTop ?? -1)}`,
);

check(
  "hero photo uses contain so the face stays in frame",
  metrics.imgFit === "contain" && /top/i.test(metrics.imgPos || ""),
  `fit=${metrics.imgFit} pos=${metrics.imgPos}`,
);

await page.screenshot({ path: "/tmp/landing_scroll_verified.png", fullPage: false });

await browser.close();
const failed = results.filter((r) => !r.pass);
if (failed.length) {
  console.error(`\n${failed.length} check(s) failed`);
  process.exit(1);
}
console.log("\nlanding scroll ok");
