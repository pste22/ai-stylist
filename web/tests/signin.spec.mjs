/**
 * End-to-end check of the sign-in flow.
 *
 *   npm run test:signin                              # against local ./dev.sh
 *   BASE=https://ai-stylist.fly.dev npm run test:signin
 *
 * Covers the ways sign-in has silently done nothing: offering a provider the
 * Supabase project has disabled, swallowing the resulting error, and dropping
 * the user on the hero instead of the auth sheet.
 */
import { chromium } from "playwright";

const BASE = process.env.BASE || "https://127.0.0.1:5173";
const results = [];
const check = (name, pass, detail = "") =>
  results.push({ name, pass, detail });

const browser = await chromium.launch();
const ctx = await browser.newContext({ ignoreHTTPSErrors: true });
const page = await ctx.newPage();
const consoleErrors = [];
page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));

await page.goto(BASE, { waitUntil: "networkidle" });

// 1. Landing hero renders
check("hero renders", await page.locator(".mira-home-brand").isVisible());

// 2. "Log in" opens the auth sheet
await page.getByRole("button", { name: "Log in" }).click();
await page.waitForSelector(".mira-home-auth-panel", { timeout: 5000 });
check("auth sheet opens from Log in", await page.locator(".mira-home-auth-panel").isVisible());

// 3. Only providers Supabase has enabled are offered
await page.waitForTimeout(1500); // settings lookup
const buttons = await page.locator(".login-actions .oauth-btn").allTextContents();
const labels = buttons.map((b) => b.trim());
check("google offered", labels.some((l) => /Google/i.test(l)), labels.join(" | "));
check("disabled github hidden", !labels.some((l) => /GitHub/i.test(l)), labels.join(" | "));
check("disabled facebook hidden", !labels.some((l) => /Facebook/i.test(l)), labels.join(" | "));

// 4. Clicking Google actually leaves for the provider
await Promise.all([
  page.waitForURL(/accounts\.google\.com/, { timeout: 20000 }).catch(() => null),
  page.getByRole("button", { name: /Continue with Google/i }).click(),
]);
check("google click reaches provider", /accounts\.google\.com/.test(page.url()), page.url());

// 5. Guest -> "Sign in" lands on the sheet, not the bare hero
const page2 = await ctx.newPage();
await page2.goto(BASE, { waitUntil: "networkidle" });
await page2.getByRole("button", { name: "Start styling" }).click();
await page2.waitForSelector(".guest-signin-btn", { timeout: 15000 });
await page2.locator(".guest-signin-btn").click();
const sheetVisible = await page2
  .waitForSelector(".mira-home-auth-panel", { timeout: 5000 })
  .then(() => true)
  .catch(() => false);
check("guest Sign in opens the sheet directly", sheetVisible);

// 6. A provider error is shown rather than swallowed
const page3 = await ctx.newPage();
await page3.goto(`${BASE}/#error=access_denied&error_description=Test+failure`, {
  waitUntil: "networkidle",
});
const errVisible = await page3
  .waitForSelector(".login-error", { timeout: 8000 })
  .then(() => true)
  .catch(() => false);
const errText = errVisible ? (await page3.locator(".login-error").textContent()).trim() : "";
check("redirect error is surfaced", errVisible, errText);
check("error cleared from url", !page3.url().includes("error"), page3.url());

await browser.close();

let failed = 0;
for (const r of results) {
  if (!r.pass) failed++;
  console.log(`${r.pass ? "PASS" : "FAIL"}  ${r.name}${r.detail ? `  [${r.detail}]` : ""}`);
}
const appErrors = consoleErrors.filter((e) => !/favicon|401|Failed to load resource/i.test(e));
if (appErrors.length) console.log("console errors:", appErrors.slice(0, 5));
console.log(failed ? `\n${failed} FAILED` : "\nall passed");
process.exit(failed ? 1 : 0);
