import { useEffect } from "react";

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const diffDays = Math.floor((now - d) / 86400000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7)  return d.toLocaleDateString("en-GB", { weekday: "long" });
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: diffDays > 365 ? "numeric" : undefined });
}

function formatTime(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

function SessionItem({ session, active, onClick }) {
  const title = session.title || "Chat session";
  const isActive = active?.id === session.id;
  return (
    <button className={`ch-session${isActive ? " ch-session--active" : ""}`} onClick={() => onClick(session)}>
      <span className="ch-session-title">{title}</span>
      <span className="ch-session-date">{formatDate(session.started_at)} · {formatTime(session.started_at)}</span>
    </button>
  );
}

export default function ChatHistory({
  sessions, archived, messages, activeSession,
  loadingList, loadingMsgs, hasMoreArchived,
  loadSessions, loadArchived, loadMessages, closeMessages,
  onClose,
}) {
  useEffect(() => { loadSessions(); }, [loadSessions]);

  return (
    <div className="ch-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="ch-panel">

        {/* ── Header ── */}
        <div className="ch-header">
          <h2 className="ch-title">Chat history</h2>
          <button className="ch-close" onClick={onClose}>✕</button>
        </div>

        {/* ── Message viewer (when a session is selected) ── */}
        {messages !== null ? (
          <div className="ch-messages-wrap">
            <button className="ch-back" onClick={closeMessages}>← Back to sessions</button>
            <p className="ch-session-meta">
              {activeSession?.title || "Chat"} · {formatDate(activeSession?.started_at)} {formatTime(activeSession?.started_at)}
            </p>
            <div className="ch-messages">
              {loadingMsgs && <p className="ch-empty">Loading…</p>}
              {!loadingMsgs && messages.length === 0 && (
                <p className="ch-empty">No messages saved for this session.</p>
              )}
              {messages.map((m, i) => (
                <div key={i} className={`ch-msg ch-msg--${m.role}`}>
                  <span className="ch-msg-role">{m.role === "mira" ? "Mira" : "You"}</span>
                  <p className="ch-msg-content">{m.content}</p>
                  <span className="ch-msg-time">{formatTime(m.created_at)}</span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="ch-list-wrap">
            {/* ── Recent sessions ── */}
            <p className="ch-section-label">Last 30 days</p>
            {loadingList && <p className="ch-empty">Loading…</p>}
            {!loadingList && sessions.length === 0 && (
              <p className="ch-empty">No chats yet. Start a conversation with Mira!</p>
            )}
            {sessions.map(s => (
              <SessionItem key={s.id} session={s} active={activeSession} onClick={loadMessages} />
            ))}

            {/* ── Archived sessions ── */}
            <div className="ch-archive-section">
              <p className="ch-section-label ch-section-label--archive">Older chats</p>
              {archived.length === 0 ? (
                <button className="ch-load-archive" onClick={loadArchived}>
                  Load older chats…
                </button>
              ) : (
                <>
                  {archived.map(s => (
                    <SessionItem key={s.id} session={s} active={activeSession} onClick={loadMessages} />
                  ))}
                  {hasMoreArchived && (
                    <button className="ch-load-archive" onClick={loadArchived}>Load more…</button>
                  )}
                </>
              )}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
