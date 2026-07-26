/**
 * Floating debug overlay — shows SessionWatcher events in real time.
 * Rendered by App.jsx only when VITE_DEBUG=true or ?debug in URL.
 */
import { useEffect, useReducer, useState } from "react";
import { setUICallback } from "./SessionWatcher.js";

const ICONS = { bug: { error: "✗", warn: "⚠" }, ok: "✓" };
const COLORS = { error: "#f87171", warn: "#fb923c", ok: "#4ade80", info: "#94a3b8" };

function entryColor(e) {
  if (e.kind === "ok") return COLORS.ok;
  return e.level === "error" ? COLORS.error : COLORS.warn;
}

function entryIcon(e) {
  if (e.kind === "ok") return ICONS.ok;
  return ICONS.bug[e.level] || "?";
}

export function SessionWatcherPanel() {
  const [entries, dispatch] = useReducer((prev, e) => e.kind === "__clear__" ? [] : [e, ...prev].slice(0, 60), []);
  const [minimised, setMinimised] = useState(false);
  const [filter, setFilter] = useState("all"); // all | bugs | ok

  useEffect(() => {
    setUICallback((entry) => dispatch(entry));
    return () => setUICallback(null);
  }, []);

  const visible = filter === "all"
    ? entries
    : filter === "bugs"
      ? entries.filter(e => e.kind === "bug")
      : entries.filter(e => e.kind === "ok");

  const bugCount = entries.filter(e => e.kind === "bug").length;

  return (
    <div style={{
      position: "fixed",
      bottom: "80px",
      right: "12px",
      width: minimised ? "auto" : "320px",
      maxHeight: minimised ? "auto" : "380px",
      background: "rgba(15,15,20,0.96)",
      border: `1px solid ${bugCount > 0 ? COLORS.warn : "#334155"}`,
      borderRadius: "10px",
      fontFamily: "monospace",
      fontSize: "11px",
      zIndex: 99999,
      boxShadow: "0 8px 32px rgba(0,0,0,.6)",
      display: "flex",
      flexDirection: "column",
      overflow: "hidden",
      transition: "width .2s, max-height .2s",
    }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", gap: "6px",
        padding: "6px 10px",
        background: "rgba(255,255,255,.05)",
        borderBottom: "1px solid #1e293b",
        cursor: "pointer",
        flexShrink: 0,
      }}
        onClick={() => setMinimised(v => !v)}
      >
        <span style={{ color: COLORS.warn, fontWeight: 700 }}>🔍</span>
        {!minimised && (
          <span style={{ color: "#e2e8f0", flex: 1, fontWeight: 700, fontSize: "12px" }}>
            Session Watcher
          </span>
        )}
        {bugCount > 0 && (
          <span style={{
            background: COLORS.error, color: "#fff", borderRadius: "4px",
            padding: "0 5px", fontWeight: 700, fontSize: "11px",
          }}>
            {bugCount} bug{bugCount !== 1 ? "s" : ""}
          </span>
        )}
        <span style={{ color: "#64748b", marginLeft: "auto" }}>{minimised ? "▲" : "▼"}</span>
      </div>

      {!minimised && (
        <>
          {/* Filter tabs */}
          <div style={{
            display: "flex", gap: "4px", padding: "6px 8px",
            borderBottom: "1px solid #1e293b", flexShrink: 0,
          }}>
            {["all", "bugs", "ok"].map(f => (
              <button key={f} onClick={(e) => { e.stopPropagation(); setFilter(f); }} style={{
                background: filter === f ? "#1e293b" : "transparent",
                border: "1px solid #334155", borderRadius: "4px",
                color: filter === f ? "#e2e8f0" : "#64748b",
                padding: "2px 8px", cursor: "pointer", fontSize: "11px", textTransform: "capitalize",
              }}>{f}</button>
            ))}
            <button onClick={(e) => { e.stopPropagation(); dispatch({ kind: "__clear__" }); }} style={{
              marginLeft: "auto", background: "transparent", border: "1px solid #334155",
              borderRadius: "4px", color: "#64748b", padding: "2px 8px", cursor: "pointer", fontSize: "11px",
            }}>clear</button>
          </div>

          {/* Log */}
          <div style={{ overflowY: "auto", flex: 1, padding: "6px 0" }}>
            {visible.length === 0 && (
              <div style={{ color: "#475569", padding: "12px 10px", textAlign: "center" }}>
                {filter === "bugs" ? "No bugs detected yet" : "Watching…"}
              </div>
            )}
            {visible.map((e, i) => (
              <div key={i} style={{
                padding: "4px 10px",
                borderBottom: "1px solid #0f172a",
                display: "grid",
                gridTemplateColumns: "14px 1fr",
                gap: "4px",
                alignItems: "start",
              }}>
                <span style={{ color: entryColor(e), fontWeight: 700, paddingTop: "1px" }}>
                  {entryIcon(e)}
                </span>
                <div>
                  <span style={{ color: entryColor(e) }}>{e.msg}</span>
                  {e.detail && (
                    <div style={{ color: "#64748b", marginTop: "2px", wordBreak: "break-all" }}>
                      {e.detail}
                    </div>
                  )}
                  <div style={{ color: "#334155", marginTop: "1px" }}>{e.ts}</div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
