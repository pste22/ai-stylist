/**
 * Mira AI Stylist — automated bug crawler
 *
 * Usage:
 *   node web/crawl_bugs.mjs [APP_URL]
 *
 * APP_URL defaults to http://localhost:5173
 * In Codespaces pass the forwarded URL:
 *   node web/crawl_bugs.mjs https://YOUR-5173.app.github.dev
 *
 * Requires: dev server + backend both running (./dev.sh)
 * Output  : PASS/FAIL per scenario + screenshots in /tmp/crawl-screenshots/
 */

import { chromium } from "playwright";
import { mkdir, writeFile } from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";

const APP_URL = process.argv[2] || "http://localhost:5173";
const SS_DIR  = "/tmp/crawl-screenshots";
const TIMEOUT  = 20_000; // ms per assertion

// ── helpers ──────────────────────────────────────────────────────────────────

const results = [];

function pass(name) {
  results.push({ name, ok: true });
  console.log(`  ✓  ${name}`);
}

function fail(name, reason) {
  results.push({ name, ok: false, reason });
  console.error(`  ✗  ${name}: ${reason}`);
}

async function shot(page, label) {
  try {
    const file = path.join(SS_DIR, `${label.replace(/\s+/g, "_")}.png`);
    await page.screenshot({ path: file, fullPage: false });
    return file;
  } catch { return null; }
}

async function waitAndCheck(page, selector, description, timeout = TIMEOUT) {
  try {
    await page.waitForSelector(selector, { timeout });
    pass(description);
    return true;
  } catch {
    const file = await shot(page, description);
    fail(description, `selector "${selector}" not found within ${timeout}ms${file ? ` — screenshot: ${file}` : ""}`);
    return false;
  }
}

// ── scenarios ─────────────────────────────────────────────────────────────────

async function scenario_page_loads(page) {
  console.log("\n── Page loads ──────────────────────────────────────────────");
  await page.goto(APP_URL, { waitUntil: "networkidle" });
  await waitAndCheck(page, "body", "HTML rendered");
  await waitAndCheck(page, ".chat-title, .login-title, .app-chat", "App container visible");
  await shot(page, "00_home");
}

async function scenario_guest_mode(page) {
  console.log("\n── Guest mode ───────────────────────────────────────────────");
  // Try to find and click Guest button (only present on login screen)
  const guestBtn = page.locator("button", { hasText: /guest/i }).first();
  const visible = await guestBtn.isVisible().catch(() => false);
  if (!visible) {
    pass("Guest mode — already authenticated (skipped)");
    return true;
  }
  await guestBtn.click();
  await waitAndCheck(page, ".app-chat", "Chat shell visible after guest login");
  await shot(page, "01_guest_mode");
  return true;
}

async function scenario_start_text_mode(page) {
  console.log("\n── Start in text mode ───────────────────────────────────────");

  // Click the Text / silent mode toggle if present
  const textToggle = page.locator(".mode-toggle button", { hasText: /text|silent/i }).first();
  if (await textToggle.isVisible().catch(() => false)) {
    await textToggle.click();
    pass("Switched to text mode");
  } else {
    pass("Text mode toggle not found — may already be active");
  }

  // Start chatting
  const startBtn = page.locator(".chat-start-btn").first();
  if (await startBtn.isVisible().catch(() => false)) {
    await startBtn.click();
    pass("Clicked Start chatting");
  } else {
    fail("Start chatting", "Button not found");
    return false;
  }

  // Wait for connection (show-more button appears when connected)
  await waitAndCheck(page, ".show-more-btn", "Connected — show-more button visible", 15_000);
  await shot(page, "02_connected");
  return true;
}

async function scenario_send_message(page) {
  console.log("\n── Send a text message ──────────────────────────────────────");

  const input = page.locator(".chat-input, textarea[class*='chat']").first();
  if (!await input.isVisible().catch(() => false)) {
    fail("Text input visible", "Input box not found");
    return false;
  }

  await input.fill("Show me something nice for a party");
  await input.press("Enter");
  pass("Message sent");

  // Expect Mira to respond with a bubble
  await waitAndCheck(page, ".msg-row.mira .msg-bubble", "Mira response bubble appears", 20_000);

  // Expect product cards
  await waitAndCheck(page, ".product-card, .product-grid", "Product cards appear", 20_000);
  await shot(page, "03_after_message");
  return true;
}

async function scenario_show_more(page) {
  console.log("\n── Show 3 more ──────────────────────────────────────────────");

  const btn = page.locator(".show-more-btn").first();
  if (!await btn.isVisible().catch(() => false)) {
    fail("Show more button visible", "Button not found");
    return false;
  }

  // Count cards before
  const before = await page.locator(".product-card").count();

  await btn.click();
  pass("Clicked Show 3 more");

  // Either new cards appear OR button re-hides (catalog exhausted)
  try {
    // Wait for the button to either re-appear (with new products) or disappear
    await page.waitForFunction(
      (prevCount) => {
        const cards = document.querySelectorAll(".product-card").length;
        const btnGone = !document.querySelector(".show-more-btn");
        return cards > prevCount || btnGone;
      },
      before,
      { timeout: 8_000 }
    );
    const after = await page.locator(".product-card").count();
    if (after > before) {
      pass(`Show 3 more — ${after - before} new product card(s) appeared`);
    } else {
      pass("Show 3 more — catalog exhausted, button hidden (correct behaviour)");
    }
  } catch {
    fail("Show 3 more — products or button state change", "Neither new cards nor button disappearance after 8s");
  }

  await shot(page, "04_show_more");
  return true;
}

async function scenario_visual_search(page) {
  console.log("\n── Visual search ────────────────────────────────────────────");

  // The hidden file input for visual search
  const fileInput = page.locator("input[type=file][accept*='image']").first();
  if (!await fileInput.count()) {
    fail("Visual search input found", "No file input for images");
    return false;
  }

  // Use a 1×1 pixel transparent PNG as a dummy image
  const pngBase64 =
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==";
  const pngBytes = Buffer.from(pngBase64, "base64");
  const tmpImg = "/tmp/test_visual_search.png";
  await writeFile(tmpImg, pngBytes);

  await fileInput.setInputFiles(tmpImg);
  pass("Image file set on input");

  // Expect loading banner to appear
  const loading = page.locator(".vs-loading");
  const loadingVisible = await loading.isVisible().catch(() => false);
  if (loadingVisible) {
    pass("Visual search loading spinner appeared");
  } else {
    fail("Visual search loading spinner", "vs-loading div did not appear");
  }

  // Wait for results or error (30s max since Gemini call takes ~3-5s)
  try {
    await page.waitForFunction(
      () => !document.querySelector(".vs-loading"),
      { timeout: 30_000 }
    );
    pass("Visual search loading cleared");
    const resultsPanel = await page.locator(".vs-results").count();
    if (resultsPanel > 0) {
      pass("Visual search results panel appeared");
    } else {
      // No results could mean empty match — not a crash
      pass("Visual search completed (no match panel — possible empty result)");
    }
  } catch {
    fail("Visual search", "vs-loading never cleared after 30s — possible hung request");
  }

  await shot(page, "05_visual_search");
}

async function scenario_look_engine(page) {
  console.log("\n── Look / event brief ───────────────────────────────────────");

  // Try clicking the event brief flow
  const eventBtn = page.locator("button", { hasText: /event|look|occasion/i }).first();
  if (await eventBtn.isVisible().catch(() => false)) {
    await eventBtn.click();
    pass("Event brief button clicked");
    await shot(page, "06_event_brief");
    // Press Escape to close without filling out
    await page.keyboard.press("Escape");
  } else {
    pass("Event brief button not visible on current screen (skipped)");
  }
}

async function scenario_console_errors(page, errors) {
  console.log("\n── Console errors ───────────────────────────────────────────");
  if (errors.length === 0) {
    pass("No JavaScript console errors");
  } else {
    const serious = errors.filter((e) => !e.includes("favicon") && !e.includes("404"));
    if (serious.length === 0) {
      pass(`Console: ${errors.length} minor error(s) (favicon/404 only)`);
    } else {
      for (const e of serious.slice(0, 5)) {
        fail("Console error", e.slice(0, 120));
      }
    }
  }
}

// ── main ─────────────────────────────────────────────────────────────────────

(async () => {
  console.log(`\n🕷️  Mira bug crawler — target: ${APP_URL}`);
  console.log(`   Screenshots → ${SS_DIR}\n`);

  await mkdir(SS_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 }, // iPhone 14 Pro
    userAgent:
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    ignoreHTTPSErrors: true,
  });

  const consoleErrors = [];
  const page = await ctx.newPage();
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  try {
    await scenario_page_loads(page);
    await scenario_guest_mode(page);
    const started = await scenario_start_text_mode(page);
    if (started) {
      await scenario_send_message(page);
      await scenario_show_more(page);
      await scenario_visual_search(page);
      await scenario_look_engine(page);
    }
    await scenario_console_errors(page, consoleErrors);
  } catch (e) {
    fail("Unhandled crawler error", String(e));
    await shot(page, "99_crash");
  } finally {
    await browser.close();
  }

  // ── Summary ────────────────────────────────────────────────────────────────
  const passed = results.filter((r) => r.ok).length;
  const failed = results.filter((r) => !r.ok).length;

  console.log(`\n${"─".repeat(60)}`);
  console.log(`  Results: ${passed} passed, ${failed} failed`);
  if (failed > 0) {
    console.log("\n  Failures:");
    results.filter((r) => !r.ok).forEach((r) => {
      console.log(`    ✗ ${r.name}`);
      console.log(`      ${r.reason}`);
    });
  }
  console.log(`${"─".repeat(60)}\n`);
  process.exit(failed > 0 ? 1 : 0);
})();
