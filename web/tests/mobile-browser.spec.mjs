/**
 * Phone-browser chrome: tap targets stay usable at 390 and 320.
 *
 *   node tests/mobile-browser.spec.mjs
 *   BASE=https://ai-stylist.fly.dev node tests/mobile-browser.spec.mjs
 */
import { chromium } from "playwright";

const BASE = process.env.BASE || "https://127.0.0.1:5173";
const results = [];
const check = (name, pass, detail = "") => {
  results.push({ name, pass, detail });
  console.log(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

async function measure(page, selector) {
  const el = page.locator(selector).first();
  if (!(await el.count()) || !(await el.isVisible().catch(() => false))) return null;
  return el.evaluate((node) => {
    const r = node.getBoundingClientRect();
    return { w: Math.round(r.width), h: Math.round(r.height) };
  });
}

async function runAt(browser, width, height) {
  const ctx = await browser.newContext({
    ignoreHTTPSErrors: true,
    viewport: { width, height },
    isMobile: true,
    hasTouch: true,
  });
  const page = await ctx.newPage();
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForSelector(".mira-home", { timeout: 15000 });
  await page.waitForTimeout(400);

  const bag = await measure(page, ".mira-icon-btn");
  const avatar = await measure(page, ".mira-avatar-btn");
  await page.locator(".mira-hero-arrow--left").waitFor({ state: "visible", timeout: 4000 }).catch(() => {});
  const prev = await measure(page, ".mira-hero-arrow--left");
  check(
    `${width} bag tap ≥ 44`,
    !!bag && bag.w >= 44 && bag.h >= 44,
    bag ? `${bag.w}×${bag.h}` : "missing",
  );
  check(
    `${width} avatar tap ≥ 44`,
    !!avatar && avatar.w >= 44 && avatar.h >= 44,
    avatar ? `${avatar.w}×${avatar.h}` : "missing",
  );
  if (prev) {
    check(
      `${width} hero arrow tap ≥ 44`,
      prev.w >= 44 && prev.h >= 44,
      `${prev.w}×${prev.h}`,
    );
  } else {
    check(`${width} hero carousel optional without catalog`, true, "no trending feed");
  }

  const overflowX = await page.evaluate(() =>
    document.documentElement.scrollWidth > document.documentElement.clientWidth + 2
  );
  check(`${width} no horizontal page scroll`, !overflowX);

  const svgBag = await page.locator(".mira-icon-btn .mira-icon").count();
  check(`${width} bag uses SVG icon`, svgBag > 0);

  await ctx.close();
}

const browser = await chromium.launch();
try {
  await runAt(browser, 390, 844);
  await runAt(browser, 320, 568);
} finally {
  await browser.close();
}

const failed = results.filter((r) => !r.pass);
if (failed.length) {
  console.error(`\n${failed.length} failed`);
  process.exit(1);
}
console.log(`\n${results.length} checks passed`);
