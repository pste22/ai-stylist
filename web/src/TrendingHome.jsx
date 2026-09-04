import { useEffect, useMemo, useRef, useState } from "react";
import { hdProductImageUrl } from "./imageUrl.js";
import { shopLabel, trackedAffiliateUrl } from "./retailer.js";

const RAIL_TABS = [
  { id: "clothes", label: "Clothes" },
  { id: "shoes", label: "Shoes" },
  { id: "bags", label: "Bags" },
];

function bucketFromFlat(items) {
  const rails = { clothes: [], shoes: [], bags: [] };
  for (const p of items || []) {
    const cat = String(p.category || "").toLowerCase();
    if (cat === "shoes") rails.shoes.push(p);
    else if (cat === "bags") rails.bags.push(p);
    else rails.clothes.push(p);
  }
  return rails;
}

function TrendCard({ p, loved, onLove, onBuy, onSelect }) {
  return (
    <div className="trend-card" onClick={() => onSelect?.(p)}>
      <div className="trend-card-img-wrap">
        {p.image_url ? (
          <img
            className="trend-card-img"
            src={hdProductImageUrl(p.image_url, { longest: 800 })}
            alt={p.name}
            loading="lazy"
          />
        ) : (
          <div className="trend-card-img trend-card-img--placeholder">{p.category}</div>
        )}
        {p.badge === "trending" && <span className="trend-card-badge">Hot</span>}
        {onLove && (
          <button
            type="button"
            className={`trend-card-heart${loved?.has(p.id) ? " is-loved" : ""}`}
            onClick={(e) => { e.stopPropagation(); onLove(p); }}
            aria-label="Save"
          >
            {loved?.has(p.id) ? "♥" : "♡"}
          </button>
        )}
      </div>
      <p className="trend-card-name">{p.brand ? `${p.brand} · ${p.name}` : p.name}</p>
      <div className="trend-card-footer">
        <span className="trend-card-price">
          ₹{Number(p.price).toLocaleString("en-IN")}
        </span>
        {p.affiliate_url && (
          <a
            className="trend-card-shop"
            href={trackedAffiliateUrl(p)}
            target="_blank"
            rel="noopener noreferrer nofollow sponsored"
            onClick={(e) => { e.stopPropagation(); onBuy?.(p); }}
          >
            {shopLabel(p, { short: true })}
          </a>
        )}
      </div>
    </div>
  );
}

function Rail({ id, label, products, loved, onLove, onBuy, onSelect, active }) {
  if (!products?.length) return null;
  return (
    <section
      className={`trend-rail${active ? " is-active" : ""}`}
      id={`trend-${id}`}
      aria-label={label}
      hidden={!active}
    >
      <div className="trend-rail-head">
        <h3 className="trend-rail-title">{label}</h3>
        <span className="trend-rail-count">{products.length}</span>
      </div>
      <div className="trend-rail-scroll">
        {products.map((p) => (
          <TrendCard
            key={p.id}
            p={p}
            loved={loved}
            onLove={onLove}
            onBuy={onBuy}
            onSelect={onSelect}
          />
        ))}
      </div>
    </section>
  );
}

export default function TrendingHome({
  rails,
  items,
  headline = "Trending now",
  subhead = "Clothes, shoes, and bags moving on social this week",
  loved,
  onLove,
  onBuy,
  onSelect,
  onVisualSearch,
  onOutfitUrl,
  vsLoading,
}) {
  const fileRef = useRef(null);
  const [tab, setTab] = useState("clothes");
  const [urlDraft, setUrlDraft] = useState("");

  const resolved = useMemo(() => {
    if (rails && (rails.clothes?.length || rails.shoes?.length || rails.bags?.length)) {
      return {
        clothes: rails.clothes || [],
        shoes: rails.shoes || [],
        bags: rails.bags || [],
      };
    }
    return bucketFromFlat(items);
  }, [rails, items]);

  useEffect(() => {
    if (resolved[tab]?.length) return;
    const next = RAIL_TABS.find((t) => resolved[t.id]?.length);
    if (next) setTab(next.id);
  }, [resolved, tab]);

  const hasAny = RAIL_TABS.some((t) => resolved[t.id]?.length);
  if (!hasAny) return null;

  const submitUrl = (e) => {
    e.preventDefault();
    const url = urlDraft.trim();
    if (!url) return;
    onOutfitUrl?.(url);
    setUrlDraft("");
  };

  const onFile = (e) => {
    const file = e.target.files?.[0];
    if (!file || !onVisualSearch) return;
    const reader = new FileReader();
    reader.onload = () => onVisualSearch(reader.result.split(",")[1], file.type);
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  return (
    <div className="trend-home">
      <div className="trend-home-header">
        <p className="trend-home-eyebrow">From social this week</p>
        <h2 className="trend-home-title">{headline}</h2>
        <p className="trend-home-sub">{subhead}</p>
      </div>

      {(onVisualSearch || onOutfitUrl) && (
        <div className="trend-drop">
          <p className="trend-drop-copy">Saw it on Instagram or Reels? Drop a screenshot or paste the post.</p>
          <div className="trend-drop-row">
            {onVisualSearch && (
              <>
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/*"
                  hidden
                  onChange={onFile}
                />
                <button
                  type="button"
                  className="trend-drop-btn"
                  disabled={vsLoading}
                  onClick={() => fileRef.current?.click()}
                >
                  {vsLoading ? "Matching…" : "Screenshot"}
                </button>
              </>
            )}
            {onOutfitUrl && (
              <form className="trend-drop-form" onSubmit={submitUrl}>
                <input
                  type="url"
                  value={urlDraft}
                  onChange={(e) => setUrlDraft(e.target.value)}
                  placeholder="Paste Instagram / Pinterest link"
                  aria-label="Paste a social post URL"
                />
                <button type="submit" disabled={!urlDraft.trim()}>Shop it</button>
              </form>
            )}
          </div>
        </div>
      )}

      <div className="trend-tabs" role="tablist" aria-label="Trending categories">
        {RAIL_TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={tab === t.id ? "is-active" : ""}
            disabled={!resolved[t.id]?.length}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {RAIL_TABS.map((t) => (
        <Rail
          key={t.id}
          id={t.id}
          label={t.label}
          products={resolved[t.id]}
          loved={loved}
          onLove={onLove}
          onBuy={onBuy}
          onSelect={onSelect}
          active={tab === t.id}
        />
      ))}
    </div>
  );
}
