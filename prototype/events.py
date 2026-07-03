"""Purchase-intent signal logging (P2-8).

Routes events through event_store for async Supabase writes (primary) with
automatic JSONL fallback for durability.  Call sites are unchanged from the
original file — same function names, same signatures.

Priority:
  1. Supabase events table  (async, batched, never blocks the voice pipeline)
  2. data/events.jsonl      (synchronous fallback if Supabase is down)
"""
from __future__ import annotations

import uuid


def new_session_id() -> str:
    """A throwaway anonymous id to group events within one conversation."""
    return uuid.uuid4().hex


def log_event(
    event: str,
    *,
    session_id: str,
    user_id: str | None = None,
    **fields,
) -> dict:
    """Enqueue an event for async write.  Returns the record dict immediately.

    Extra kwargs are forwarded to event_store.log_event (product_id,
    product_name, input_tokens, output_tokens, cost_usd, …).
    """
    try:
        from event_store import log_event as _async_log
        _async_log(event, session_id=session_id, user_id=user_id, **fields)
    except Exception as exc:
        # Last-resort synchronous JSONL write — never lose an event
        _jsonl_fallback(event, session_id=session_id, user_id=user_id, **fields)
        print(f"[events] event_store unavailable, wrote to JSONL: {exc}")

    # Return the record for any caller that still inspects it
    from datetime import datetime, timezone
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "event": event,
        **({"user_id": user_id} if user_id else {}),
        **fields,
    }


def log_would_buy(
    product_id: str,
    *,
    session_id: str,
    user_id: str | None = None,
    product_name: str | None = None,
) -> dict:
    """Core purchase-intent signal: shopper tapped 'Would Buy' or said they'd buy it."""
    return log_event(
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
) -> dict:
    """Affiliate handoff: shopper tapped 'Buy →' and was sent to the retailer."""
    return log_event(
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
) -> dict:
    """End-of-session LLM cost summary."""
    return log_event(
        "session_cost",
        session_id=session_id,
        user_id=user_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
    )


# ------------------------------------------------------------------
# JSONL fallback (synchronous, used only when event_store is unavailable)
# ------------------------------------------------------------------

def _jsonl_fallback(event: str, *, session_id: str, **fields) -> None:
    import json
    from datetime import datetime, timezone
    from pathlib import Path

    path = Path(__file__).parent / "data" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "event": event,
        **fields,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
