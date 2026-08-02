// Thin analytics wrapper around PostHog. No-op until VITE_POSTHOG_KEY is set.
// PostHog is loaded lazily after idle so it never blocks first paint.
//
// Setup:
//   VITE_POSTHOG_KEY=phc_xxx
//   VITE_POSTHOG_HOST=https://eu.i.posthog.com

const KEY = import.meta.env.VITE_POSTHOG_KEY;
const HOST = import.meta.env.VITE_POSTHOG_HOST || "https://eu.i.posthog.com";

let _on = false;
let _ph = null;
let _queue = [];

function _flush() {
  if (!_ph) return;
  for (const job of _queue) job(_ph);
  _queue = [];
}

export function initAnalytics() {
  if (_on || !KEY || typeof window === "undefined") return;
  _on = true; // prevent double-schedule; actual client may still be loading

  const boot = () => {
    import("posthog-js")
      .then(({ default: posthog }) => {
        try {
          posthog.init(KEY, {
            api_host: HOST,
            capture_pageview: true,
            persistence: "localStorage+cookie",
            // Autocapture adds main-thread work; opt in later if needed.
            autocapture: false,
            loaded: () => {
              _ph = posthog;
              _flush();
            },
          });
          // Some builds don't fire `loaded` — set immediately as fallback.
          if (!_ph) {
            _ph = posthog;
            _flush();
          }
        } catch (e) {
          console.warn("[analytics] init failed", e);
          _on = false;
        }
      })
      .catch((e) => {
        console.warn("[analytics] load failed", e);
        _on = false;
      });
  };

  if ("requestIdleCallback" in window) {
    requestIdleCallback(boot, { timeout: 4000 });
  } else {
    setTimeout(boot, 2500);
  }
}

export function track(event, props = {}) {
  if (!_on) return;
  const run = (ph) => { try { ph.capture(event, props); } catch { /* ignore */ } };
  if (_ph) run(_ph);
  else _queue.push(run);
}

export function identify(userId, traits = {}) {
  if (!_on || !userId) return;
  const run = (ph) => { try { ph.identify(userId, traits); } catch { /* ignore */ } };
  if (_ph) run(_ph);
  else _queue.push(run);
}

export function resetAnalytics() {
  if (!_ph) return;
  try { _ph.reset(); } catch { /* ignore */ }
}
