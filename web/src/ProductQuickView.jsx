import { useEffect, useRef, useState } from "react";

const CATEGORY_EMOJI = {
  dresses: "👗", tops: "👚", bottoms: "👖", outerwear: "🧥",
  shoes: "👟", bags: "👜", accessories: "✨", activewear: "🏃",
};

const SWATCH_COLORS = {
  sand: "#d8c5a0", white: "#f4f4f0", charcoal: "#3a3a3a", forest: "#2e4a36",
  black: "#222", indigo: "#34406b", cream: "#efe6d2", olive: "#6b6b3a",
  burgundy: "#6b2a35", sage: "#a8b8a0", camel: "#c2956a", "washed blue": "#7e9bbf",
  tan: "#c19a6b", "off-white": "#efece4", nude: "#e3c4ad", rust: "#9c5a32",
  emerald: "#1f6b53", brown: "#6b4a30", gray: "#999", grey: "#999",
  beige: "#d4c4a8", khaki: "#c2a96a", natural: "#e8dcc8", blue: "#7e9bbf",
  navy: "#1e2d5a", terracotta: "#c1643c", lavender: "#9b8ec4",
  "dusty pink": "#d4a0a0", "forest green": "#2e5437",
};
function swatchHex(c) { return SWATCH_COLORS[c?.toLowerCase()] || "#cbb9a8"; }

function formatPrice(price, currency) {
  const isINR = (currency || "INR") === "INR";
  const num = Number(price) || 0;
  return isINR ? "₹" + num.toLocaleString("en-IN") : "$" + num.toLocaleString("en-US");
}

/* Simulate 4 different "angles" using object-position crops */
const CROPS = [
  { label: "Full",   pos: "center center", zoom: "1" },
  { label: "Detail", pos: "center top",    zoom: "1.15" },
  { label: "Mid",    pos: "center 40%",    zoom: "1.2" },
  { label: "Hem",    pos: "center bottom", zoom: "1.15" },
];

function isRealPhoto(url) {
  return url && (url.includes("m.media-amazon.com") || url.includes("images.pexels.com"));
}

/* High-res Amazon URL swap: _SL500_ → _SL1200_ */
function hiResUrl(url) {
  if (!url) return url;
  return url.replace(/\._SL\d+_/, "._SL1200_");
}

export default function ProductQuickView({ product, loved, onLove, onBuy, onClose }) {
  const [cropIdx, setCropIdx] = useState(0);
  const [zoomed, setZoomed]   = useState(false);
  const panelRef = useRef(null);
  const hasPhoto = isRealPhoto(product.image_url);
  const imgSrc   = hasPhoto ? hiResUrl(product.image_url) : null;
  const emoji    = CATEGORY_EMOJI[product.category] || "🛍️";
  const crop     = CROPS[cropIdx];

  useEffect(() => {
    function onKey(e) { if (e.key === "Escape") onClose(); }
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  function handleBackdrop(e) {
    if (e.target === e.currentTarget) onClose();
  }

  return (
    <div className="qv-backdrop" onClick={handleBackdrop} role="dialog" aria-modal="true" aria-label={product.name}>
      <div className="qv-panel" ref={panelRef}>
        <button className="qv-close" onClick={onClose} aria-label="Close">✕</button>

        {/* ── Image area ── */}
        <div className="qv-img-wrap">
          {hasPhoto ? (
            <img
              className={`qv-img${zoomed ? " qv-img--zoomed" : ""}`}
              src={imgSrc}
              alt={product.name}
              style={{ objectPosition: crop.pos, transform: zoomed ? `scale(${crop.zoom}) translate(0,5%)` : "scale(1)" }}
              onClick={() => setZoomed(v => !v)}
              title={zoomed ? "Click to zoom out" : "Click to zoom in"}
            />
          ) : (
            <div className="qv-img-fallback">
              <span>{emoji}</span>
            </div>
          )}

          {/* Zoom hint */}
          {hasPhoto && !zoomed && (
            <span className="qv-zoom-hint" aria-hidden="true">🔍 Tap to zoom</span>
          )}

          {/* Love button overlaid */}
          <button
            className={`qv-heart${loved ? " is-loved" : ""}`}
            onClick={() => onLove(product)}
            aria-label={loved ? "Remove from saved" : "Save item"}
          >
            {loved ? "♥" : "♡"}
          </button>
        </div>

        {/* ── Crop thumbnails ── */}
        {hasPhoto && (
          <div className="qv-thumbs" role="tablist" aria-label="Image views">
            {CROPS.map((c, i) => (
              <button
                key={c.label}
                className={`qv-thumb${i === cropIdx ? " qv-thumb--active" : ""}`}
                onClick={() => { setCropIdx(i); setZoomed(false); }}
                role="tab"
                aria-selected={i === cropIdx}
                title={c.label}
              >
                <img
                  src={imgSrc}
                  alt={c.label}
                  style={{ objectPosition: c.pos }}
                />
              </button>
            ))}
          </div>
        )}

        {/* ── Product info ── */}
        <div className="qv-info">
          <span className="qv-cat-chip">{emoji} {product.category || "Fashion"}</span>
          <h2 className="qv-name">{product.name}</h2>

          <div className="qv-meta-row">
            <span className="qv-swatch-pill">
              <span className="qv-color-dot" style={{ background: swatchHex(product.color) }} />
              <span className="qv-color-label">{product.color || "—"}</span>
            </span>
            <strong className="qv-price">{formatPrice(product.price, product.currency)}</strong>
          </div>

          <div className="qv-actions">
            <button
              className={`qv-save-btn${loved ? " is-loved" : ""}`}
              onClick={() => onLove(product)}
            >
              {loved ? "♥ Saved" : "♡ Save"}
            </button>
            <a
              className="qv-shop-btn"
              href={product.affiliate_url}
              target="_blank"
              rel="noopener noreferrer nofollow sponsored"
              onClick={() => onBuy?.(product)}
            >
              Shop on Amazon →
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
