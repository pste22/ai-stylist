/**
 * Floating debug overlay — shows SessionWatcher events and session stats.
 * Rendered by App.jsx in dev mode or when ?debug is in the URL.
 */
import { useEffect, useReducer, useState } from "react";
import { setUICallback, getReport } from "./SessionWatcher.js";

const COLORS = { error: "#f87171", warn: "#fb923c", ok: "#4ade80" };

function entryColor(e) { return e.kind === "ok" ? COLORS.ok : COLORS[e.level] || COLORS.warn; }
function entryIcon(e)  { return e.kind === "ok" ? "✓" : e.level === "error" ? "✗" : "⚠"; }

function healthColor(score) {
  if (score >= 80) return COLORS.ok;
  if (score >= 50) return COLORS.warn;
  return COLORS.error;
}

function StatPill({ label, value, color }) {
  return (
    <div style={{
      background: "#1e293b", borderRadius: "6px", padding: "4px 8px",
      display: "flex", flexDirection: "column", alignItems: "center", gap: "1px", minWidth: "52px",
    }}>
      <span style={{ color: color || "#94a3b8", fontWeight: 700, fontSize: "13px", lineHeight: 1 }}>
        {value ?? "—"}
      </span>
      <span style={{ color: "#475569", fontSize: "9px", textTransform: "uppercase", letterSpacing: ".4px" }}>
        {label}
      </span>
    </div>
  );
}

export function SessionWatcherPanel() {
  const [entries, dispatch] = useReducer(
    (prev, e) => e.kind === "__clear__" ? [] : [e, ...prev].slice(0, 80),
    []
  );
  const [minimised, setMinimised] = useState(false);
  const [filter,    setFilter]    = useState("all"); // all | bugs | ok
  const [tab,       setTab]       = useState("log"); // log | stats

  // Re-render stats every 2 s so latency/turn counts stay fresh
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 2000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    setUICallback((entry) => dispatch(entry));
    return () => setUICallback(null);
  }, []);

  const report   = getReport();
  const bugCount = entries.filter(e => e.kind === "bug").length;
  const visible  = filter === "all" ? entries
    : filter === "bugs" ? entries.filter(e => e.kind === "bug")
    : entries.filter(e => e.kind === "ok");

  return (
    <div style={{
      position: "fixed", bottom: "80px", right: "12px",
      width: minimised ? "auto" : "320px",
      maxHeight: minimised ? "auto" : "420px",
      background: "rgba(10,12,18,0.97)",
      border: `1px solid ${bugCount > 0 ? COLORS.warn : "#1e293b"}`,
      borderRadius: "12px",
      fontFamily: "'SF Mono', 'Fira Code', monospace",
      fontSize: "11px",
      zIndex: 99999,
      boxShadow: "0 12px 40px rgba(0,0,0,.7)",
      display: "flex", flexDirection: "column",
      overflow: "hidden",
    }}>

      {/* ── Header ── */}
      <div style={{
        display: "flex", alignItems: "center", gap: "6px",
        padding: "7px 10px", cursor: "pointer",
        background: "rgba(255,255,255,.04)", borderBottom: "1px solid #1e293b", flexShrink: 0,
      }} onClick={() => setMinimised(v => !v)}>
        <span style={{ fontSize: "13px" }}>🔍</span>
        {!minimised && (
          <span style={{ color: "#e2e8f0", flex: 1, fontWeight: 700, fontSize: "11px", letterSpacing: ".3px" }}>
            SESSION WATCHER
          </span>
        )}
        {bugCount > 0 && (
          <span style={{
            background: COLORS.error, color: "#fff", borderRadius: "4px",
            padding: "1px 6px", fontWeight: 700, fontSize: "10px",
          }}>{bugCount}</span>
        )}
        <span style={{ color: "#475569" }}>{minimised ? "▲" : "▼"}</span>
      </div>

      {!minimised && (
        <>
          {/* ── Tab bar ── */}
          <div style={{
            display: "flex", borderBottom: "1px solid #1e293b", flexShrink: 0,
          }}>
            {["log", "stats"].map(t => (
              <button key={t} onClick={(e) => { e.stopPropagation(); setTab(t); }} style={{
                flex: 1, padding: "5px 0",
                background: tab === t ? "#1e293b" : "transparent",
                border: "none", borderBottom: tab === t ? `2px solid ${COLORS.ok}` : "2px solid transparent",
                color: tab === t ? "#e2e8f0" : "#475569",
                cursor: "pointer", fontSize: "10px", textTransform: "uppercase", letterSpacing: ".5px",
              }}>{t}</button>
            ))}
          </div>

          {tab === "stats" && (
            <div style={{ padding: "10px", overflowY: "auto", flex: 1 }}>
              {/* Health score */}
              <div style={{
                display: "flex", alignItems: "center", gap: "8px",
                background: "#1e293b", borderRadius: "8px", padding: "8px 12px", marginBottom: "10px",
              }}>
                <span style={{
                  fontSize: "22px", fontWeight: 700, color: healthColor(report.healthScore), lineHeight: 1,
                }}>{report.healthScore}</span>
                <div>
                  <div style={{ color: "#e2e8f0", fontSize: "11px", fontWeight: 700 }}>Session Health</div>
                  <div style={{ color: "#475569", fontSize: "9px" }}>
                    {report.healthScore >= 80 ? "All clear" : report.healthScore >= 50 ? "Some issues" : "Needs attention"}
                  </div>
                </div>
                <div style={{ marginLeft: "auto", color: "#334155", fontSize: "9px" }}>
                  {report.mode} · {Math.round((Date.now() - (report.reportedAt ? new Date(report.reportedAt) : Date.now())) / 1000)}s
                </div>
              </div>

              {/* Stat pills */}
              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "10px" }}>
                <StatPill label="turns"     value={report.turns} />
                <StatPill label="products"  value={report.productsShown} />
                <StatPill label="show more" value={report.showMoreClicks} />
                <StatPill label="looks"     value={report.looksReceived} />
                <StatPill label="vs search" value={report.vsSearches} />
                <StatPill label="bugs"      value={report.errorCount + report.warnCount}
                  color={(report.errorCount + report.warnCount) > 0 ? COLORS.warn : COLORS.ok} />
                <StatPill label="avg ms"    value={report.avgLatencyMs}
                  color={report.avgLatencyMs > 8000 ? COLORS.error : report.avgLatencyMs > 4000 ? COLORS.warn : COLORS.ok} />
                <StatPill label="p95 ms"    value={report.p95LatencyMs} />
              </div>

              {/* Turn log table */}
              {report.turnLog.length > 0 && (
                <>
                  <div style={{ color: "#475569", fontSize: "9px", textTransform: "uppercase", marginBottom: "4px" }}>
                    Turn Log
                  </div>
                  {report.turnLog.map((t) => (
                    <div key={t.turn} style={{
                      background: "#0f172a", borderRadius: "6px", padding: "5px 8px",
                      marginBottom: "4px", borderLeft: `3px solid ${t.responseMs && t.responseMs > 8000 ? COLORS.error : "#334155"}`,
                    }}>
                      <div style={{ color: "#94a3b8", marginBottom: "2px" }}>
                        #{t.turn} · {t.responseMs ? `${t.responseMs} ms` : "…"} · {t.productCount} products
                      </div>
                      <div style={{ color: "#475569", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        "{t.text}"
                      </div>
                    </div>
                  ))}
                </>
              )}

              {/* Latency breakdown */}
              {report.latencySamples.length > 0 && (
                <>
                  <div style={{ color: "#475569", fontSize: "9px", textTransform: "uppercase", margin: "8px 0 4px" }}>
                    Latency Samples
                  </div>
                  {report.latencySamples.map((s, i) => (
                    <div key={i} style={{
                      display: "flex", justifyContent: "space-between",
                      color: s.ms > 8000 ? COLORS.warn : "#64748b",
                      padding: "2px 0", borderBottom: "1px solid #0f172a",
                    }}>
                      <span>{s.type}</span>
                      <span>{s.ms} ms</span>
                    </div>
                  ))}
                </>
              )}
            </div>
          )}

          {tab === "log" && (
            <>
              {/* Filter bar */}
              <div style={{
                display: "flex", gap: "4px", padding: "5px 8px",
                borderBottom: "1px solid #1e293b", flexShrink: 0,
              }}>
                {["all", "bugs", "ok"].map(f => (
                  <button key={f} onClick={(e) => { e.stopPropagation(); setFilter(f); }} style={{
                    background: filter === f ? "#1e293b" : "transparent",
                    border: "1px solid #334155", borderRadius: "4px",
                    color: filter === f ? "#e2e8f0" : "#475569",
                    padding: "2px 8px", cursor: "pointer", fontSize: "10px", textTransform: "capitalize",
                  }}>{f}</button>
                ))}
                <button onClick={(e) => { e.stopPropagation(); dispatch({ kind: "__clear__" }); }} style={{
                  marginLeft: "auto", background: "transparent",
                  border: "1px solid #334155", borderRadius: "4px",
                  color: "#475569", padding: "2px 8px", cursor: "pointer", fontSize: "10px",
                }}>clear</button>
              </div>

              {/* Log entries */}
              <div style={{ overflowY: "auto", flex: 1, padding: "4px 0" }}>
                {visible.length === 0 && (
                  <div style={{ color: "#334155", padding: "14px 10px", textAlign: "center" }}>
                    {filter === "bugs" ? "No bugs yet ✓" : "Watching session…"}
                  </div>
                )}
                {visible.map((e, i) => (
                  <div key={i} style={{
                    padding: "4px 10px", borderBottom: "1px solid #0a0c12",
                    display: "grid", gridTemplateColumns: "14px 1fr", gap: "4px", alignItems: "start",
                  }}>
                    <span style={{ color: entryColor(e), fontWeight: 700, paddingTop: "1px" }}>
                      {entryIcon(e)}
                    </span>
                    <div>
                      <span style={{ color: entryColor(e) }}>{e.msg}</span>
                      {e.detail && (
                        <div style={{ color: "#475569", marginTop: "2px", wordBreak: "break-all" }}>
                          {e.detail}
                        </div>
                      )}
                      <div style={{ color: "#1e293b", marginTop: "1px" }}>{e.ts}</div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
