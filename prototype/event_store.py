"""Async event store — fire-and-forget writes to Supabase with JSONL fallback.

Architecture:
  Caller → in-process deque (non-blocking) → background flush thread
               ↓ every 30 s or 100 events
           Supabase events table (primary)
               ↓ on Supabase error
           data/events.jsonl (fallback — never lose an event)

Why this design for 10K users/day:
  - Voice pipeline is latency-critical. Event writes must NOT block it.
  - Supabase free tier: unlimited API calls but each HTTP round-trip is ~100–300 ms.
    Batching 100 events into one INSERT costs the same as writing 1.
  - JSONL fallback ensures durability even if Supabase is down for a few minutes.
  - At 10K users × ~5 events/session = 50K events/day → ~500 flushes/day at batch=100.
    Well within free-tier limits.

Env:
  SUPABASE_URL          Supabase project URL
  SUPABASE_SECRET_KEY   Service-role key

Thread safety: deque.appendleft/pop are GIL-protected. The lock only guards
the flush-in-progress check to prevent double-flush.
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ------------------------------------------------------------------ config
_FLUSH_INTERVAL = 30    # seconds between forced flushes
_FLUSH_BATCH    = 100   # flush early if queue reaches this size
_JSONL_PATH     = Path(__file__).parent / "data" / "events.jsonl"

# ------------------------------------------------------------------ queue
_queue: deque[dict] = deque()
_flush_lock = threading.Lock()

# ------------------------------------------------------------------ Supabase client (lazy)
_client = None
_client_lock = threading.Lock()


def _db():
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is not None:
            return _client
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SECRET_KEY", "")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY must be set")
        _client = create_client(url, key)
    return _client


# ------------------------------------------------------------------ enqueue (non-blocking)

def log_event(
    event: str,
    *,
    session_id: str,
    user_id: str | None = None,
    product_id: str | None = None,
    product_name: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
    **extra: Any,
) -> None:
    """Enqueue an event for async write.  Returns immediately — never blocks."""
    record: dict = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "event": event,
    }
    if user_id:
        record["user_id"] = user_id
    if product_id:
        record["product_id"] = product_id
    if product_name:
        record["product_name"] = product_name
    if input_tokens is not None:
        record["input_tokens"] = input_tokens
    if output_tokens is not None:
        record["output_tokens"] = output_tokens
    if cost_usd is not None:
        record["cost_usd"] = cost_usd
    if extra:
        record["meta"] = extra

    _queue.append(record)

    # Trigger an early flush if the queue is getting large
    if len(_queue) >= _FLUSH_BATCH:
        _trigger_flush()


# Convenience wrappers (keep call sites clean)

def log_would_buy(
    product_id: str,
    *,
    session_id: str,
    user_id: str | None = None,
    product_name: str | None = None,
) -> None:
    log_event(
        "would_buy",
        session_id=session_id,
        user_id=user_id,
        product_id=product_id,
        product_name=product_name,
    )


def log_buy_click(
    product_id: str,
    *,
    session_id: str,
    user_id: str | None = None,
    product_name: str | None = None,
) -> None:
    log_event(
        "buy_click",
        session_id=session_id,
        user_id=user_id,
        product_id=product_id,
        product_name=product_name,
    )


def log_session_cost(
    *,
    session_id: str,
    user_id: str | None = None,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> None:
    log_event(
        "session_cost",
        session_id=session_id,
        user_id=user_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
    )


# ------------------------------------------------------------------ flush logic

def _trigger_flush() -> None:
    """Start a one-shot flush thread if one isn't already running."""
    if _flush_lock.acquire(blocking=False):
        t = threading.Thread(target=_do_flush_and_release, daemon=True, name="event-flush")
        t.start()
    # If lock not acquired, a flush is already in flight — that's fine.


def _do_flush_and_release() -> None:
    try:
        _flush()
    finally:
        _flush_lock.release()


def _flush() -> None:
    """Drain the queue and write to Supabase (with JSONL fallback)."""
    if not _queue:
        return

    # Snapshot the queue — take up to _FLUSH_BATCH items
    batch: list[dict] = []
    for _ in range(_FLUSH_BATCH):
        if not _queue:
            break
        batch.append(_queue.popleft())

    if not batch:
        return

    # --- Primary: Supabase batch insert ---
    try:
        _db().table("events").insert(batch).execute()
        return  # success — don't write to JSONL
    except Exception as exc:
        print(f"[event_store] Supabase flush failed ({len(batch)} events): {exc}")

    # --- Fallback: append to JSONL (durability guarantee) ---
    _jsonl_append(batch)


def _jsonl_append(records: list[dict]) -> None:
    _JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _JSONL_PATH.open("a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


# ------------------------------------------------------------------ background flush thread

def _background_loop() -> None:
    while True:
        time.sleep(_FLUSH_INTERVAL)
        try:
            _flush()
        except Exception as exc:
            print(f"[event_store] background flush error: {exc}")


_flush_thread = threading.Thread(
    target=_background_loop, daemon=True, name="event-flush-bg"
)
_flush_thread.start()


# ------------------------------------------------------------------ migration helper

def migrate_jsonl_to_supabase(jsonl_path: Path | None = None) -> int:
    """One-time: read existing events.jsonl and insert into Supabase events table.

    product_id values that don't exist in the products table are set to null so
    old demo events (with ids like 's02', 't01') don't violate the FK constraint.

    Returns the number of rows inserted.
    """
    path = jsonl_path or _JSONL_PATH
    if not path.exists():
        print("[event_store] No events.jsonl to migrate.")
        return 0

    records = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    if not records:
        return 0

    # Fetch the set of product IDs that actually exist in Supabase
    try:
        result = _db().table("products").select("id").execute()
        known_ids = {row["id"] for row in (result.data or [])}
    except Exception as exc:
        print(f"[event_store] could not fetch known product ids: {exc}")
        known_ids = set()

    # Null out product_id for any event referencing an unknown product
    nulled = 0
    for r in records:
        if r.get("product_id") and r["product_id"] not in known_ids:
            r["product_id"] = None
            nulled += 1
    if nulled:
        print(f"[event_store] nulled product_id on {nulled} events (unknown/demo products)")

    # Batch in chunks of 500 to stay within Supabase request limits
    total = 0
    chunk_size = 500
    for i in range(0, len(records), chunk_size):
        chunk = records[i : i + chunk_size]
        try:
            _db().table("events").insert(chunk).execute()
            total += len(chunk)
            print(f"[event_store] migrated {total}/{len(records)} events…")
        except Exception as exc:
            print(f"[event_store] migration chunk {i}–{i+chunk_size} failed: {exc}")

    return total
