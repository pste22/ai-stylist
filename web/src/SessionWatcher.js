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

  // ── show_more: must get products back within 6 s ─────────────────────────
  show_more: {
    onSend(msg, ctx) {
      ctx.expectIncoming("products", 6000,
        (resp) => {
          if (!Array.isArray(resp.items)) return "products message missing items array";
          if (resp.items.length === 0 && resp.show_more !== false)
            return "empty products batch but show_more !== false (button will loop forever)";
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

  // ── text_input: must get a Mira transcript within 12 s ───────────────────
  text_input: {
    onSend(msg, ctx) {
      if (!msg.text?.trim()) {
        ctx.bug("warn", "text_input sent with empty text");
        return;
      }
      ctx.expectIncoming("transcript", 12000,
        (resp) => resp.who === "mira" ? null : "skip", // skip if who=you
        "text_input sent but Mira never responded with a transcript within 12 s"
      );
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
      looks.forEach((look, i) => {
        if (!look.slots) {
          ctx.bug("warn", `looks[${i}] "${look.name}": missing slots object`);
          return;
        }
        if (!look.slots.outfit?.length) {
          ctx.bug("warn", `looks[${i}] "${look.name}": empty outfit slot`);
        }
      });
      ctx.ok(`looks: ${looks.length} complete look(s) received`);
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
        () => null,
        "init sent but no initial product picks arrived within 8 s"
      );
      ctx.ok(`init sent — user: ${msg.name || "guest"}, mode: ${msg.text_mode ? "text" : "voice"}`);
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
