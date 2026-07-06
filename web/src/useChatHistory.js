import { useCallback, useState } from "react";
import { supabase } from "./supabaseClient.js";

// Keyset (cursor) pagination — O(log n) at any depth via B-tree index seek.
// Cursor = { started_at, id } of the last row seen. Stable under concurrent inserts.

const PAGE = 20;
const THIRTY_DAYS_AGO = () =>
  new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();

export function useChatHistory(userId) {
  const [sessions, setSessions]       = useState([]);
  const [archived, setArchived]       = useState([]);
  const [messages, setMessages]       = useState(null);
  const [activeSession, setActive]    = useState(null);
  const [loadingList, setLoadingList] = useState(false);
  const [loadingMsgs, setLoadingMsgs] = useState(false);

  // Cursors: last row's { started_at, id } — null means "start from the top"
  const [recentCursor, setRecentCursor]   = useState(null);
  const [archivedCursor, setArchivedCursor] = useState(null);
  const [hasMoreRecent, setHasMoreRecent]   = useState(true);
  const [hasMoreArchived, setHasMore]       = useState(true);

  // ── Recent sessions (last 30 days) ──────────────────────────────────────────
  const loadSessions = useCallback(async (reset = false) => {
    if (!userId) return;
    if (!reset && !hasMoreRecent) return;
    setLoadingList(true);

    const cursor = reset ? null : recentCursor;
    let q = supabase
      .from("chat_sessions")
      .select("id, started_at, ended_at, title")
      .eq("user_id", userId)
      .eq("is_archived", false)
      .gte("started_at", THIRTY_DAYS_AGO())
      .order("started_at", { ascending: false })
      .order("id",          { ascending: false })
      .limit(PAGE);

    // Keyset: skip rows we've already seen using the last cursor position
    if (cursor) {
      q = q.or(
        `started_at.lt.${cursor.started_at},` +
        `and(started_at.eq.${cursor.started_at},id.lt.${cursor.id})`
      );
    }

    const { data } = await q;
    const rows = data ?? [];

    setSessions(prev => reset ? rows : [...prev, ...rows]);
    setHasMoreRecent(rows.length === PAGE);
    if (rows.length > 0) {
      const last = rows[rows.length - 1];
      setRecentCursor({ started_at: last.started_at, id: last.id });
    }
    if (reset) setRecentCursor(null);
    setLoadingList(false);
  }, [userId, recentCursor, hasMoreRecent]);

  // ── Archived sessions (> 30 days, load on demand) ───────────────────────────
  const loadArchived = useCallback(async () => {
    if (!userId || !hasMoreArchived) return;

    let q = supabase
      .from("chat_sessions")
      .select("id, started_at, ended_at, title")
      .eq("user_id", userId)
      .eq("is_archived", true)
      .order("started_at", { ascending: false })
      .order("id",          { ascending: false })
      .limit(PAGE);

    if (archivedCursor) {
      q = q.or(
        `started_at.lt.${archivedCursor.started_at},` +
        `and(started_at.eq.${archivedCursor.started_at},id.lt.${archivedCursor.id})`
      );
    }

    const { data } = await q;
    const rows = data ?? [];
    setArchived(prev => [...prev, ...rows]);
    setHasMore(rows.length === PAGE);
    if (rows.length > 0) {
      const last = rows[rows.length - 1];
      setArchivedCursor({ started_at: last.started_at, id: last.id });
    }
  }, [userId, archivedCursor, hasMoreArchived]);

  // ── Messages within a session ────────────────────────────────────────────────
  // Messages are bounded per session (max ~500) so a simple created_at keyset
  // is sufficient — no infinite scroll needed here, just a single fetch.
  const loadMessages = useCallback(async (session) => {
    setActive(session);
    setLoadingMsgs(true);
    const { data } = await supabase
      .from("chat_messages")
      .select("role, content, created_at")
      .eq("session_id", session.id)
      .order("created_at", { ascending: true })
      .limit(500);
    setMessages(data ?? []);
    setLoadingMsgs(false);
  }, []);

  const closeMessages = useCallback(() => {
    setMessages(null);
    setActive(null);
  }, []);

  return {
    sessions, archived, messages, activeSession,
    loadingList, loadingMsgs, hasMoreRecent, hasMoreArchived,
    loadSessions, loadArchived, loadMessages, closeMessages,
  };
}
