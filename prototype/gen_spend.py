"""Daily generation spend guardrails.

Pure helpers so the user/global caps can be unit-tested without booting the
Live server. `live_server` owns the in-memory ledger and env defaults.
"""
from __future__ import annotations


SPEND_MSG = {
    "disabled":   "Try-on is paused right now — please check back soon.",
    "global_cap": "Mira's try-on studio has hit today's limit — back tomorrow! ✨",
    "user_cap":   "You've reached today's try-on limit — see you tomorrow ✨",
}


def parse_demo_emails(raw: str | None) -> frozenset[str]:
    """Comma-separated emails that skip the per-user cap (still count globally)."""
    return frozenset(e.strip().lower() for e in (raw or "").split(",") if e.strip())


def is_demo_email(email: str | None, demo_emails: frozenset[str] | set[str]) -> bool:
    if not email:
        return False
    return email.strip().lower() in demo_emails


def check(
    *,
    disabled: bool,
    total: float,
    user_spent: float,
    est: float,
    global_cap: float,
    user_cap: float,
    enforce_user_cap: bool,
) -> str | None:
    """Return a SPEND_MSG key if generation should be blocked, else None."""
    if disabled:
        return "disabled"
    if total + est > global_cap:
        return "global_cap"
    if enforce_user_cap and user_spent + est > user_cap:
        return "user_cap"
    return None


def is_cap_message(message: str | None) -> bool:
    """True for daily-limit copy — the UI should not offer 'Try again'."""
    if not message:
        return False
    text = message.lower()
    return (
        "try-on limit" in text
        or "today's limit" in text
        or "paused right now" in text
    )
