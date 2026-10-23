"""Password-protected founder admin: uptime, funnel, user activity.

Auth is cookie + HTTP Basic against MIRA_ADMIN_PASSWORD. If that env var is
unset the routes 404 so the path isn't advertised on a public deploy.
"""
from __future__ import annotations

import base64
import collections
import hashlib
import hmac
import html
import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import ops_metrics

COOKIE_NAME = "mira_admin"
COOKIE_MAX_AGE = 7 * 24 * 3600
LOGIN_WINDOW_S = 15 * 60
LOGIN_MAX_FAILS = 8

# Conservative India-fashion affiliate averages — estimates only.
_COMMISSION = {
    "amazon": 0.04,
    "myntra": 0.08,
    "ajio": 0.07,
    "nykaa": 0.10,
    "ajio.com": 0.07,
    "myntra.com": 0.08,
    "amazon.in": 0.04,
    "amazon.com": 0.04,
}
_DEFAULT_COMMISSION = 0.06

_login_fails: dict[str, list[float]] = {}


def admin_password() -> str:
    return (os.environ.get("MIRA_ADMIN_PASSWORD") or "").strip()


def configured() -> bool:
    return bool(admin_password())


def cookie_token(password: str | None = None) -> str:
    secret = (password or admin_password()).encode("utf-8")
    return hmac.new(secret, b"mira-admin-v1", hashlib.sha256).hexdigest()


def _parse_cookies(header: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (header or "").split(";"):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _basic_password(header: str) -> str | None:
    if not header or not header.lower().startswith("basic "):
        return None
    try:
        raw = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
    except Exception:
        return None
    if ":" not in raw:
        return None
    _user, pw = raw.split(":", 1)
    return pw


def authorized(headers: Any) -> bool:
    """True when cookie or HTTP Basic matches MIRA_ADMIN_PASSWORD."""
    pw = admin_password()
    if not pw:
        return False
    get = headers.get if hasattr(headers, "get") else lambda _k, _d="": ""
    cookie = _parse_cookies(get("Cookie") or get("cookie") or "")
    if hmac.compare_digest(cookie.get(COOKIE_NAME, ""), cookie_token(pw)):
        return True
    supplied = _basic_password(get("Authorization") or get("authorization") or "")
    if supplied is not None and hmac.compare_digest(supplied, pw):
        return True
    header_pw = (get("X-Mira-Admin") or "").strip()
    if header_pw and hmac.compare_digest(header_pw, pw):
        return True
    return False


def login_blocked(ip: str) -> bool:
    now = time.time()
    fails = [t for t in _login_fails.get(ip, []) if now - t < LOGIN_WINDOW_S]
    _login_fails[ip] = fails
    return len(fails) >= LOGIN_MAX_FAILS


def record_login_fail(ip: str) -> None:
    _login_fails.setdefault(ip, []).append(time.time())


def record_login_ok(ip: str) -> None:
    _login_fails.pop(ip, None)


def set_cookie_header() -> str:
    return (
        f"{COOKIE_NAME}={cookie_token()}; Path=/; Max-Age={COOKIE_MAX_AGE}; "
        "HttpOnly; Secure; SameSite=Strict"
    )


def clear_cookie_header() -> str:
    return f"{COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict"


# ── snapshot / funnel ─────────────────────────────────────────────────────────

def _ts_to_epoch(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _platform_of(product_id: str, catalog: dict | None, row: dict | None = None) -> str:
    if row:
        meta = row.get("meta") or {}
        for key in ("platform", "retailer", "source"):
            val = (row.get(key) or meta.get(key) or "")
            if val:
                return str(val).lower()
    prod = (catalog or {}).get(product_id) or {}
    for key in ("retailer", "retailer_label", "source"):
        val = prod.get(key)
        if val:
            return str(val).lower()
    return ""


def _commission_rate(platform: str) -> float:
    key = (platform or "").lower()
    if key in _COMMISSION:
        return _COMMISSION[key]
    for name, rate in _COMMISSION.items():
        if name in key:
            return rate
    return _DEFAULT_COMMISSION


def _price_of(product_id: str, catalog: dict | None, row: dict | None = None) -> float:
    if row and row.get("price") is not None:
        try:
            return float(row["price"])
        except (TypeError, ValueError):
            pass
    prod = (catalog or {}).get(product_id) or {}
    try:
        return float(prod.get("price") or 0)
    except (TypeError, ValueError):
        return 0.0


def build_snapshot(
    *,
    events: list[dict],
    history: list[dict],
    users: list[dict],
    health: dict,
    errors: list[dict],
    live_sessions: list[dict] | None = None,
    catalog: dict | None = None,
    days: int = 7,
    platform: str = "",
    now: float | None = None,
) -> dict:
    """Pure aggregation — tests feed lists, production feeds Supabase/JSONL."""
    now = now if now is not None else time.time()
    days = max(1, min(int(days or 7), 90))
    since = now - days * 86400
    platform = (platform or "").strip().lower()
    catalog = catalog or {}

    def in_window(row: dict) -> bool:
        ts = _ts_to_epoch(row.get("ts") or row.get("created_at") or row.get("last_seen"))
        return ts >= since if ts else True

    def plat_ok(row: dict) -> bool:
        if not platform:
            return True
        pid = row.get("product_id") or ""
        got = _platform_of(pid, catalog, row)
        return platform in got

    ev = [r for r in events if in_window(r) and plat_ok(r)]
    hist = [r for r in history if in_window(r) and plat_ok(r)]
    user_rows = [u for u in users if in_window(u)]

    sessions = {r.get("session_id") for r in ev if r.get("session_id")}
    session_starts = [r for r in ev if r.get("event") == "session_start"]
    shown = [r for r in hist if r.get("action") == "shown"]
    saves = [r for r in hist if r.get("action") in ("would_buy", "wishlist")]
    saves += [r for r in ev if r.get("event") == "would_buy"]
    buys = [r for r in hist if r.get("action") == "buy_click"]
    buys += [r for r in ev if r.get("event") == "buy_click"]

    # Dedupe buy/save rows that landed in both tables.
    def _dedupe(rows: list[dict], kind: str) -> list[dict]:
        seen: set[tuple] = set()
        out = []
        for r in rows:
            key = (
                r.get("user_id") or r.get("session_id"),
                r.get("product_id"),
                kind,
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(r)
        return out

    saves = _dedupe(saves, "save")
    buys = _dedupe(buys, "buy")

    est_revenue = 0.0
    by_platform: dict[str, dict] = collections.defaultdict(
        lambda: {"buy_clicks": 0, "revenue": 0.0}
    )
    for row in buys:
        pid = row.get("product_id") or ""
        plat = _platform_of(pid, catalog, row) or "unknown"
        price = _price_of(pid, catalog, row)
        rev = price * _commission_rate(plat)
        est_revenue += rev
        by_platform[plat]["buy_clicks"] += 1
        by_platform[plat]["revenue"] += rev

    stats: dict[str, dict] = collections.defaultdict(
        lambda: {"shown": 0, "saves": 0, "buys": 0, "name": "", "platform": ""}
    )
    for r in shown:
        pid = r.get("product_id") or ""
        if not pid:
            continue
        stats[pid]["shown"] += 1
        stats[pid]["name"] = r.get("product_name") or stats[pid]["name"]
        stats[pid]["platform"] = _platform_of(pid, catalog, r)
    for r in saves:
        pid = r.get("product_id") or ""
        if not pid:
            continue
        stats[pid]["saves"] += 1
        stats[pid]["name"] = r.get("product_name") or stats[pid]["name"]
        stats[pid]["platform"] = stats[pid]["platform"] or _platform_of(pid, catalog, r)
    for r in buys:
        pid = r.get("product_id") or ""
        if not pid:
            continue
        stats[pid]["buys"] += 1
        stats[pid]["name"] = r.get("product_name") or stats[pid]["name"]
        stats[pid]["platform"] = stats[pid]["platform"] or _platform_of(pid, catalog, r)
        if not stats[pid]["name"] and pid in catalog:
            stats[pid]["name"] = catalog[pid].get("name") or pid

    def conversion(row: dict) -> float:
        shown_n = row["shown"] or 1
        return (row["saves"] / shown_n) if row["shown"] else (1.0 if row["saves"] else 0.0)

    ranked = []
    for pid, row in stats.items():
        name = row["name"] or (catalog.get(pid) or {}).get("name") or pid
        ranked.append({
            "product_id": pid,
            "name": name,
            "platform": row["platform"] or _platform_of(pid, catalog, None),
            "shown": row["shown"],
            "saves": row["saves"],
            "buys": row["buys"],
            "save_rate": round(conversion(row), 3),
            "buy_rate": round((row["buys"] / row["saves"]) if row["saves"] else 0.0, 3),
        })
    top = sorted(ranked, key=lambda r: (r["saves"] + r["buys"] * 2, r["shown"]), reverse=True)[:10]
    engaged = [r for r in ranked if r["shown"] >= 3]
    bottom = sorted(engaged, key=lambda r: (r["save_rate"], r["saves"], -r["shown"]))[:10]

    # Daily bars for a simple 30-day (or `days`) sparkline.
    buckets: dict[str, int] = {}
    for r in ev + hist:
        ts = _ts_to_epoch(r.get("ts") or r.get("created_at"))
        if not ts:
            continue
        day = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        buckets[day] = buckets.get(day, 0) + 1
    chart = []
    for i in range(days - 1, -1, -1):
        day = (datetime.fromtimestamp(now, tz=timezone.utc).date() - timedelta(days=i)).isoformat()
        chart.append({"day": day, "n": buckets.get(day, 0)})

    n_sessions = max(len(sessions), len(session_starts), 0)
    activity = []
    for r in hist[:80]:
        activity.append({
            "ts": r.get("ts"),
            "kind": r.get("action") or "history",
            "user_id": r.get("user_id"),
            "name": "",
            "product": r.get("product_name") or r.get("product_id") or "",
        })
    for r in ev[:80]:
        if r.get("event") in ("session_cost",):
            continue
        activity.append({
            "ts": r.get("ts"),
            "kind": r.get("event") or "event",
            "user_id": r.get("user_id"),
            "name": (r.get("meta") or {}).get("name") if isinstance(r.get("meta"), dict) else "",
            "product": r.get("product_name") or r.get("product_id") or "",
        })
    activity.sort(key=lambda r: _ts_to_epoch(r.get("ts")), reverse=True)
    user_names = {u.get("user_id"): u.get("name") for u in users}
    for row in activity:
        if not row.get("name"):
            row["name"] = user_names.get(row.get("user_id")) or ""

    return {
        "days": days,
        "platform": platform,
        "health": health,
        "funnel": {
            "sessions": n_sessions,
            "shown": len(shown),
            "saves": len(saves),
            "buy_clicks": len(buys),
            "est_revenue_usd": round(est_revenue, 2),
            "by_platform": {
                k: {"buy_clicks": v["buy_clicks"], "revenue": round(v["revenue"], 2)}
                for k, v in sorted(by_platform.items(), key=lambda kv: -kv[1]["revenue"])
            },
        },
        "users": {
            "total": len(user_rows),
            "recent": [
                {
                    "user_id": u.get("user_id"),
                    "name": u.get("name") or "—",
                    "first_seen": u.get("first_seen"),
                    "last_seen": u.get("last_seen"),
                    "tier": "free",
                }
                for u in user_rows[:50]
            ],
        },
        "top_products": top,
        "bottom_products": bottom,
        "live_sessions": live_sessions or [],
        "activity": activity[:60],
        "errors": errors[:40],
        "chart": chart,
        "note": "Pro/paid tier is not live yet — every shopper is counted as free.",
    }


def _select(table: str, columns: str, order: str, limit: int, desc: bool = True) -> list[dict]:
    try:
        from product_store import _db
        q = _db().table(table).select(columns)
        q = q.order(order, desc=desc).limit(limit)
        return q.execute().data or []
    except Exception as exc:
        print(f"[admin] {table} query failed: {exc}")
        return []


def _jsonl_events(limit: int = 400) -> list[dict]:
    path = os.path.join(os.path.dirname(__file__), "data", "events.jsonl")
    if not os.path.exists(path):
        return []
    rows: list[dict] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return rows[-limit:]


def load_snapshot(*, days: int = 7, platform: str = "", catalog: dict | None = None,
                  health: dict | None = None) -> dict:
    events = _select(
        "events",
        "ts,session_id,user_id,event,product_id,product_name,meta,cost_usd",
        "ts",
        800,
    )
    if not events:
        events = _jsonl_events()
    history = _select(
        "user_history",
        "ts,user_id,product_id,product_name,action",
        "ts",
        800,
    )
    users = _select(
        "users",
        "user_id,name,first_seen,last_seen",
        "last_seen",
        80,
    )
    return build_snapshot(
        events=events,
        history=history,
        users=users,
        health=health or {},
        errors=ops_metrics.errors_since(86400),
        live_sessions=ops_metrics.active_sessions(),
        catalog=catalog or {},
        days=days,
        platform=platform,
    )


# ── HTML ──────────────────────────────────────────────────────────────────────

def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _fmt_ts(value: Any) -> str:
    ts = _ts_to_epoch(value)
    if not ts:
        return "—"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def _fmt_uptime(seconds: int) -> str:
    seconds = max(0, int(seconds or 0))
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def render_login(error: str = "") -> str:
    err = f'<p class="err">{_esc(error)}</p>' if error else ""
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>Mira admin</title>
<style>{_CSS}</style>
</head><body class="login">
<main class="card">
  <p class="kicker">Mira · founder</p>
  <h1>Admin</h1>
  <p class="lede">Uptime, sessions, and shopper activity. Not a public page.</p>
  {err}
  <form id="f">
    <label>Password <input id="p" type="password" autocomplete="current-password" autofocus></label>
    <button type="submit">Enter</button>
  </form>
</main>
<script>
document.getElementById("f").addEventListener("submit", async (e) => {{
  e.preventDefault();
  const pw = document.getElementById("p").value;
  const r = await fetch("/admin/session", {{
    headers: {{ "X-Mira-Admin": pw }},
    credentials: "same-origin",
  }});
  if (r.ok) location.replace("/admin");
  else document.querySelector(".lede").textContent =
    r.status === 429 ? "Too many tries — wait 15 minutes." : "Wrong password.";
}});
</script>
</body></html>
"""


def render_dashboard(snap: dict, *, days: int, platform: str) -> str:
    h = snap.get("health") or {}
    funnel = snap.get("funnel") or {}
    status = (h.get("status") or "unknown")
    degraded = status != "ok"
    max_bar = max((c["n"] for c in snap.get("chart") or [{"n": 1}]), default=1) or 1
    bars = "".join(
        f'<span class="bar" title="{_esc(c["day"])}: {c["n"]}" style="height:{max(6, int(c["n"] / max_bar * 64))}px"></span>'
        for c in (snap.get("chart") or [])
    )
    plat_opts = ["", "amazon", "myntra", "ajio", "nykaa"]
    chips = "".join(
        f'<a class="chip{" on" if platform == p else ""}" href="/admin?days={days}&amp;platform={_esc(p)}">'
        f'{p or "all"}</a>'
        for p in plat_opts
    )
    day_chips = "".join(
        f'<a class="chip{" on" if days == d else ""}" href="/admin?days={d}&amp;platform={_esc(platform)}">{d}d</a>'
        for d in (1, 7, 30)
    )

    def product_table(rows: list[dict], empty: str) -> str:
        if not rows:
            return f'<p class="muted">{_esc(empty)}</p>'
        body = "".join(
            "<tr>"
            f"<td>{_esc(r.get('name'))}</td>"
            f"<td>{_esc(r.get('platform') or '—')}</td>"
            f"<td>{r.get('shown', 0)}</td>"
            f"<td>{r.get('saves', 0)}</td>"
            f"<td>{r.get('buys', 0)}</td>"
            f"<td>{int((r.get('save_rate') or 0) * 100)}%</td>"
            "</tr>"
            for r in rows
        )
        return (
            "<table><thead><tr><th>Product</th><th>Platform</th><th>Shown</th>"
            "<th>Saves</th><th>Buys</th><th>Save rate</th></tr></thead>"
            f"<tbody>{body}</tbody></table>"
        )

    users = "".join(
        "<tr>"
        f"<td>{_esc(u.get('name'))}</td>"
        f"<td class='mono'>{_esc((u.get('user_id') or '')[:8])}</td>"
        f"<td>{_esc(_fmt_ts(u.get('last_seen')))}</td>"
        f"<td>{_esc(u.get('tier'))}</td>"
        "</tr>"
        for u in (snap.get("users") or {}).get("recent") or []
    ) or "<tr><td colspan='4' class='muted'>No signed-in shoppers yet.</td></tr>"

    live = "".join(
        "<tr>"
        f"<td>{_esc(s.get('name') or 'guest')}</td>"
        f"<td class='mono'>{_esc((s.get('user_id') or 'anon')[:8])}</td>"
        f"<td>{s.get('age_s', 0)}s</td>"
        "</tr>"
        for s in snap.get("live_sessions") or []
    ) or "<tr><td colspan='3' class='muted'>No live voice/chat sessions.</td></tr>"

    activity = "".join(
        "<tr>"
        f"<td>{_esc(_fmt_ts(a.get('ts')))}</td>"
        f"<td>{_esc(a.get('kind'))}</td>"
        f"<td>{_esc(a.get('name') or a.get('user_id') or 'guest')}</td>"
        f"<td>{_esc(a.get('product'))}</td>"
        "</tr>"
        for a in snap.get("activity") or []
    ) or "<tr><td colspan='4' class='muted'>No product events in this window.</td></tr>"

    glitches = "".join(
        "<tr>"
        f"<td>{_esc(_fmt_ts(e.get('ts')))}</td>"
        f"<td>{_esc(e.get('kind'))}</td>"
        f"<td>{_esc(e.get('message'))}</td>"
        "</tr>"
        for e in snap.get("errors") or []
    ) or "<tr><td colspan='3' class='muted'>No glitches recorded since last deploy.</td></tr>"

    plat_rev = "".join(
        f"<li>{_esc(k)} · {v['buy_clicks']} clicks · ${v['revenue']:.2f}</li>"
        for k, v in (funnel.get("by_platform") or {}).items()
    ) or "<li class='muted'>No affiliate click-outs yet.</li>"

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<meta http-equiv="refresh" content="30">
<title>Mira admin</title>
<style>{_CSS}</style>
</head><body>
<header>
  <div>
    <p class="kicker">Mira · founder</p>
    <h1>Activity</h1>
  </div>
  <div class="status {'bad' if degraded else 'ok'}">
    {('degraded' if degraded else 'live')} · commit {_esc(h.get('commit') or 'dev')}
  </div>
  <a class="logout" href="/admin/logout">Log out</a>
</header>

<section class="filters">
  <div>{day_chips}</div>
  <div>{chips}</div>
</section>

<section class="grid">
  <article><p class="kicker">Uptime</p><strong>{_esc(_fmt_uptime(h.get('uptime_s') or 0))}</strong></article>
  <article><p class="kicker">Live sessions</p><strong>{h.get('active_sessions', 0)}</strong></article>
  <article><p class="kicker">Spend today</p><strong>${h.get('spend_today_usd', 0)}</strong>
    <span class="muted">/ {h.get('spend_global_cap_usd', 15)} cap</span></article>
  <article><p class="kicker">Errors / hour</p><strong>{h.get('errors_last_hour', 0)}</strong></article>
  <article><p class="kicker">Gen circuit</p><strong>{'OPEN' if h.get('gen_circuit_open') else 'ok'}</strong></article>
  <article><p class="kicker">HTTP p95</p><strong>{h.get('http_p95_ms', 0)}ms</strong></article>
</section>

<section>
  <h2>Funnel · last {days}d</h2>
  <div class="funnel">
    <div><span>Sessions</span><strong>{funnel.get('sessions', 0)}</strong></div>
    <div><span>Shown</span><strong>{funnel.get('shown', 0)}</strong></div>
    <div><span>Saves</span><strong>{funnel.get('saves', 0)}</strong></div>
    <div><span>Buy clicks</span><strong>{funnel.get('buy_clicks', 0)}</strong></div>
    <div><span>Est. commission</span><strong>${funnel.get('est_revenue_usd', 0):.2f}</strong></div>
  </div>
  <p class="muted">{_esc(snap.get('note'))}</p>
  <ul class="plats">{plat_rev}</ul>
  <div class="chart" aria-hidden="true">{bars}</div>
</section>

<section>
  <h2>Live right now</h2>
  <table><thead><tr><th>Shopper</th><th>User</th><th>Age</th></tr></thead>
  <tbody>{live}</tbody></table>
</section>

<section class="split">
  <div>
    <h2>Top products</h2>
    {product_table(snap.get("top_products") or [], "No engagement yet.")}
  </div>
  <div>
    <h2>Low engagement</h2>
    {product_table(snap.get("bottom_products") or [], "Need at least 3 shows to rank a miss.")}
  </div>
</section>

<section>
  <h2>Recent shoppers</h2>
  <table><thead><tr><th>Name</th><th>User</th><th>Last seen</th><th>Tier</th></tr></thead>
  <tbody>{users}</tbody></table>
</section>

<section>
  <h2>User activity</h2>
  <table><thead><tr><th>When</th><th>Event</th><th>Who</th><th>Product</th></tr></thead>
  <tbody>{activity}</tbody></table>
</section>

<section>
  <h2>Glitches</h2>
  <table><thead><tr><th>When</th><th>Kind</th><th>Message</th></tr></thead>
  <tbody>{glitches}</tbody></table>
</section>
</body></html>
"""


_CSS = """
:root { --bg:#f6f4f1; --ink:#141414; --muted:#767676; --accent:#b23a48; --line:rgba(20,20,20,.12); }
* { box-sizing:border-box; }
html,body { margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.45 "Instrument Sans", Inter, system-ui, sans-serif; }
h1,h2 { font-family: Fraunces, Georgia, serif; font-weight:500; margin:0 0 .4rem; }
h1 { font-size:2rem; } h2 { font-size:1.15rem; margin-top:0; }
header { display:flex; align-items:flex-end; gap:1rem; padding:1.5rem 1.5rem 0; }
header .status { margin-left:auto; font-size:.8rem; letter-spacing:.04em; text-transform:uppercase; }
.status.ok { color:#2f6b3a; } .status.bad { color:var(--accent); }
.logout { color:var(--ink); font-size:.85rem; }
.kicker { text-transform:uppercase; letter-spacing:.12em; font-size:.68rem; color:var(--muted); margin:0 0 .25rem; }
section { padding:1.25rem 1.5rem; border-top:1px solid var(--line); }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(9rem,1fr)); gap:.75rem; border-top:none; }
.grid article { background:#fff; padding:.9rem 1rem; border:1px solid var(--line); }
.grid strong { font-size:1.35rem; display:block; }
.filters { display:flex; gap:1rem; flex-wrap:wrap; border-top:none; padding-bottom:0; }
.chip { display:inline-block; margin-right:.35rem; padding:.2rem .65rem; border:1px solid var(--line);
  color:var(--ink); text-decoration:none; font-size:.8rem; }
.chip.on { background:var(--ink); color:#fff; }
.funnel { display:flex; gap:.75rem; flex-wrap:wrap; }
.funnel div { background:#fff; border:1px solid var(--line); padding:.8rem 1rem; min-width:7rem; }
.funnel span { display:block; font-size:.72rem; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); }
.muted { color:var(--muted); font-size:.85rem; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size:.8rem; }
table { width:100%; border-collapse:collapse; font-size:.9rem; }
th,td { text-align:left; padding:.4rem .5rem .4rem 0; border-bottom:1px solid var(--line); vertical-align:top; }
th { font-size:.72rem; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); font-weight:500; }
.split { display:grid; grid-template-columns:1fr 1fr; gap:1.5rem; }
@media (max-width:800px){ .split { grid-template-columns:1fr; } }
.chart { display:flex; align-items:flex-end; gap:3px; height:72px; margin-top:1rem; }
.bar { flex:1; background:#141414; opacity:.75; min-width:4px; }
.plats { padding-left:1.1rem; }
body.login { min-height:100dvh; display:grid; place-items:center; }
.card { background:#fff; padding:2rem; width:min(22rem,92vw); border:1px solid var(--line); }
label { display:block; font-size:.8rem; margin:1rem 0 .4rem; }
input { width:100%; padding:.65rem .7rem; border:1px solid var(--line); background:var(--bg); font:inherit; }
button { margin-top:1rem; background:var(--ink); color:#fff; border:0; padding:.65rem 1rem; font:inherit; cursor:pointer; }
.err { color:var(--accent); }
a { color:var(--ink); }
"""


# ── HTTP dispatch (no websockets dependency) ─────────────────────────────────

_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def handle_request(
    path: str,
    headers: Any,
    client_ip: str,
    *,
    health: dict | None = None,
    catalog: dict | None = None,
) -> tuple[int, dict[str, str], str]:
    """Return (status, headers, body) for /admin and /api/admin/*."""
    parsed = urlparse(path or "")
    route = parsed.path.rstrip("/") or "/"
    qs = parse_qs(parsed.query)
    days = 7
    try:
        days = int((qs.get("days") or ["7"])[0])
    except ValueError:
        days = 7
    platform = ((qs.get("platform") or [""])[0] or "").strip().lower()
    hdrs = dict(_SECURITY_HEADERS)

    if not configured():
        return 404, {**hdrs, "Content-Type": "text/plain; charset=utf-8"}, "not found"

    if route == "/admin/logout":
        hdrs["Set-Cookie"] = clear_cookie_header()
        hdrs["Location"] = "/admin"
        return 302, hdrs, ""

    if route == "/admin/session":
        if login_blocked(client_ip):
            return 429, {**hdrs, "Content-Type": "text/plain; charset=utf-8"}, "too many attempts"
        if authorized(headers):
            record_login_ok(client_ip)
            hdrs["Set-Cookie"] = set_cookie_header()
            hdrs["Content-Type"] = "application/json"
            return 200, hdrs, json.dumps({"ok": True})
        record_login_fail(client_ip)
        return 401, {**hdrs, "Content-Type": "application/json"}, json.dumps({"ok": False})

    if not authorized(headers):
        if route.startswith("/api/"):
            hdrs["Content-Type"] = "application/json"
            hdrs["WWW-Authenticate"] = 'Basic realm="mira-admin"'
            return 401, hdrs, json.dumps({"error": "unauthorized"})
        hdrs["Content-Type"] = "text/html; charset=utf-8"
        return 200, hdrs, render_login()

    snap = load_snapshot(days=days, platform=platform, catalog=catalog, health=health)
    if route in ("/api/admin/activity", "/api/admin"):
        hdrs["Content-Type"] = "application/json"
        return 200, hdrs, json.dumps(snap, default=str)
    if route == "/admin":
        hdrs["Content-Type"] = "text/html; charset=utf-8"
        return 200, hdrs, render_dashboard(snap, days=snap["days"], platform=platform)
    return 404, {**hdrs, "Content-Type": "text/plain; charset=utf-8"}, "not found"
