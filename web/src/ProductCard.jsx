import { useState } from "react";
import { shopLabel, trackedAffiliateUrl } from "./retailer.js";
import { hdProductImageUrl, isProductPhotoUrl, productImageSrcSet } from "./imageUrl.js";

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

function isInUserSize(productName, userSize) {
  if (!userSize || !productName) return false;
  const name = productName.toLowerCase();
  const size = userSize.trim().toLowerCase();
  // Match whole word/token: "S" shouldn't match "XS" or "2XS"
  const re = new RegExp(`(?<![a-z0-9])${size}(?![a-z0-9])`, "i");
  return re.test(name);
}

/* Still-life catalog shots (bags, shoes, jewellery) get cropped to straps/toes
   when we cover-fill a portrait frame. Apparel keeps cover so faces stay in. */
const CONTAIN_CATEGORIES = new Set(["bags", "shoes", "accessories"]);
export function shouldContainProductPhoto(category) {
  return CONTAIN_CATEGORIES.has(String(category || "").toLowerCase());
}

function titleCase(value) {
  const s = String(value || "").replace(/_/g, " ").trim();
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
}

/* Titles usually repeat the brand ("Allen Solly Women Blouse") — drop it so the
   brand line and product line aren't saying the same thing twice. */
function splitBrandTitle(product) {
  const brand = product.brand || product.facets?.brand || null;
  const name = product.name || "";
  if (!brand) return { brand: null, title: name };
  const stripped = name.toLowerCase().startsWith(brand.toLowerCase())
    ? name.slice(brand.length).replace(/^[\s\-–—·,]+/, "")
    : name;
  return { brand, title: stripped || name };
}

/* Tags are derived only from facets the catalogue actually has, so cards never
   claim a style the data can't back up. */
function styleTags(product) {
  const f = product.facets || {};
  const tags = [];
  if (f.new_in) tags.push("New in");
  (Array.isArray(f.occasion) ? f.occasion : []).forEach((o) => tags.push(titleCase(o)));
  [f.fit, f.pattern, f.material].forEach((v) => { if (v) tags.push(titleCase(v)); });
  return [...new Set(tags.filter(Boolean))].slice(0, 3);
}

export default function ProductCard({ product, loved, highlighted, inCart, onLove, onBuy, onAddToCart, onSelect, compact, userSize, onTryOn, variant, onViewSimilar }) {
  const [imgLoaded, setImgLoaded] = useState(false);
  const [imgError, setImgError]   = useState(false);
  const [useHd, setUseHd]         = useState(true);

  const usePhoto     = isProductPhotoUrl(product.image_url) && !imgError;
  const isUserSize   = isInUserSize(product.name, userSize);
  const priceStr   = formatPrice(product.price, product.currency);
  const imgSrc     = usePhoto
    ? (useHd ? hdProductImageUrl(product.image_url, { longest: 1500 }) : product.image_url)
    : null;
  const imgSrcSet  = usePhoto && useHd ? productImageSrcSet(product.image_url) : undefined;

  const containPhoto = usePhoto && (compact || shouldContainProductPhoto(product.category));
  const thumbnail = usePhoto ? (
    <>
      {!imgLoaded && <div className="card-img-skeleton" aria-hidden="true" />}
      <img
        className={`card-img${imgLoaded ? "" : " card-img--loading"}${containPhoto ? " card-img--contain" : ""}`}
        src={imgSrc}
        srcSet={imgSrcSet}
        sizes={compact
          ? "96px"
          : "(max-width: 640px) 92vw, (max-width: 820px) 45vw, 320px"}
        alt={product.name}
        loading="lazy"
        decoding="async"
        onLoad={() => setImgLoaded(true)}
        onError={() => {
          // HD rewrite failed → try original catalog URL once before giving up
          if (useHd) {
            setUseHd(false);
            setImgLoaded(false);
            return;
          }
          setImgError(true);
          setImgLoaded(true);
        }}
      />
    </>
  ) : (
    <CategoryThumbnail category={product.category} color={product.color} />
  );

  /* ── Compact card: horizontal layout for in-chat display ── */
  if (compact) {
    return (
      <div
        className={`card compact${loved ? " loved" : ""}`}
        onClick={() => onSelect?.(product)}
      >
        <div className="card-thumb">
          {thumbnail}
        </div>
        <div className="card-body">
          <p className="card-name">{product.name}</p>
          {product.mix_role === "curiosity" && (
            <span className="card-elevated-label">elevated</span>
          )}
          <p className="card-meta">
            <span className="card-color-swatch" style={{ background: swatchHex(product.color) }} />
            {product.color}
          </p>
          <p className="card-price">{priceStr}</p>
          <div className="card-actions">
            <button
              className={`love${loved ? " is-loved" : ""}`}
              onClick={(e) => { e.stopPropagation(); onLove(product); }}
              title={loved ? "Click to unlike" : "Save for later"}
            >{loved ? "♥ Saved" : "♡ Save"}</button>
            <a
              className="buy"
              href={trackedAffiliateUrl(product)}
              target="_blank"
              rel="noopener noreferrer nofollow sponsored"
              onClick={(e) => { e.stopPropagation(); onBuy?.(product); }}
            >{shopLabel(product, { short: true })}</a>
          </div>
        </div>
      </div>
    );
  }

  /* ── Catalog card: premium results-grid presentation ── */
  if (variant === "catalog") {
    const { brand, title } = splitBrandTitle(product);
    const tags = styleTags(product);
    return (
      <article
        className={`pc${loved ? " is-loved" : ""}${highlighted ? " is-highlighted" : ""}`}
        onClick={() => onSelect?.(product)}
      >
        <div className="pc-media">
          {thumbnail}
          {isUserSize && <span className="pc-flag">Your size</span>}
          <button
            className={`pc-save${loved ? " is-loved" : ""}`}
            type="button"
            onClick={(e) => { e.stopPropagation(); onLove(product); }}
            aria-label={loved ? "Remove from saved" : "Save item"}
          >
            {loved ? "♥" : "♡"}
          </button>
          <div className="pc-quick">
            <button
              className="pc-quick-btn pc-quick-btn--primary"
              type="button"
              disabled={!onTryOn}
              onClick={(e) => { e.stopPropagation(); onTryOn?.(product); }}
            >
              Try on
            </button>
            <button
              className="pc-quick-btn"
              type="button"
              onClick={(e) => { e.stopPropagation(); onAddToCart?.(product); }}
            >
              {inCart ? "In bag" : "Add to bag"}
            </button>
            {onViewSimilar && (
              <button
                className="pc-quick-btn"
                type="button"
                onClick={(e) => { e.stopPropagation(); onViewSimilar(product); }}
              >
                View similar
              </button>
            )}
          </div>
        </div>

        <div className="pc-info">
          {brand && <p className="pc-brand">{brand}</p>}
          <h3 className="pc-title">{title}</h3>
          {tags.length > 0 && (
            <ul className="pc-tags">
              {tags.map((t) => <li key={t}>{t}</li>)}
            </ul>
          )}
          <div className="pc-foot">
            <strong className="pc-price">{priceStr}</strong>
            <a
              className="pc-shop"
              href={trackedAffiliateUrl(product)}
              target="_blank"
              rel="noopener noreferrer nofollow sponsored"
              onClick={(e) => { e.stopPropagation(); onBuy?.(product); }}
            >
              {shopLabel(product, { short: true })}
            </a>
          </div>
        </div>
      </article>
    );
  }

  /* ── Portrait card: full editorial grid card ── */
  return (
      <div
        className={`card${loved ? " loved" : ""}${highlighted ? " highlighted" : ""}`}
        onClick={() => onSelect?.(product)}
      >

        {/* ── Image area ── */}
        <div className="card-thumb">
          {thumbnail}

          {/* Gradient overlay — fades in on hover */}
          <div className="card-img-overlay" aria-hidden="true" />

          {/* Heart — top-right */}
          <button
            className={`card-heart${loved ? " is-loved" : ""}`}
            onClick={(e) => { e.stopPropagation(); onLove(product); }}
            aria-label={loved ? "Remove from saved" : "Save item"}
          >
            {loved ? "♥" : "♡"}
          </button>
        </div>

        {/* ── Info panel ── */}
        <div className="card-body">

          {/* Category chip + size badge + curiosity label */}
          <div className="card-chip-row">
            <span className="card-cat-chip">
              {CATEGORY_EMOJI[product.category] || "🛍️"}
              {" "}{categoryLabel(product.category)}
            </span>
            {product.mix_role === "curiosity" && (
              <span className="card-elevated-label">elevated</span>
            )}
            {isUserSize && (
              <span className="card-size-badge">✓ Your size</span>
            )}
          </div>

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
              onClick={(e) => { e.stopPropagation(); onTryOn?.(product); }}
              aria-label="Virtual try on"
              title="Virtual Try On"
              disabled={!onTryOn}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                {/* Person silhouette */}
                <circle cx="12" cy="5" r="2.5"/>
                <path d="M8 10 Q8 8 12 8 Q16 8 16 10 L17.5 17 H14 L13 14 H11 L10 17 H6.5 Z"/>
              </svg>
            </button>
            <button
              className={`card-cart-btn${inCart ? " in-cart" : ""}`}
              type="button"
              onClick={(e) => { e.stopPropagation(); onAddToCart?.(product); }}
              aria-label={inCart ? "Remove from bag" : "Add to bag"}
              title={inCart ? "Remove from bag" : "Add to bag"}
            >
              {inCart ? "🛒✓" : "🛒"}
            </button>
            <a
              className="card-buy-btn"
              href={trackedAffiliateUrl(product)}
              target="_blank"
              rel="noopener noreferrer nofollow sponsored"
              onClick={(e) => { e.stopPropagation(); onBuy?.(product); }}
              title={shopLabel(product)}
            >
              {shopLabel(product, { short: true })}
            </a>
          </div>
        </div>
      </div>
  );
}
