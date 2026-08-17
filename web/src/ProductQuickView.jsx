import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import SizeAdvice from "./SizeAdvice.jsx";
import ReviewComposer from "./ReviewComposer.jsx";
import AffiliateDisclosure from "./AffiliateDisclosure.jsx";
import { formatFitLabel, useProductReviews } from "./useProductReviews.js";
import { shopLabel, trackedAffiliateUrl } from "./retailer.js";
import { hdProductImageUrl, isProductPhotoUrl } from "./imageUrl.js";

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

function formatCount(n) {
  const num = Number(n) || 0;
  if (num >= 1000) return `${(num / 1000).toFixed(num >= 10000 ? 0 : 1).replace(/\.0$/, "")}k`;
  return String(num);
}

const ASK_CHIPS = [
  { key: "suit", label: "Does this suit me?" },
  { key: "wear", label: "When would I wear this?" },
  { key: "pair", label: "What goes with it?" },
];

function isRealPhoto(url) {
  return isProductPhotoUrl(url);
}

function hiResUrl(url) {
  return hdProductImageUrl(url, { longest: 1600 });
}

function Stars({ value, size = "md", interactive = false, onPick }) {
  const n = Math.max(0, Math.min(5, Number(value) || 0));
  const full = Math.floor(n);
  const half = n - full >= 0.4 && n - full < 0.9;
  return (
    <span className={`qv-stars qv-stars--${size}${interactive ? " qv-stars--interactive" : ""}`} aria-label={`${n} out of 5`}>
      {[1, 2, 3, 4, 5].map((i) => {
        let cls = "qv-star";
        if (i <= full) cls += " is-on";
        else if (i === full + 1 && half) cls += " is-half";
        return (
          <button
            key={i}
            type="button"
            className={cls}
            disabled={!interactive}
            onClick={() => interactive && onPick?.(i)}
            aria-label={interactive ? `Rate ${i} stars` : undefined}
            tabIndex={interactive ? 0 : -1}
          >
            ★
          </button>
        );
      })}
    </span>
  );
}

function productGallery(product) {
  const raw = Array.isArray(product.image_urls) ? product.image_urls : [];
  const urls = raw.filter(Boolean);
  if (urls.length) return urls;
  return product.image_url ? [product.image_url] : [];
}

export default function ProductQuickView({
  product, loved, inCart, onLove, onBuy, onAddToCart, onClose, prefs, onSetSize, onAskMira,
  related = [], onSelectRelated,
}) {
  const [imgIdx, setImgIdx] = useState(0);
  const [writingReview, setWritingReview] = useState(false);
  const panelRef = useRef(null);
  const galleryRef = useRef(null);
  const gallery = productGallery(product);
  const activeUrl = gallery[Math.min(imgIdx, Math.max(gallery.length - 1, 0))] || product.image_url;
  const hasPhoto = isRealPhoto(activeUrl);
  const emoji = CATEGORY_EMOJI[product.category] || "🛍️";

  const amazonRating = Number(product.rating) || 0;
  const amazonCount  = Number(product.ratings_total) || 0;
  const { reviews, aggregate, addReview } = useProductReviews(product.id);

  useEffect(() => {
    setImgIdx(0);
    setWritingReview(false);
    galleryRef.current?.scrollTo({ left: 0 });
  }, [product.id]);

  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") { onClose(); return; }
      if (e.key === "ArrowRight") goTo(imgIdx + 1);
      if (e.key === "ArrowLeft") goTo(imgIdx - 1);
    }
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose, imgIdx, gallery.length]); // eslint-disable-line react-hooks/exhaustive-deps

  function goTo(i) {
    const next = Math.max(0, Math.min(gallery.length - 1, i));
    setImgIdx(next);
    const el = galleryRef.current;
    if (el) el.scrollTo({ left: next * el.clientWidth, behavior: "smooth" });
  }

  function onGalleryScroll() {
    const el = galleryRef.current;
    if (!el || !el.clientWidth) return;
    const i = Math.round(el.scrollLeft / el.clientWidth);
    if (i !== imgIdx && i >= 0 && i < gallery.length) setImgIdx(i);
  }

  function handleBackdrop(e) {
    if (e.target === e.currentTarget) onClose();
  }

  const moreLike = (related || []).filter((p) => p && p.id !== product.id).slice(0, 8);

  const sheet = (
    <div className="qv-backdrop" onClick={handleBackdrop} role="dialog" aria-modal="true" aria-label={product.name}>
      <div className="qv-panel" ref={panelRef}>
        <header className="qv-topbar">
          <button className="qv-topbar-btn" type="button" onClick={onClose} aria-label="Back">←</button>
          <span className="qv-topbar-shop">{shopLabel(product, { short: true })}</span>
          <button
            className={`qv-topbar-btn qv-topbar-heart${loved ? " is-loved" : ""}`}
            type="button"
            onClick={() => onLove(product)}
            aria-label={loved ? "Remove from saved" : "Save item"}
          >
            {loved ? "♥" : "♡"}
          </button>
          <button className="qv-topbar-btn" type="button" onClick={onClose} aria-label="Close">✕</button>
        </header>

        <div className="qv-scroll">
          <div
            className="qv-gallery"
            ref={galleryRef}
            onScroll={onGalleryScroll}
            role="region"
            aria-label="Product photos"
          >
            {gallery.length && hasPhoto ? gallery.map((url, i) => (
              <div className="qv-slide" key={`${url}-${i}`}>
                {isRealPhoto(url) ? (
                  <img
                    className="qv-img"
                    src={hiResUrl(url)}
                    alt={`${product.name}${gallery.length > 1 ? ` — photo ${i + 1}` : ""}`}
                    draggable={false}
                  />
                ) : (
                  <div className="qv-img-fallback"><span>{emoji}</span></div>
                )}
              </div>
            )) : (
              <div className="qv-slide">
                <div className="qv-img-fallback"><span>{emoji}</span></div>
              </div>
            )}
          </div>

          {gallery.length > 1 && (
            <div className="qv-dots" role="tablist" aria-label="Photo">
              {gallery.map((_, i) => (
                <button
                  key={i}
                  type="button"
                  className={`qv-dot${i === imgIdx ? " qv-dot--active" : ""}`}
                  onClick={() => goTo(i)}
                  aria-label={`Photo ${i + 1}`}
                  aria-current={i === imgIdx ? "true" : undefined}
                />
              ))}
              <span className="qv-dots-count">{imgIdx + 1} / {gallery.length}</span>
            </div>
          )}

          <div className="qv-info">
            <span className="qv-cat-chip">{emoji} {product.category || "Fashion"}</span>
            <h2 className="qv-name">{product.name}</h2>

            <div className="qv-rating-row">
              {aggregate ? (
                <div className="qv-rating-block">
                  <Stars value={aggregate.avg} />
                  <span className="qv-rating-meta">
                    <strong>{aggregate.avg.toFixed(1)}</strong>
                    {" · "}
                    {aggregate.count} Mira {aggregate.count === 1 ? "review" : "reviews"}
                    {aggregate.topFit ? ` · ${formatFitLabel(aggregate.topFit)}` : ""}
                  </span>
                </div>
              ) : amazonRating > 0 ? (
                <div className="qv-rating-block">
                  <Stars value={amazonRating} />
                  <span className="qv-rating-meta">
                    <strong>{amazonRating.toFixed(1)}</strong>
                    {amazonCount > 0 ? ` · ${formatCount(amazonCount)}` : ""}
                    {" · "}
                    <span className="qv-rating-src">Amazon</span>
                  </span>
                </div>
              ) : (
                <p className="qv-rating-empty">No reviews yet — be the first</p>
              )}
            </div>

            <div className="qv-meta-row">
              <span className="qv-swatch-pill">
                <span className="qv-color-dot" style={{ background: swatchHex(product.color) }} />
                <span className="qv-color-label">{product.color || "—"}</span>
              </span>
              <strong className="qv-price qv-price--inline">{formatPrice(product.price, product.currency)}</strong>
            </div>

            {onAskMira && (
              <div className="qv-ask">
                <p className="qv-ask-label">Ask Mira</p>
                <div className="qv-ask-chips">
                  {ASK_CHIPS.map((c) => (
                    <button
                      key={c.key}
                      type="button"
                      className="qv-ask-chip"
                      onClick={() => onAskMira(product, c.key)}
                    >
                      {c.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <SizeAdvice product={product} prefs={prefs} onSetSize={onSetSize} />
            <AffiliateDisclosure compact />

            {moreLike.length > 0 && (
              <section className="qv-related" aria-label="More like this">
                <h3 className="qv-related-title">More like this</h3>
                <div className="qv-related-rail">
                  {moreLike.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      className="qv-related-card"
                      onClick={() => onSelectRelated?.(p)}
                    >
                      {isRealPhoto(p.image_url) ? (
                        <img src={hiResUrl(p.image_url)} alt="" loading="lazy" />
                      ) : (
                        <span className="qv-related-fallback">{CATEGORY_EMOJI[p.category] || "🛍️"}</span>
                      )}
                      <span className="qv-related-name">{p.name}</span>
                      <strong className="qv-related-price">{formatPrice(p.price, p.currency)}</strong>
                    </button>
                  ))}
                </div>
              </section>
            )}

            <section className="qv-reviews" aria-label="Reviews">
              <div className="qv-reviews-head">
                <h3 className="qv-reviews-title">Reviews</h3>
                {!writingReview && (
                  <button type="button" className="qv-reviews-write" onClick={() => setWritingReview(true)}>
                    Write a review
                  </button>
                )}
              </div>

              {writingReview ? (
                <ReviewComposer
                  product={product}
                  onCancel={() => setWritingReview(false)}
                  onSubmit={(data) => {
                    addReview(product.id, data);
                    setWritingReview(false);
                  }}
                />
              ) : (
                <>
                  {reviews.length === 0 ? (
                    <p className="qv-reviews-empty">
                      Share fit &amp; real photos — helps the next person decide.
                    </p>
                  ) : (
                    <ul className="qv-review-list">
                      {reviews.slice(0, 5).map((r) => (
                        <li key={r.id} className="qv-review-item">
                          <div className="qv-review-item-top">
                            <Stars value={r.stars} size="sm" />
                            {r.fit && <span className="qv-review-fit">{formatFitLabel(r.fit)}</span>}
                          </div>
                          {r.text && <p className="qv-review-body">{r.text}</p>}
                          {r.photo && <img className="qv-review-img" src={r.photo} alt="" />}
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              )}
            </section>
          </div>
        </div>

        <div className="qv-sticky">
          <div className="qv-sticky-meta">
            <strong className="qv-sticky-price">{formatPrice(product.price, product.currency)}</strong>
            <span className="qv-sticky-color">{product.color || product.category || ""}</span>
          </div>
          <button
            className={`qv-sticky-cart${inCart ? " in-cart" : ""}`}
            type="button"
            onClick={() => !inCart && onAddToCart?.(product)}
          >
            {inCart ? "In cart" : "Add"}
          </button>
          <a
            className="qv-sticky-shop"
            href={trackedAffiliateUrl(product)}
            target="_blank"
            rel="noopener noreferrer nofollow sponsored"
            onClick={() => onBuy?.(product)}
          >
            {shopLabel(product, { short: true })}
          </a>
        </div>
      </div>
    </div>
  );

  return createPortal(sheet, document.body);
}
