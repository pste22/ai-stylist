"""In-process ops metrics — uptime, live sessions, recent glitches.

Kept in memory so /health and /admin can show "is anyone hitting a wall right
now?" without a round-trip to Supabase. Process restart clears the buffers;
that's expected (Fly health checks still catch a dead machine).
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

_LOCK = threading.Lock()
_STARTED = time.time()
_MAX_ERRORS = 100
_MAX_REQS = 400

_errors: deque[dict] = deque(maxlen=_MAX_ERRORS)
_requests: deque[dict] = deque(maxlen=_MAX_REQS)
_sessions: dict[str, dict] = {}
_counters = {
    "errors_total": 0,
    "http_requests": 0,
    "http_5xx": 0,
    "ws_opens": 0,
    "ws_closes": 0,
    "circuit_opens": 0,
}


def started_at() -> float:
    return _STARTED


def uptime_s() -> int:
    return int(time.time() - _STARTED)


def record_error(kind: str, message: str, **extra: Any) -> None:
    """Record a glitch (gen failure, live drop, 5xx). Never raises."""
    rec = {
        "ts": time.time(),
        "kind": (kind or "error")[:80],
        "message": (message or "")[:400],
    }
    if extra:
        rec["extra"] = {k: str(v)[:120] for k, v in extra.items()}
    with _LOCK:
        _errors.appendleft(rec)
        _counters["errors_total"] += 1
        if kind == "circuit_open":
            _counters["circuit_opens"] += 1


def record_request(path: str, status: int, ms: float) -> None:
    rec = {
        "ts": time.time(),
        "path": (path or "")[:120],
        "status": int(status),
        "ms": round(float(ms), 1),
    }
    with _LOCK:
        _requests.appendleft(rec)
        _counters["http_requests"] += 1
        if status >= 500:
            _counters["http_5xx"] += 1


def session_open(session_id: str, *, user_id: str | None = None, name: str | None = None) -> None:
    if not session_id:
        return
    with _LOCK:
        _sessions[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "name": name or "guest",
            "started": time.time(),
        }
        _counters["ws_opens"] += 1


def session_close(session_id: str | None) -> None:
    if not session_id:
        return
    with _LOCK:
        _sessions.pop(session_id, None)
        _counters["ws_closes"] += 1


def active_sessions() -> list[dict]:
    now = time.time()
    with _LOCK:
        rows = []
        for rec in _sessions.values():
            rows.append({
                **rec,
                "age_s": int(now - rec["started"]),
            })
        rows.sort(key=lambda r: r["started"], reverse=True)
        return rows


def errors_since(seconds: float = 3600) -> list[dict]:
    cutoff = time.time() - seconds
    with _LOCK:
        return [e for e in list(_errors) if e["ts"] >= cutoff]


def snapshot() -> dict:
    """Compact dict for /health and the admin header."""
    now = time.time()
    hour_ago = now - 3600
    with _LOCK:
        err_hour = sum(1 for e in _errors if e["ts"] >= hour_ago)
        recent_ms = [r["ms"] for r in _requests if r["ts"] >= hour_ago]
        p95 = 0.0
        if recent_ms:
            ordered = sorted(recent_ms)
            p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
        return {
            "uptime_s": int(now - _STARTED),
            "started_at": int(_STARTED),
            "active_sessions": len(_sessions),
            "errors_last_hour": err_hour,
            "errors_total": _counters["errors_total"],
            "http_requests": _counters["http_requests"],
            "http_5xx": _counters["http_5xx"],
            "ws_opens": _counters["ws_opens"],
            "circuit_opens": _counters["circuit_opens"],
            "http_p95_ms": round(p95, 1),
        }


def reset_for_tests() -> None:
    """Wipe buffers — tests only."""
    with _LOCK:
        _errors.clear()
        _requests.clear()
        _sessions.clear()
        for k in _counters:
            _counters[k] = 0
