"""Chat history store — Supabase-backed, 30-day active window with archiving.

Schema: run the SQL block in docs/chat_history_schema.sql once in Supabase SQL Editor.

Design decisions for scale:
- Partial indexes: one for active (NOT is_archived), one for archived — queries never
  scan both halves of the table.
- user_id denormalized onto chat_messages so user-scoped queries skip the join.
- Messages capped at 500 per session on read to prevent runaway payloads.
- create_session / end_session are fire-and-forget (errors logged, never raised) so
  a DB hiccup never kills the live voice session.
"""
from __future__ import annotations

import os
import uuid
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


def create_session(user_id: str) -> str | None:
    """Insert a new chat_session row, return its UUID string (or None on error)."""
    try:
        sid = str(uuid.uuid4())
        _db().table("chat_sessions").insert({
            "id":         sid,
            "user_id":    user_id,
            "started_at": _now_iso(),
            "is_archived": False,
        }).execute()
        return sid
    except Exception as exc:
        print(f"  ! chat_store.create_session: {exc}")
        return None


def end_session(chat_session_id: str, title: str | None = None) -> None:
    """Mark session ended and set an auto-generated title (first user message)."""
    try:
        update: dict = {"ended_at": _now_iso()}
        if title:
            update["title"] = title[:120]  # cap at 120 chars
        _db().table("chat_sessions").update(update).eq("id", chat_session_id).execute()
    except Exception as exc:
        print(f"  ! chat_store.end_session: {exc}")


def save_message(chat_session_id: str, user_id: str, role: str, content: str) -> None:
    """Append one message (role='user'|'mira') to chat_messages."""
    if not content.strip():
        return
    # Strip internal context prefixes before storing
    if content.startswith("[CONTEXT:") or content.startswith("[START SESSION]"):
        return
    try:
        _db().table("chat_messages").insert({
            "session_id": chat_session_id,
            "user_id":    user_id,
            "role":       role,
            "content":    content.strip(),
            "created_at": _now_iso(),
        }).execute()
    except Exception as exc:
        print(f"  ! chat_store.save_message: {exc}")


def get_recent_sessions(user_id: str, limit: int = 20) -> list[dict]:
    """Return most recent non-archived sessions for a user (newest first)."""
    try:
        rows = (
            _db()
            .table("chat_sessions")
            .select("id, started_at, ended_at, title")
            .eq("user_id", user_id)
            .eq("is_archived", False)
            .order("started_at", desc=True)
            .limit(limit)
            .execute()
        )
        return rows.data or []
    except Exception as exc:
        print(f"  ! chat_store.get_recent_sessions: {exc}")
        return []


def get_archived_sessions(user_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
    """Return archived sessions with pagination."""
    try:
        rows = (
            _db()
            .table("chat_sessions")
            .select("id, started_at, ended_at, title")
            .eq("user_id", user_id)
            .eq("is_archived", True)
            .order("started_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return rows.data or []
    except Exception as exc:
        print(f"  ! chat_store.get_archived_sessions: {exc}")
        return []


def get_messages(chat_session_id: str, limit: int = 500) -> list[dict]:
    """Return messages for a session, oldest first, capped at limit."""
    try:
        rows = (
            _db()
            .table("chat_messages")
            .select("role, content, created_at")
            .eq("session_id", chat_session_id)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        return rows.data or []
    except Exception as exc:
        print(f"  ! chat_store.get_messages: {exc}")
        return []
