"""Thread-safe TTL cache with optional background refresh.

Used by product_store and user_store to keep hot data in process memory
so Supabase is only hit on a cold-start or after the TTL expires.

Design choices:
  - Pure stdlib — no Redis, no Memcached, no extra cost.
  - Background refresh: a daemon thread re-fetches the value *before* TTL
    expires so callers always get a warm result (no thundering-herd on expiry).
  - Thread-safe via RLock; get() never blocks a caller while a refresh runs —
    it returns the stale value and lets the background thread catch up.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional


class TTLCache:
    """Single-key TTL cache with optional background auto-refresh.

    Args:
        ttl:            Seconds until the cached value is considered stale.
        refresh_fn:     Zero-arg callable that fetches a fresh value.
                        If provided, a daemon thread refreshes the value
                        automatically every `ttl * refresh_ratio` seconds.
        refresh_ratio:  Fraction of TTL at which the background refresh fires
                        (default 0.8 → refresh at 80% of TTL, before it expires).
    """

    def __init__(
        self,
        ttl: float,
        refresh_fn: Optional[Callable[[], Any]] = None,
        refresh_ratio: float = 0.8,
    ) -> None:
        self._ttl = ttl
        self._refresh_fn = refresh_fn
        self._lock = threading.RLock()
        self._value: Any = _MISSING
        self._expires_at: float = 0.0
        self._refresh_thread: Optional[threading.Thread] = None

        if refresh_fn is not None:
            interval = max(ttl * refresh_ratio, 10)
            self._start_refresh_thread(interval)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self) -> Any:
        """Return cached value, or _MISSING if cache is cold/expired."""
        with self._lock:
            if self._value is not _MISSING and time.monotonic() < self._expires_at:
                return self._value
            return _MISSING

    def set(self, value: Any) -> None:
        with self._lock:
            self._value = value
            self._expires_at = time.monotonic() + self._ttl

    def invalidate(self) -> None:
        with self._lock:
            self._value = _MISSING
            self._expires_at = 0.0

    def get_or_load(self, loader: Callable[[], Any]) -> Any:
        """Return cached value; call loader() on miss and cache the result."""
        hit = self.get()
        if hit is not _MISSING:
            return hit
        value = loader()
        self.set(value)
        return value

    # ------------------------------------------------------------------
    # Background refresh
    # ------------------------------------------------------------------

    def _start_refresh_thread(self, interval: float) -> None:
        def _loop() -> None:
            while True:
                time.sleep(interval)
                try:
                    value = self._refresh_fn()  # type: ignore[misc]
                    self.set(value)
                except Exception as exc:
                    print(f"[cache] background refresh failed: {exc}")

        t = threading.Thread(target=_loop, daemon=True, name="cache-refresh")
        t.start()
        self._refresh_thread = t


class MultiKeyTTLCache:
    """Per-key TTL cache — think of it as a dict where each entry expires.

    Used for user-profile caching (one entry per user_id).
    """

    def __init__(self, ttl: float) -> None:
        self._ttl = ttl
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Any:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return _MISSING
            value, exp = entry
            if time.monotonic() < exp:
                return value
            del self._store[key]
            return _MISSING

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (value, time.monotonic() + self._ttl)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def get_or_load(self, key: str, loader: Callable[[], Any]) -> Any:
        hit = self.get(key)
        if hit is not _MISSING:
            return hit
        value = loader()
        self.set(key, value)
        return value


class _Missing:
    """Sentinel — distinguishes a cached None from a cache miss."""
    def __repr__(self) -> str:
        return "<MISSING>"


_MISSING = _Missing()
