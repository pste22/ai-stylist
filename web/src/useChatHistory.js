import { useCallback, useState } from "react";
import { supabase } from "./supabaseClient.js";

const RECENT_LIMIT   = 20;
const ARCHIVED_LIMIT = 20;

export function useChatHistory(userId) {
  const [sessions, setSessions]         = useState([]);
  const [archived, setArchived]         = useState([]);
  const [messages, setMessages]         = useState(null); // null = none loaded
  const [activeSession, setActive]      = useState(null);
  const [loadingList, setLoadingList]   = useState(false);
  const [loadingMsgs, setLoadingMsgs]   = useState(false);
  const [archivedPage, setArchivedPage] = useState(0);
  const [hasMoreArchived, setHasMore]   = useState(true);

  const loadSessions = useCallback(async () => {
    if (!userId) return;
    setLoadingList(true);
    const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
    const { data } = await supabase
      .from("chat_sessions")
      .select("id, started_at, ended_at, title")
      .eq("user_id", userId)
      .eq("is_archived", false)
      .gte("started_at", thirtyDaysAgo)
      .order("started_at", { ascending: false })
      .limit(RECENT_LIMIT);
    setSessions(data ?? []);
    setLoadingList(false);
  }, [userId]);

  const loadArchived = useCallback(async () => {
    if (!userId) return;
    const from = archivedPage * ARCHIVED_LIMIT;
    const { data } = await supabase
      .from("chat_sessions")
      .select("id, started_at, ended_at, title")
      .eq("user_id", userId)
      .eq("is_archived", true)
      .order("started_at", { ascending: false })
      .range(from, from + ARCHIVED_LIMIT - 1);
    const rows = data ?? [];
    setArchived(prev => [...prev, ...rows]);
    setHasMore(rows.length === ARCHIVED_LIMIT);
    setArchivedPage(p => p + 1);
  }, [userId, archivedPage]);

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
    loadingList, loadingMsgs, hasMoreArchived,
    loadSessions, loadArchived, loadMessages, closeMessages,
  };
}
