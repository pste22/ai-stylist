import { useState } from "react";
import TryOnModal from "./TryOnModal";

const CATEGORY_EMOJI = {
  dresses:     "👗",
  tops:        "👚",
  bottoms:     "👖",
  outerwear:   "🧥",
  shoes:       "👟",
  bags:        "👜",
  accessories: "✨",
  activewear:  "🏃",
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

function swatchHex(color) {
  return SWATCH_COLORS[color?.toLowerCase()] || "#cbb9a8";
}

function pseudoRandom(id, seed) {
  let h = seed | 0;
  for (const c of String(id || "")) h = (Math.imul(31, h) + c.charCodeAt(0)) | 0;
  return Math.abs(h);
}

function isRealProductPhoto(url) {
  return url && (
    url.includes("m.media-amazon.com") ||
    url.includes("images.pexels.com")
  );
}

/* Format price with proper INR grouping: ₹1,23,499 or $1,234 */
function formatPrice(price, currency) {
  const isINR = (currency || "INR") === "INR";
  const num   = Number(price) || 0;
  if (isINR) return "₹" + num.toLocaleString("en-IN");
  return "$" + num.toLocaleString("en-US");
}

function CategoryThumbnail({ category, color }) {
  const base  = swatchHex(color);
  const emoji = CATEGORY_EMOJI[category] || "🛍️";
  return (
    <div className="card-cat-thumb" style={{ "--swatch": base }}>
      <span className="card-cat-emoji">{emoji}</span>
    </div>
  );
}

/* ── Category label for chip below the image ── */
function categoryLabel(cat) {
  return cat ? cat.charAt(0).toUpperCase() + cat.slice(1) : "Fashion";
}

export default function ProductCard({ product, loved, highlighted, onLove, onBuy, compact }) {
  const [tryOnOpen, setTryOnOpen] = useState(false);

  const usePhoto   = isRealProductPhoto(product.image_url);
  const isTrending = pseudoRandom(product.id, 7777) % 6 === 0;
  const isNew      = pseudoRandom(product.id, 9999) % 9 === 0 && !isTrending;
  const priceStr   = formatPrice(product.price, product.currency);

  const thumbnail = usePhoto ? (
    <img
      className="card-img"
      src={product.image_url}
      alt={product.name}
      loading="lazy"
      onError={(e) => { e.currentTarget.style.display = "none"; }}
    />
  ) : (
    <CategoryThumbnail category={product.category} color={product.color} />
  );

  /* ── Compact card: horizontal layout for in-chat display ── */
  if (compact) {
    return (
      <div className={`card compact${loved ? " loved" : ""}`}>
        <div className="card-thumb">
          {thumbnail}
        </div>
        <div className="card-body">
          <p className="card-name">{product.name}</p>
          <p className="card-meta">
            <span className="card-color-swatch" style={{ background: swatchHex(product.color) }} />
            {product.color}
          </p>
          <p className="card-price">{priceStr}</p>
          <div className="card-actions">
            <button
              className={`love${loved ? " is-loved" : ""}`}
              onClick={() => onLove(product)}
              title={loved ? "Click to unlike" : "Save for later"}
            >{loved ? "♥ Saved" : "♡ Save"}</button>
            <a
              className="buy"
              href={product.affiliate_url}
              target="_blank"
              rel="noopener noreferrer nofollow sponsored"
              onClick={() => onBuy?.(product)}
            >Shop →</a>
          </div>
        </div>
      </div>
    );
  }

  /* ── Portrait card: full editorial grid card ── */
  return (
    <>
      <div className={`card${loved ? " loved" : ""}${highlighted ? " highlighted" : ""}`}>

        {/* ── Image area ── */}
        <div className="card-thumb">
          {thumbnail}

          {/* Gradient overlay — fades in on hover */}
          <div className="card-img-overlay" aria-hidden="true" />

          {/* Trend / New badge — top-left */}
          {isTrending && <span className="card-badge card-badge--hot">🔥 Trending</span>}
          {isNew      && <span className="card-badge card-badge--new">✦ New</span>}

          {/* Heart — top-right */}
          <button
            className={`card-heart${loved ? " is-loved" : ""}`}
            onClick={() => onLove(product)}
            aria-label={loved ? "Remove from saved" : "Save item"}
          >
            {loved ? "♥" : "♡"}
          </button>
        </div>

        {/* ── Info panel ── */}
        <div className="card-body">

          {/* Category chip */}
          <span className="card-cat-chip">
            {CATEGORY_EMOJI[product.category] || "🛍️"}
            {" "}{categoryLabel(product.category)}
          </span>

          {/* Product name */}
          <p className="card-name">{product.name}</p>

          {/* Colour swatch pill + price — same row */}
          <div className="card-meta-row">
            <span className="card-swatch-pill">
              <span
                className="card-color-dot"
                style={{ background: swatchHex(product.color) }}
              />
              <span className="card-color-label">{product.color}</span>
            </span>
            <strong className="card-price">{priceStr}</strong>
          </div>

          {/* CTAs */}
          <div className="card-ctas">
            <button
              className="card-try-btn"
              type="button"
              onClick={() => setTryOnOpen(true)}
            >
              Try On ✨
            </button>
            <a
              className="card-buy-btn"
              href={product.affiliate_url}
              target="_blank"
              rel="noopener noreferrer nofollow sponsored"
              onClick={() => onBuy?.(product)}
            >
              Shop →
            </a>
          </div>
        </div>
      </div>

      {tryOnOpen && (
        <TryOnModal
          product={product}
          onClose={() => setTryOnOpen(false)}
        />
      )}
    </>
  );
}
