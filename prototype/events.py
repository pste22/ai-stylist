"""Purchase-intent signal logging (P2-8).

We can't measure what we don't capture. This is the tiny primitive a "Buy" button (or a
voice "I'd buy that") calls so we can later compute purchase-INTENT — the number that,
paired with cost-per-session (P2-10), decides our pricing model (see docs/12-...).

Phase 2 keeps it dead simple: append one JSON line per event to data/events.jsonl.
No PII — just an anonymous session id, the product, and a timestamp.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

_EVENTS = Path(__file__).parent / "data" / "events.jsonl"


def new_session_id() -> str:
    """A throwaway anonymous id to group events within one conversation."""
    return uuid.uuid4().hex


def log_event(event: str, *, session_id: str, **fields) -> dict:
    """Append a single event as one JSON line. Returns the written record."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "event": event,
        **fields,
    }
    _EVENTS.parent.mkdir(parents=True, exist_ok=True)
    with _EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record


def log_would_buy(product_id: str, *, session_id: str, product_name: str | None = None) -> dict:
    """The core purchase-intent signal: shopper tapped 'Buy' / said they'd buy it."""
    return log_event(
        "would_buy",
        session_id=session_id,
        product_id=product_id,
        product_name=product_name,
    )
