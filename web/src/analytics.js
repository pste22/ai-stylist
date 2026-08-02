// Thin analytics wrapper around PostHog. No-op until VITE_POSTHOG_KEY is set, so
// dev/test/CI never break and you flip it on by adding the key.
//
// Setup: create a free PostHog project (EU region for privacy), then set in the
// build env / .env:
//   VITE_POSTHOG_KEY=phc_xxx
//   VITE_POSTHOG_HOST=https://eu.i.posthog.com   (or https://us.i.posthog.com)
import posthog from "posthog-js";

const KEY = import.meta.env.VITE_POSTHOG_KEY;
const HOST = import.meta.env.VITE_POSTHOG_HOST || "https://eu.i.posthog.com";

let _on = false;

export function initAnalytics() {
  if (_on || !KEY) return;
  try {
    posthog.init(KEY, {
      api_host: HOST,
      capture_pageview: true,
      persistence: "localStorage+cookie",
      autocapture: true,
    });
    _on = true;
  } catch (e) {
    console.warn("[analytics] init failed", e);
  }
}

export function track(event, props = {}) {
  if (!_on) return;
  try { posthog.capture(event, props); } catch { /* ignore */ }
}

export function identify(userId, traits = {}) {
  if (!_on || !userId) return;
  try { posthog.identify(userId, traits); } catch { /* ignore */ }
}

export function resetAnalytics() {
  if (!_on) return;
  try { posthog.reset(); } catch { /* ignore */ }
}
