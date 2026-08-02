import { useEffect, useRef, useState } from "react";
import { listTryOns, deleteTryOn, clearTryOns } from "./tryOnDB.js";

function timeAgo(ts) {
  if (!ts) return "";
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60); if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60); if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24); if (d < 7) return `${d}d ago`;
  const w = Math.floor(d / 7); if (w < 5) return `${w}w ago`;
  return new Date(ts).toLocaleDateString();
}

function price(p) {
  if (p.price == null) return "";
  const cur = p.currency === "USD" ? "$" : "₹";
  return `${cur}${Number(p.price).toLocaleString("en-IN")}`;
}

const CMP_ANGLES = [
  { key: "front", label: "Front" },
  { key: "side", label: "Side" },
  { key: "back", label: "Back" },
];

export default function FittingRoom({ onClose, onOpenTryOn, onCountChange }) {
  const overlayRef = useRef(null);
  const [items, setItems] = useState(null); // null = loading
  const [sort, setSort] = useState("recent"); // "recent" | "product"
  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState(() => new Set());
  const [comparing, setComparing] = useState(false);
  const [cmpAngle, setCmpAngle] = useState("front");

  const toggleSelect = (id) =>
    setSelected((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else if (n.size < 4) n.add(id);   // compare up to 4
      return n;
    });

  const exitSelect = () => { setSelectMode(false); setSelected(new Set()); setComparing(false); };

  const refresh = () =>
    listTryOns().then((rows) => { setItems(rows); onCountChange?.(rows.length); });

  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, []);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [onClose]);

  // Close compare if selection drops below 2.
  useEffect(() => { if (comparing && selected.size < 2) setComparing(false); }, [comparing, selected]);

  const sorted = (items || []).slice().sort((a, b) =>
    sort === "product"
      ? (a.product?.name || "").localeCompare(b.product?.name || "")
      : (b.ts || 0) - (a.ts || 0)
  );
  const selectedRecords = (items || []).filter((r) => selected.has(r.productId));

  const remove = async (e, id) => {
    e.stopPropagation();
    await deleteTryOn(id);
    refresh();
  };

  const clearAll = async () => {
    await clearTryOns();
    refresh();
  };

  return (
    <>
    <div className="fr-overlay" ref={overlayRef}
      onClick={(e) => { if (e.target === overlayRef.current) onClose(); }}
      role="dialog" aria-modal="true" aria-label="My Fitting Room">
      <div className="fr-panel">
        <div className="fr-header">
          <div>
            <h2 className="fr-title">🪞 My Fitting Room</h2>
            <p className="fr-sub">Looks you've seen on you · saved on this device only</p>
          </div>
          <button className="fr-close" onClick={onClose} aria-label="Close">✕</button>
        </div>

        {items && items.length > 0 && (
          <div className="fr-toolbar">
            {selectMode ? (
              <>
                <span className="fr-select-hint">{selected.size} selected · pick 2–4 to compare</span>
                <button className="fr-clear" onClick={exitSelect}>Cancel</button>
              </>
            ) : (
              <>
                <div className="fr-sort">
                  <button className={`fr-sort-btn${sort === "recent" ? " active" : ""}`} onClick={() => setSort("recent")}>Recent</button>
                  <button className={`fr-sort-btn${sort === "product" ? " active" : ""}`} onClick={() => setSort("product")}>By product</button>
                </div>
                <div className="fr-toolbar-actions">
                  {items.length > 1 && <button className="fr-sort-btn" onClick={() => setSelectMode(true)}>⇄ Compare</button>}
                  <button className="fr-clear" onClick={clearAll}>Clear all</button>
                </div>
              </>
            )}
          </div>
        )}

        <div className="fr-body">
          {items === null ? (
            <div className="fr-empty"><span>Loading your looks…</span></div>
          ) : items.length === 0 ? (
            <div className="fr-empty">
              <div className="fr-empty-glow">✨</div>
              <p className="fr-empty-head">Your fitting room is empty</p>
              <p className="fr-empty-sub">Try on anything and it'll live here — saved right on this device.</p>
              <button className="fr-empty-cta" onClick={onClose}>Browse styles →</button>
            </div>
          ) : (
            <div className="fr-grid">
              {sorted.map((rec) => {
                const cover = rec.views?.front || Object.values(rec.views || {})[0];
                const hasVideo = rec.clips && Object.keys(rec.clips).length > 0;
                const angles = Object.keys(rec.views || {}).length;
                const isSel = selected.has(rec.productId);
                return (
                  <button key={rec.productId} className={`fr-tile${isSel ? " fr-tile--selected" : ""}`}
                    onClick={() => selectMode ? toggleSelect(rec.productId) : onOpenTryOn?.(rec.product)}>
                    {cover
                      ? <img className="fr-tile-img" src={`data:${cover.mime};base64,${cover.image}`} alt={rec.product?.name} loading="lazy" />
                      : <div className="fr-tile-img fr-tile-img--ph">🛍️</div>}
                    {hasVideo && <span className="fr-badge fr-badge--video">▶</span>}
                    {selectMode && <span className={`fr-tile-check${isSel ? " on" : ""}`}>{isSel ? "✓" : ""}</span>}
                    {!selectMode && <span className="fr-tile-del" onClick={(e) => remove(e, rec.productId)} title="Remove" role="button">✕</span>}
                    <div className="fr-tile-info">
                      <p className="fr-tile-name">{rec.product?.name}</p>
                      <div className="fr-tile-meta">
                        <span className="fr-tile-price">{price(rec.product || {})}</span>
                        <span className="fr-tile-date">{timeAgo(rec.ts)}</span>
                      </div>
                      {angles > 1 && <span className="fr-tile-dots">{"•".repeat(angles)}</span>}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {selectMode && selected.size >= 2 && !comparing && (
          <div className="fr-compare-bar">
            <button className="fr-compare-go" onClick={() => setComparing(true)}>
              Compare {selected.size} looks →
            </button>
          </div>
        )}
      </div>
    </div>

    {comparing && (
      <div className="fr-cmp-overlay" onClick={(e) => { if (e.target.classList.contains("fr-cmp-overlay")) setComparing(false); }}
        role="dialog" aria-modal="true" aria-label="Compare looks">
        <div className="fr-cmp-panel">
          <div className="fr-cmp-head">
            <h3 className="fr-cmp-title">Compare</h3>
            <div className="fr-cmp-angles">
              {CMP_ANGLES.map((a) => (
                <button key={a.key} className={`fr-sort-btn${cmpAngle === a.key ? " active" : ""}`}
                  onClick={() => setCmpAngle(a.key)}>{a.label}</button>
              ))}
            </div>
            <button className="fr-close" onClick={() => setComparing(false)} aria-label="Close">✕</button>
          </div>
          <div className="fr-cmp-row">
            {selectedRecords.map((rec) => {
              const v = rec.views?.[cmpAngle] || rec.views?.front || Object.values(rec.views || {})[0];
              return (
                <div key={rec.productId} className="fr-cmp-col">
                  {v
                    ? <img className="fr-cmp-img" src={`data:${v.mime};base64,${v.image}`} alt={rec.product?.name} />
                    : <div className="fr-cmp-img fr-tile-img--ph">🛍️</div>}
                  <p className="fr-cmp-name">{rec.product?.name}</p>
                  <p className="fr-cmp-price">{price(rec.product || {})}</p>
                  <button className="fr-cmp-remove" onClick={() => toggleSelect(rec.productId)}>Remove</button>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    )}
    </>
  );
}
