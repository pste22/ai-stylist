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

export default function FittingRoom({ onClose, onOpenTryOn, onCountChange }) {
  const overlayRef = useRef(null);
  const [items, setItems] = useState(null); // null = loading
  const [sort, setSort] = useState("recent"); // "recent" | "product"

  const refresh = () =>
    listTryOns().then((rows) => { setItems(rows); onCountChange?.(rows.length); });

  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, []);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [onClose]);

  const sorted = (items || []).slice().sort((a, b) =>
    sort === "product"
      ? (a.product?.name || "").localeCompare(b.product?.name || "")
      : (b.ts || 0) - (a.ts || 0)
  );

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
            <div className="fr-sort">
              <button className={`fr-sort-btn${sort === "recent" ? " active" : ""}`} onClick={() => setSort("recent")}>Recent</button>
              <button className={`fr-sort-btn${sort === "product" ? " active" : ""}`} onClick={() => setSort("product")}>By product</button>
            </div>
            <button className="fr-clear" onClick={clearAll}>Clear all</button>
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
                return (
                  <button key={rec.productId} className="fr-tile"
                    onClick={() => { onOpenTryOn?.(rec.product); }}>
                    {cover
                      ? <img className="fr-tile-img" src={`data:${cover.mime};base64,${cover.image}`} alt={rec.product?.name} loading="lazy" />
                      : <div className="fr-tile-img fr-tile-img--ph">🛍️</div>}
                    {hasVideo && <span className="fr-badge fr-badge--video">▶</span>}
                    <span className="fr-tile-del" onClick={(e) => remove(e, rec.productId)} title="Remove" role="button">✕</span>
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
      </div>
    </div>
  );
}
