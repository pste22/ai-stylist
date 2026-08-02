/**
 * SessionWatcher — real-time session validator + tester reporter.
 *
 * Patches window.WebSocket globally so every message in both directions is
 * intercepted, validated, and measured.  Works for the real user session —
 * not a synthetic test.
 *
 * Three layers:
 *   1. Validation rules   — assert expected message sequences and payloads
 *   2. Latency tracking   — measure time from user action to first response
 *   3. Session reporting  — POST a summary + bug list to Supabase at session end
 *
 * Active in dev mode automatically; add ?debug to any URL to enable in prod.
 *
 * Exported API:
 *   install()       — patch WS; safe to call once at app boot
 *   uninstall()     — restore original WS
 *   setUICallback() — called by the overlay to receive live log entries
 *   getReport()     — return current session report object
 */

// ─── Config ───────────────────────────────────────────────────────────────────

const MAX_LOG      = 80;
const REPORT_URL   = "/mira-ws/session-report"; // backend endpoint (optional)
// If you have a direct Supabase REST URL you can set it here instead:
const SUPABASE_URL = typeof import.meta !== "undefined"
  ? (import.meta.env?.VITE_SUPABASE_URL || null)
  : null;
const SUPABASE_KEY = typeof import.meta !== "undefined"
  ? (import.meta.env?.VITE_SUPABASE_ANON_KEY || null)
  : null;

// ─── Session state ────────────────────────────────────────────────────────────
// Shared across all rules — resets when a new WS connection opens.

function makeSession() {
  return {
    id:            crypto.randomUUID(),
    startedAt:     Date.now(),
    mode:          "unknown",   // "text" | "voice"
    userName:      null,
    userId:        null,

    // Counters
    turns:         0,           // user text_input messages sent
    productsShown: 0,           // total product items received
    showMoreClicks: 0,
    looksReceived: 0,
    vsSearches:    0,

    // Latency samples (ms) — one per turn
    latencySamples: [],         // { turn, ms, type }

    // Per-turn records
    turnLog:       [],          // { turn, text, responseMs, transcriptChars, productCount }
    _turnStart:    null,        // timestamp when text_input was sent
    _currentTurn:  0,

    // Bug + ok counts
    bugs:          [],          // { level, msg, detail, ts, turn }
    okCount:       0,

    // State machine tracking
    _lastState:    null,
    _thinkingAt:   null,
  };
}

let _session = makeSession();

function _recordBug(level, msg, detail) {
  _session.bugs.push({ level, msg, detail: detail || null, ts: _ts(), turn: _session._currentTurn });
}

function _recordOk() {
  _session.okCount++;
}

// ─── Validation rules ─────────────────────────────────────────────────────────

const RULES = {

  // ── init ─────────────────────────────────────────────────────────────────────
  init: {
    onSend(msg, ctx) {
      _session.mode     = msg.text_mode ? "text" : "voice";
      _session.userName = msg.name || "guest";
      _session.userId   = msg.user_id || null;

      ctx.expectIncoming("products", 8000,
        (resp) => {
          if (!resp.items?.length)
            return "initial products batch is empty — no personalized picks on load";
          return null;
        },
        "init sent but no initial product picks arrived within 8 s"
      );
      ctx.ok(`session started — user: ${msg.name || "guest"}, mode: ${_session.mode}`);
    },
  },

  // ── text_input — full response sequence ──────────────────────────────────────
  text_input: {
    onSend(msg, ctx) {
      if (!msg.text?.trim()) {
        ctx.bug("warn", "text_input sent with empty text");
        return;
      }
      _session.turns++;
      _session._currentTurn = _session.turns;
      _session._turnStart   = Date.now();
      _session.turnLog.push({
        turn:            _session.turns,
        text:            msg.text.slice(0, 120),
        responseMs:      null,
        transcriptChars: 0,
        productCount:    0,
      });

      // 1. state:thinking within 3 s
      ctx.expectIncoming("state", 3000,
        (resp) => resp.state === "thinking" ? null : "skip",
        `turn ${_session.turns}: no state:thinking within 3 s after text_input`
      );

      // 2. Non-empty Mira transcript within 12 s
      ctx.expectIncoming("transcript", 12000,
        (resp) => {
          if (resp.who !== "mira") return "skip";
          if (!resp.text?.trim()) return "transcript received but text is empty — blank Mira response";
          return null;
        },
        `turn ${_session.turns}: Mira never responded within 12 s`
      );

      // 3. Turn completes within 25 s
      ctx.expectIncoming("state", 25000,
        (resp) => (resp.state === "idle" || resp.state === "reacting") ? null : "skip",
        `turn ${_session.turns}: turn never completed — state stuck, possible hang`
      );
    },
  },

  // ── show_more — count + timing ────────────────────────────────────────────────
  show_more: {
    onSend(msg, ctx) {
      _session.showMoreClicks++;
      const clickedAt = Date.now();

      ctx.expectIncoming("products", 6000,
        (resp) => {
          if (!Array.isArray(resp.items))
            return "products response missing items array";

          const n   = resp.items.length;
          const ms  = Date.now() - clickedAt;
          _session.latencySamples.push({ turn: _session._currentTurn, type: "show_more", ms });

          if (n === 0) {
            return resp.show_more === false
              ? null  // catalog exhausted — correct
              : "show_more: 0 items returned but show_more !== false — button will loop";
          }
          if (n > 3)
            return `show_more: returned ${n} items — server should cap at 3`;
          if (n < 3 && resp.show_more === true)
            return `show_more: only ${n}/3 items returned but server says more exist — catalog gap`;

          ctx.ok(`show_more: ${n} product(s) in ${ms} ms`);
          return null;
        },
        "show_more: no products response within 6 s — button may never re-enable"
      );
    },
  },

  // ── visual_search ─────────────────────────────────────────────────────────────
  visual_search: {
    onSend(msg, ctx) {
      if (!msg.image) { ctx.bug("warn", "visual_search sent without image payload"); return; }
      _session.vsSearches++;
      const sentAt = Date.now();

      ctx.expectIncoming("visual_search_results", 25000,
        (resp) => {
          if (!Array.isArray(resp.items)) return "visual_search_results missing items array";
          const ms = Date.now() - sentAt;
          _session.latencySamples.push({ turn: _session._currentTurn, type: "visual_search", ms });
          ctx.ok(`visual_search: ${resp.items.length} match(es) in ${ms} ms`);
          return null;
        },
        "visual_search: no results within 25 s — spinner may be stuck"
      );
    },
  },

  // ── transcript — measure latency + check content ─────────────────────────────
  transcript: {
    onReceive(msg, ctx) {
      if (msg.who !== "mira") return;

      const text = (msg.text || "").trim();

      // Record first-byte latency for the current turn
      if (_session._turnStart) {
        const ms = Date.now() - _session._turnStart;
        _session._turnStart = null; // only record once per turn
        _session.latencySamples.push({ turn: _session._currentTurn, type: "transcript_first", ms });
        const rec = _session.turnLog.find(t => t.turn === _session._currentTurn);
        if (rec) rec.responseMs = ms;
      }

      // Accumulate chars in turnLog
      const rec = _session.turnLog.find(t => t.turn === _session._currentTurn);
      if (rec) rec.transcriptChars += text.length;

      // Detect error phrases leaked into Mira's response
      const errorPhrases = [
        "i'm sorry, i encountered", "an error occurred",
        "i cannot process",         "i'm unable to",
        "something went wrong",     "i don't have access",
      ];
      if (text.length > 20 && errorPhrases.some(p => text.toLowerCase().includes(p)))
        ctx.bug("warn", `Mira response contains error phrase: "${text.slice(0, 80)}"`);

      // Flag very short complete-seeming responses (< 20 chars, not mid-stream)
      if (text.endsWith(".") && text.length < 20)
        ctx.bug("warn", `Mira gave suspiciously short response: "${text}"`);
    },
  },

  // ── state — track the state machine ──────────────────────────────────────────
  state: {
    onReceive(msg, ctx) {
      const prev  = _session._lastState;
      const next  = msg.state;
      _session._lastState = next;

      if (next === "thinking") _session._thinkingAt = Date.now();

      // Illegal transitions
      const illegal = {
        idle:     [],
        thinking: [],
        talking:  ["idle"],       // shouldn't jump straight from idle to talking
        reacting: ["thinking"],   // shouldn't react without talking first
      };
      const forbidden = illegal[next] || [];
      if (forbidden.includes(prev))
        ctx.bug("warn", `state transition ${prev} → ${next} is unexpected`);
    },
  },

  // ── products — payload + count checks ────────────────────────────────────────
  products: {
    onReceive(msg, ctx) {
      const items  = msg.items || [];
      _session.productsShown += items.length;

      const rec = _session.turnLog.find(t => t.turn === _session._currentTurn);
      if (rec) rec.productCount += items.length;

      // Broken items
      const broken = items.filter(p => !p.image_url || !p.affiliate_url || !p.name);
      if (broken.length)
        ctx.bug("warn",
          `products: ${broken.length}/${items.length} item(s) missing image_url/affiliate_url/name`,
          broken.map(p => p.id || p.name).join(", ")
        );

      // Too many in one batch (UI only renders 3)
      if (items.length > 6)
        ctx.bug("warn", `products: ${items.length} items in one batch — UI shows max 3, rest hidden`);

      if (items.length > 0 && broken.length === 0)
        ctx.ok(`products: ${items.length} item(s) — all fields present`);
    },
  },

  // ── looks — slot completeness ─────────────────────────────────────────────────
  looks: {
    onReceive(msg, ctx) {
      const looks = msg.items || [];
      _session.looksReceived += looks.length;

      if (!looks.length) { ctx.bug("warn", "looks: empty array — look deck will be blank"); return; }

      let anyBroken = false;
      looks.forEach((look, i) => {
        if (!look.slots) {
          ctx.bug("warn", `looks[${i}] "${look.name}": missing slots object`); anyBroken = true; return;
        }
        if (!look.slots.outfit?.length) {
          ctx.bug("warn", `looks[${i}] "${look.name}": empty outfit slot`); anyBroken = true;
        }
        if (!look.total_price)
          ctx.bug("warn", `looks[${i}] "${look.name}": missing total_price`);
      });
      if (!anyBroken)
        ctx.ok(`looks: ${looks.length} complete look(s) with all slots populated`);
    },
  },

  // ── visual_search_results ─────────────────────────────────────────────────────
  visual_search_results: {
    onReceive(msg, ctx) {
      if (msg.error) { ctx.bug("error", `visual_search server error: ${msg.error}`); return; }
      ctx.ok(`visual_search_results: ${(msg.items || []).length} match(es) — query: "${msg.query || ""}"`);
    },
  },

  // ── add_to_cart ───────────────────────────────────────────────────────────────
  add_to_cart: {
    onReceive(msg, ctx) {
      const items = msg.items || [];
      if (!items.length) { ctx.bug("warn", "add_to_cart: empty items — cart not updated"); return; }
      const broken = items.filter(p => !p.id || !p.name);
      if (broken.length)
        ctx.bug("warn", `add_to_cart: ${broken.length} item(s) missing id or name`);
      else
        ctx.ok(`add_to_cart: ${items.length} item(s) — ${items.map(p => p.name).join(", ")}`);
    },
  },

  // ── server errors ─────────────────────────────────────────────────────────────
  error: {
    onReceive(msg, ctx) {
      ctx.bug("error", `server error: ${msg.message || JSON.stringify(msg)}`);
    },
  },
};

// ─── Context object passed to each rule ───────────────────────────────────────

function makeCtx(emit, pendingExpects) {
  return {
    bug(level, msg, detail) {
      _recordBug(level, msg, detail);
      emit({ kind: "bug", level, msg, detail, ts: _ts() });
    },
    ok(msg) {
      _recordOk();
      emit({ kind: "ok", msg, ts: _ts() });
    },
    expectIncoming(type, timeoutMs, validate, timeoutMsg) {
      const token = `${type}_${Date.now()}_${Math.random()}`;
      const timer = setTimeout(() => {
        pendingExpects.delete(token);
        _recordBug("error", timeoutMsg, null);
        emit({ kind: "bug", level: "error", msg: timeoutMsg, ts: _ts() });
      }, timeoutMs);
      pendingExpects.set(token, { type, validate, timer });
    },
  };
}

function _ts() {
  return new Date().toLocaleTimeString("en-IN", { hour12: false });
}

// ─── Session report ───────────────────────────────────────────────────────────

export function getReport() {
  const now        = Date.now();
  const durationMs = now - _session.startedAt;
  const latencies  = _session.latencySamples;

  const avgLatency = latencies.length
    ? Math.round(latencies.reduce((s, l) => s + l.ms, 0) / latencies.length)
    : null;

  const p95Latency = latencies.length
    ? latencies.map(l => l.ms).sort((a, b) => a - b)[Math.floor(latencies.length * 0.95)]
    : null;

  const errorBugs = _session.bugs.filter(b => b.level === "error");
  const warnBugs  = _session.bugs.filter(b => b.level === "warn");

  // Health score: start at 100, deduct for bugs and timeouts
  let health = 100;
  health -= errorBugs.length * 20;
  health -= warnBugs.length  * 5;
  if (avgLatency && avgLatency > 8000) health -= 10;
  if (avgLatency && avgLatency > 15000) health -= 20;
  health = Math.max(0, Math.min(100, health));

  return {
    sessionId:       _session.id,
    userId:          _session.userId,
    userName:        _session.userName,
    mode:            _session.mode,
    durationMs,
    turns:           _session.turns,
    productsShown:   _session.productsShown,
    showMoreClicks:  _session.showMoreClicks,
    looksReceived:   _session.looksReceived,
    vsSearches:      _session.vsSearches,
    avgLatencyMs:    avgLatency,
    p95LatencyMs:    p95Latency,
    latencySamples:  latencies,
    turnLog:         _session.turnLog,
    bugs:            _session.bugs,
    errorCount:      errorBugs.length,
    warnCount:       warnBugs.length,
    okCount:         _session.okCount,
    healthScore:     health,
    reportedAt:      new Date().toISOString(),
  };
}

// ─── Reporter — sends report to Supabase at session end ───────────────────────

async function _sendReport() {
  const report = getReport();
  if (report.turns === 0) return; // nothing happened, skip

  // Always log to console for the developer
  console.groupCollapsed(
    `%c[SessionWatcher] Session ended — health: ${report.healthScore}/100 | ${report.errorCount} errors, ${report.warnCount} warnings | ${report.turns} turns`,
    `color: ${report.healthScore >= 80 ? "#4ade80" : report.healthScore >= 50 ? "#fb923c" : "#f87171"}; font-weight: bold`
  );
  console.table(report.turnLog);
  console.log("Full report:", report);
  console.groupEnd();

  // POST to Supabase if credentials are available
  if (!SUPABASE_URL || !SUPABASE_KEY) return;

  try {
    await fetch(`${SUPABASE_URL}/rest/v1/watcher_sessions`, {
      method:  "POST",
      headers: {
        "Content-Type":  "application/json",
        "apikey":         SUPABASE_KEY,
        "Authorization": `Bearer ${SUPABASE_KEY}`,
        "Prefer":        "return=minimal",
      },
      body: JSON.stringify(report),
    });
  } catch (e) {
    console.warn("[SessionWatcher] Failed to POST report:", e);
  }
}

// ─── Core WS patcher ─────────────────────────────────────────────────────────

let _installed    = false;
let _OriginalWS   = null;
let _notifyUI     = null;
let _log          = [];

export function setUICallback(fn) {
  _notifyUI = fn;
  _log.forEach(fn);
}

function emit(entry) {
  _log = [entry, ..._log].slice(0, MAX_LOG);
  _notifyUI?.(entry);
  if (entry.kind === "bug")
    console[entry.level === "error" ? "error" : "warn"](
      `%c[SessionWatcher] ${entry.level.toUpperCase()}: ${entry.msg}`,
      "color: #f87171; font-weight: bold",
      entry.detail || ""
    );
}

export function install() {
  if (_installed) return;
  _installed  = true;
  _OriginalWS = window.WebSocket;

  window.WebSocket = function PatchedWebSocket(url, protocols) {
    // Reset session state for each new WS connection
    _session = makeSession();
    _log     = [];

    const ws = protocols ? new _OriginalWS(url, protocols) : new _OriginalWS(url);
    const pendingExpects = new Map();

    function resolveExpects(msg) {
      for (const [token, ex] of pendingExpects) {
        if (ex.type !== msg.type) continue;
        const result = ex.validate(msg);
        if (result === "skip") continue;
        clearTimeout(ex.timer);
        pendingExpects.delete(token);
        if (result) {
          _recordBug("warn", result, null);
          emit({ kind: "bug", level: "warn", msg: result, ts: _ts() });
        } else if (msg.type !== "transcript" && msg.type !== "state") {
          _recordOk();
          emit({ kind: "ok", msg: `${msg.type} ← received as expected`, ts: _ts() });
        }
      }
    }

    const ctx = makeCtx(emit, pendingExpects);

    // Outbound (client → server)
    const origSend = ws.send.bind(ws);
    ws.send = function (data) {
      try {
        if (typeof data === "string") {
          const msg = JSON.parse(data);
          RULES[msg.type]?.onSend?.(msg, ctx);
        }
      } catch { /* binary audio frames */ }
      return origSend(data);
    };

    // Inbound (server → client) — addEventListener path
    const origAddListener = ws.addEventListener.bind(ws);
    ws.addEventListener = function (type, handler, opts) {
      if (type === "message") {
        const wrapped = function (e) {
          try {
            if (typeof e.data === "string") {
              const msg = JSON.parse(e.data);
              resolveExpects(msg);
              RULES[msg.type]?.onReceive?.(msg, ctx);
            }
          } catch { /* ignore */ }
          return handler.call(this, e);
        };
        return origAddListener(type, wrapped, opts);
      }
      return origAddListener(type, handler, opts);
    };

    // Inbound — onmessage property path (used by useMiraVoice.js)
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
              RULES[msg.type]?.onReceive?.(msg, ctx);
            }
          } catch { /* ignore */ }
          handler?.call(ws, e);
        });
      },
    });

    // Send report when WS closes
    ws.addEventListener("close", () => _sendReport());

    // Copy static constants
    Object.assign(window.WebSocket, _OriginalWS);
    window.WebSocket.prototype = _OriginalWS.prototype;

    emit({ kind: "ok", msg: "SessionWatcher active — watching all WS traffic", ts: _ts() });
    return ws;
  };

  Object.assign(window.WebSocket, _OriginalWS);
  window.WebSocket.prototype = _OriginalWS.prototype;
}

export function uninstall() {
  if (!_installed || !_OriginalWS) return;
  window.WebSocket = _OriginalWS;
  _OriginalWS = _notifyUI = null;
  _installed  = false;
  _log        = [];
}
