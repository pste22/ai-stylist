"""User memory store — Supabase-backed cross-session shopping history.

Stores user identity, style preferences, and product interaction history so Mira
can greet returning shoppers by name, reference past picks, and honour known budgets
without asking the same questions twice.

Schema: run prototype/schema.sql once in the Supabase SQL Editor.
Env:    SUPABASE_URL + SUPABASE_SECRET_KEY (service-role key, never reaches browser).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone


def _db():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SECRET_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY must be set")
    return create_client(url, key)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# In-process cache: avoids a Supabase round-trip on every reconnect within the same
# server lifetime. TTL of 5 minutes keeps it fresh without staling across long gaps.
_cache: dict[str, tuple[str, bool, float]] = {}  # user_id → (prompt, is_returning, ts)
_CACHE_TTL = 300  # seconds


def _days_ago(iso: str) -> int:
    try:
        then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - then).days
    except Exception:
        return 0


def load_user(user_id: str, name: str) -> tuple[str, bool]:
    """Upsert the user record and return (memory_prompt, is_returning)."""
    import time
    cached = _cache.get(user_id)
    if cached and (time.monotonic() - cached[2]) < _CACHE_TTL:
        return cached[0], cached[1]

    db = _db()

    existing = db.table("users").select("*").eq("user_id", user_id).execute()
    is_returning = bool(existing.data)

    import time
    if is_returning:
        db.table("users").update({"name": name, "last_seen": _now_iso()}).eq("user_id", user_id).execute()
        user = existing.data[0]
    else:
        db.table("users").insert({"user_id": user_id, "name": name}).execute()
        result = _new_user_prompt(name), False
        _cache[user_id] = (*result, time.monotonic())
        return result

    result = _returning_user_prompt(db, user), True
    _cache[user_id] = (*result, time.monotonic())
    return result


def _new_user_prompt(name: str) -> str:
    return (
        f"NEW SHOPPER: {name} is visiting Mira for the first time.\n"
        f"Open with a warm, friendly greeting using their name — e.g. 'Hey {name}! "
        f"So great to meet you — I'm Mira.' Then ask about their budget "
        f"(\"Do you have a budget in mind?\") before showing product options."
    )


def _returning_user_prompt(db, user: dict) -> str:
    name = user["name"]
    days = _days_ago(user.get("last_seen") or user.get("first_seen", ""))

    lines = [f"RETURNING SHOPPER: {name}"]
    if days == 0:
        lines.append(
            f"They were here earlier today. Greet them by first name ({name}) warmly "
            "but briefly — e.g. 'Hey Prashant, you're back!' then get straight to it."
        )
    elif days == 1:
        lines.append(
            f"Last visit: yesterday. Open with a warm greeting by first name ({name})."
        )
    elif days < 14:
        lines.append(
            f"Last visit: {days} days ago. Open with a warm greeting by first name ({name})."
        )
    else:
        weeks = days // 7
        lines.append(
            f"Last visit: {weeks} week{'s' if weeks > 1 else ''} ago. "
            f"Open with a warm 'welcome back' greeting using their first name ({name}) — "
            "e.g. 'Welcome back Prashant! It's been a while…'"
        )

    prefs = db.table("user_preferences").select("*").eq("user_id", user["user_id"]).execute()
    if prefs.data:
        p = prefs.data[0]
        if p.get("budget_max"):
            bmin = p.get("budget_min")
            if bmin:
                lines.append(f"Known budget: ${bmin}–${p['budget_max']}. Don't ask again.")
            else:
                lines.append(f"Known budget: up to ${p['budget_max']}. Don't ask again.")
        else:
            lines.append("Budget: unknown — ask once before showing options.")
        if p.get("vibes"):
            lines.append(f"Style vibes they like: {', '.join(p['vibes'])}.")
        if p.get("body_notes"):
            lines.append(f"Fit notes: {p['body_notes']}.")
    else:
        lines.append("Budget: unknown — ask once before showing options.")

    # Query loved and bought separately so `shown` rows can never crowd them out.
    loved_rows = (
        db.table("user_history")
        .select("product_name")
        .eq("user_id", user["user_id"])
        .in_("action", ["would_buy", "wishlist"])
        .order("ts", desc=True)
        .limit(10)
        .execute()
    )
    bought_rows = (
        db.table("user_history")
        .select("product_name")
        .eq("user_id", user["user_id"])
        .eq("action", "buy_click")
        .order("ts", desc=True)
        .limit(10)
        .execute()
    )
    loved = list(dict.fromkeys(h["product_name"] for h in loved_rows.data if h["product_name"]))
    bought = list(dict.fromkeys(h["product_name"] for h in bought_rows.data if h["product_name"]))
    if loved:
        lines.append(
            f"Items they loved / wishlisted: {', '.join(loved[:5])}. "
            "Reference these naturally — e.g. 'Since you loved the [X], you might also like…'"
        )
    if bought:
        lines.append(
            f"Items they clicked Buy on: {', '.join(bought[:5])}. "
            "You can ask how they turned out."
        )

    lines.append(
        "Use this memory naturally — don't recite it back or make a list. "
        "Weave it in like a friend who remembers."
    )
    return "\n".join(lines)


def log_product_event(user_id: str, product_id: str, product_name: str, action: str) -> None:
    """Record that a product was shown, buy-clicked, or wishlisted."""
    try:
        _db().table("user_history").insert({
            "user_id": user_id,
            "product_id": product_id,
            "product_name": product_name,
            "action": action,
        }).execute()
        _cache.pop(user_id, None)  # invalidate so next session loads fresh history
    except Exception as exc:
        print(f"  ! user_store.log_product_event: {exc}")


def get_loved_ids(user_id: str) -> list[str]:
    """Return product IDs the user has wishlisted/loved, most recent first."""
    try:
        result = (
            _db().table("user_history")
            .select("product_id")
            .eq("user_id", user_id)
            .in_("action", ["would_buy", "wishlist"])
            .order("ts", desc=True)
            .limit(50)
            .execute()
        )
        return list(dict.fromkeys(h["product_id"] for h in result.data if h["product_id"]))
    except Exception as exc:
        print(f"  ! user_store.get_loved_ids: {exc}")
        return []


def unlike_product(user_id: str, product_id: str) -> None:
    """Remove all would_buy/wishlist rows for this product — user un-liked it."""
    try:
        _db().table("user_history").delete().eq("user_id", user_id).eq("product_id", product_id).in_("action", ["would_buy", "wishlist"]).execute()
        _cache.pop(user_id, None)
    except Exception as exc:
        print(f"  ! user_store.unlike_product: {exc}")


def save_preferences(user_id: str, **kwargs) -> None:
    """Upsert style preferences (budget_min, budget_max, vibes, body_notes)."""
    try:
        _db().table("user_preferences").upsert(
            {"user_id": user_id, "updated_at": _now_iso(), **kwargs},
            on_conflict="user_id",
        ).execute()
    except Exception as exc:
        print(f"  ! user_store.save_preferences: {exc}")
