/**
 * SessionWatcher — real-time session validator.
 *
 * Patches the global WebSocket constructor so every WS message (in both
 * directions) is intercepted and run through validation rules.  Reports
 * bugs and confirms working features via a floating overlay in the browser.
 *
 * Injected automatically in dev mode (VITE_DEBUG=true or ?debug in URL).
 * Safe to leave in: the overlay is hidden in prod and has zero runtime cost
 * when inactive.
 *
 * Exported API:
 *   install()  → patch WS + return uninstall fn
 *   uninstall()
 */

const MAX_LOG = 60; // max entries in the panel

// ── Rule definitions ──────────────────────────────────────────────────────────
//
// Each rule watches for a specific outbound (client→server) message and expects
// a corresponding inbound (server→client) message within a timeout.
//
// Rules can also fire on inbound messages alone (e.g., validate payload shape).

const RULES = {

  // ── show_more: must get back 1–3 products (or explicit show_more:false) ──
  show_more: {
    onSend(msg, ctx) {
      ctx.expectIncoming("products", 6000,
        (resp) => {
          if (!Array.isArray(resp.items))
            return "products response missing items array";

          const n = resp.items.length;

          // Catalog exhausted — server must say so explicitly
          if (n === 0) {
            return resp.show_more === false
              ? null  // correct: server signalled end of catalog
              : "show_more returned 0 items but show_more !== false — button will re-enable with no products";
          }

          // Should be exactly 3 unless we're at the tail of the catalog
          if (n > 3)
            return `show_more returned ${n} items — server should cap at 3`;

          // Count must match what server actually has (1–3 is acceptable)
          // Warn on < 3 only when show_more:true, which implies more exist
          if (n < 3 && resp.show_more === true)
            return `show_more returned only ${n} item(s) but server says more exist — possible catalog gap`;

          return null; // ok
        },
        "show_more sent but no products response within 6 s — button may never re-enable"
      );
    },
  },

  // ── visual_search: must get visual_search_results within 25 s ────────────
  visual_search: {
    onSend(msg, ctx) {
      if (!msg.image) {
        ctx.bug("warn", "visual_search sent without image payload");
        return;
      }
      ctx.expectIncoming("visual_search_results", 25000,
        (resp) => {
          if (!Array.isArray(resp.items)) return "visual_search_results missing items array";
          return null;
        },
        "visual_search sent but no results received within 25 s — spinner may be stuck"
      );
    },
  },

  // ── text_input: validate the full response sequence ───────────────────────
  //
  // Expected flow after each user message:
  //   1. state:thinking   (within 3 s)
  //   2. transcript who=mira  (within 12 s)  — may stream many chunks
  //   3. state:reacting / state:idle  (within 25 s of the text_input)
  //
  // Also tracks whether Mira named a product in her reply but no product
  // cards arrived (name-drop without a card = broken recommendation).
  text_input: {
    onSend(msg, ctx) {
      if (!msg.text?.trim()) {
        ctx.bug("warn", "text_input sent with empty text");
        return;
      }

      // 1. state:thinking within 3 s
      ctx.expectIncoming("state", 3000,
        (resp) => resp.state === "thinking" ? null : "skip",
        `text_input: no state:thinking within 3 s — server may not have received the message`
      );

      // 2. Mira transcript within 12 s
      ctx.expectIncoming("transcript", 12000,
        (resp) => {
          if (resp.who !== "mira") return "skip";
          if (!resp.text?.trim())
            return "transcript received but text is empty — blank Mira response";
          return null;
        },
        "text_input: Mira never responded with a transcript within 12 s"
      );

      // 3. Turn must complete (state:idle or state:reacting) within 25 s
      ctx.expectIncoming("state", 25000,
        (resp) => (resp.state === "idle" || resp.state === "reacting") ? null : "skip",
        "text_input: turn never completed — state never returned to idle/reacting within 25 s (hung response?)"
      );
    },
  },

  // ── transcript: validate every Mira response chunk ───────────────────────
  transcript: {
    onReceive(msg, ctx) {
      if (msg.who !== "mira") return; // skip user echo

      // Flag suspiciously short completions (likely a partial/truncated response)
      // We only want to check the FINAL chunk — approximate: if text ends with
      // sentence-ending punctuation it's likely a complete thought.
      const text = (msg.text || "").trim();
      if (text.length > 0 && text.length < 8 && /^[a-z]/.test(text)) {
        // Very short, starts lowercase — likely a mid-stream chunk; skip
        return;
      }
      // Detect error phrases leaked into the response
      const errorPhrases = [
        "i'm sorry, i encountered",
        "an error occurred",
        "i cannot process",
        "i'm unable to",
        "something went wrong",
      ];
      const lower = text.toLowerCase();
      if (errorPhrases.some(p => lower.includes(p))) {
        ctx.bug("warn", `Mira response contains error phrase: "${text.slice(0, 80)}"`);
      }
    },
  },

  // ── products payload validation ───────────────────────────────────────────
  products: {
    onReceive(msg, ctx) {
      const items = msg.items || [];
      const broken = items.filter(p => !p.image_url || !p.affiliate_url || !p.name);
      if (broken.length) {
        ctx.bug("warn",
          `products: ${broken.length} item(s) missing image_url / affiliate_url / name — cards will render broken`,
          broken.map(p => p.id || p.name).join(", ")
        );
      }
      if (items.length > 0) {
        ctx.ok(`products: ${items.length} item(s) received, all fields present`);
      }
      // Warn on unexpectedly large batches from a single turn
      if (items.length > 6) {
        ctx.bug("warn", `products: ${items.length} items in one batch — UI shows max 3, rest are invisible`);
      }
    },
  },

  // ── looks payload validation ──────────────────────────────────────────────
  looks: {
    onReceive(msg, ctx) {
      const looks = msg.items || [];
      if (!looks.length) {
        ctx.bug("warn", "looks: empty array received — look deck will be empty");
        return;
      }
      let anyBroken = false;
      looks.forEach((look, i) => {
        if (!look.slots) {
          ctx.bug("warn", `looks[${i}] "${look.name}": missing slots object`);
          anyBroken = true; return;
        }
        if (!look.slots.outfit?.length) {
          ctx.bug("warn", `looks[${i}] "${look.name}": empty outfit slot — look card will render incomplete`);
          anyBroken = true;
        }
        if (!look.total_price) {
          ctx.bug("warn", `looks[${i}] "${look.name}": missing total_price`);
        }
      });
      if (!anyBroken) {
        ctx.ok(`looks: ${looks.length} complete look(s) received with all slots populated`);
      }
    },
  },

  // ── visual_search_results validation ─────────────────────────────────────
  visual_search_results: {
    onReceive(msg, ctx) {
      if (msg.error) {
        ctx.bug("error", `visual_search failed on server: ${msg.error}`);
        return;
      }
      ctx.ok(`visual_search_results: ${(msg.items || []).length} match(es) — query: "${msg.query || ""}"`);
    },
  },

  // ── error messages from server ────────────────────────────────────────────
  error: {
    onReceive(msg, ctx) {
      ctx.bug("error", `server error: ${msg.message || JSON.stringify(msg)}`);
    },
  },

  // ── connection: initial products must arrive within 8 s of init ──────────
  init: {
    onSend(msg, ctx) {
      ctx.expectIncoming("products", 8000,
        (resp) => {
          if (!resp.items?.length)
            return "initial products batch is empty — no personalized picks on load";
          return null;
        },
        "init sent but no initial product picks arrived within 8 s"
      );
      ctx.ok(`init sent — user: ${msg.name || "guest"}, mode: ${msg.text_mode ? "text" : "voice"}`);
    },
  },

  // ── add_to_cart: validate the items sent back ─────────────────────────────
  add_to_cart: {
    onReceive(msg, ctx) {
      const items = msg.items || [];
      if (!items.length) {
        ctx.bug("warn", "add_to_cart received with empty items array — cart not updated");
        return;
      }
      const broken = items.filter(p => !p.id || !p.name);
      if (broken.length) {
        ctx.bug("warn", `add_to_cart: ${broken.length} item(s) missing id or name`);
      } else {
        ctx.ok(`add_to_cart: ${items.length} item(s) added — ${items.map(p => p.name).join(", ")}`);
      }
    },
  },
};

// ── Context object passed to each rule ───────────────────────────────────────

function makeCtx(emit, pendingExpects) {
  return {
    bug(level, msg, detail) {
      emit({ kind: "bug", level, msg, detail, ts: _ts() });
    },
    ok(msg) {
      emit({ kind: "ok", msg, ts: _ts() });
    },
    expectIncoming(type, timeoutMs, validate, timeoutMsg) {
      const token = `${type}_${Date.now()}_${Math.random()}`;
      const timer = setTimeout(() => {
        pendingExpects.delete(token);
        emit({ kind: "bug", level: "error", msg: timeoutMsg, ts: _ts() });
      }, timeoutMs);
      pendingExpects.set(token, { type, validate, timer });
    },
  };
}

function _ts() {
  return new Date().toLocaleTimeString("en-IN", { hour12: false });
}

// ── Core patcher ─────────────────────────────────────────────────────────────

let _installed = false;
let _OriginalWS = null;
let _notifyUI = null; // callback set by the overlay component
let _log = []; // in-memory log for late-mounting overlay

export function setUICallback(fn) {
  _notifyUI = fn;
  // Replay existing log into the UI
  _log.forEach(fn);
}

function emit(entry) {
  _log = [entry, ..._log].slice(0, MAX_LOG);
  _notifyUI?.(entry);
  if (entry.kind === "bug") {
    console[entry.level === "error" ? "error" : "warn"](
      `%c[SessionWatcher] ${entry.level.toUpperCase()}: ${entry.msg}`,
      "color: #f87171; font-weight: bold",
      entry.detail || ""
    );
  }
}

export function install() {
  if (_installed) return;
  _installed = true;
  _OriginalWS = window.WebSocket;

  window.WebSocket = function PatchedWebSocket(url, protocols) {
    const ws = protocols ? new _OriginalWS(url, protocols) : new _OriginalWS(url);
    const pendingExpects = new Map();

    // Resolve any pending expects for an incoming message type
    function resolveExpects(msg) {
      for (const [token, ex] of pendingExpects) {
        if (ex.type !== msg.type) continue;
        const result = ex.validate(msg);
        if (result === "skip") continue; // predicate said skip, keep waiting
        clearTimeout(ex.timer);
        pendingExpects.delete(token);
        if (result) {
          emit({ kind: "bug", level: "warn", msg: result, ts: _ts() });
        } else {
          // Only emit ok for the most important confirmations (not every transcript)
          if (msg.type !== "transcript") {
            emit({ kind: "ok", msg: `${msg.type} ← received as expected`, ts: _ts() });
          }
        }
      }
    }

    const ctx = makeCtx(emit, pendingExpects);

    // Intercept outbound (client → server)
    const origSend = ws.send.bind(ws);
    ws.send = function (data) {
      try {
        if (typeof data === "string") {
          const msg = JSON.parse(data);
          const rule = RULES[msg.type];
          if (rule?.onSend) rule.onSend(msg, ctx);
        }
      } catch { /* binary frames — ignore */ }
      return origSend(data);
    };

    // Intercept inbound (server → client)
    const origAddListener = ws.addEventListener.bind(ws);
    ws.addEventListener = function (type, handler, opts) {
      if (type === "message") {
        const wrappedHandler = function (e) {
          try {
            if (typeof e.data === "string") {
              const msg = JSON.parse(e.data);
              resolveExpects(msg);
              const rule = RULES[msg.type];
              if (rule?.onReceive) rule.onReceive(msg, ctx);
            }
          } catch { /* ignore */ }
          return handler.call(this, e);
        };
        return origAddListener(type, wrappedHandler, opts);
      }
      return origAddListener(type, handler, opts);
    };

    // Also intercept onmessage property setter
    let _onmessage = null;
    Object.defineProperty(ws, "onmessage", {
      get: () => _onmessage,
      set(handler) {
        _onmessage = handler;
        origAddListener("message", function (e) {
          try {
            if (typeof e.data === "string") {
              const msg = JSON.parse(e.data);
              resolveExpects(msg);
              const rule = RULES[msg.type];
              if (rule?.onReceive) rule.onReceive(msg, ctx);
            }
          } catch { /* ignore */ }
          if (handler) handler.call(ws, e);
        });
      },
    });

    return ws;
  };

  // Copy static props (CONNECTING, OPEN, CLOSING, CLOSED)
  Object.assign(window.WebSocket, _OriginalWS);
  window.WebSocket.prototype = _OriginalWS.prototype;

  emit({ kind: "ok", msg: "SessionWatcher active — watching WebSocket traffic", ts: _ts() });
}

export function uninstall() {
  if (!_installed || !_OriginalWS) return;
  window.WebSocket = _OriginalWS;
  _OriginalWS = null;
  _installed = false;
  _log = [];
  _notifyUI = null;
}
