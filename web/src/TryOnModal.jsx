import { useEffect, useRef, useState } from "react";

/* ── Minimal body-outline SVG silhouette ── */
function SilhouetteSVG() {
  return (
    <svg
      className="tryon-silhouette"
      viewBox="0 0 120 280"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      {/* Head */}
      <ellipse cx="60" cy="28" rx="18" ry="22" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" />
      {/* Neck */}
      <path d="M52 49 Q60 56 68 49" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
      {/* Shoulders */}
      <path d="M52 49 C38 54 24 64 18 80 L22 82 C28 68 40 60 52 56 Z" fill="currentColor" opacity=".15" />
      <path d="M68 49 C82 54 96 64 102 80 L98 82 C92 68 80 60 68 56 Z" fill="currentColor" opacity=".15" />
      {/* Torso outline */}
      <path
        d="M52 56 C40 60 28 70 26 90 L28 130 C30 140 32 144 60 144 C88 144 90 140 92 130 L94 90 C92 70 80 60 68 56 Q60 60 52 56 Z"
        stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round"
        fill="currentColor" opacity=".06"
      />
      {/* Arms */}
      <path d="M28 80 C18 95 14 115 16 140 L24 138 C22 115 26 96 34 82 Z" fill="currentColor" opacity=".12" />
      <path d="M92 80 C102 95 106 115 104 140 L96 138 C98 115 94 96 86 82 Z" fill="currentColor" opacity=".12" />
      {/* Waist pinch */}
      <path d="M28 128 Q60 136 92 128" stroke="currentColor" strokeWidth="2" strokeLinecap="round" opacity=".4" />
      {/* Hips */}
      <path
        d="M28 130 C22 148 20 162 26 178 L94 178 C100 162 98 148 92 130"
        stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round"
        fill="currentColor" opacity=".08"
      />
      {/* Legs */}
      <path d="M26 178 C22 210 24 240 28 268 L46 268 C44 240 42 210 46 178 Z" fill="currentColor" opacity=".1" />
      <path d="M74 178 C78 210 76 240 72 268 L90 268 C96 240 98 210 94 178 Z" fill="currentColor" opacity=".1" />
      {/* Dashed vertical centre line */}
      <line x1="60" y1="56" x2="60" y2="275" stroke="currentColor" strokeWidth="1" strokeDasharray="4 5" opacity=".2" />
      {/* Sparkle dots — hint of magic */}
      <circle cx="15" cy="55" r="2.5" fill="currentColor" opacity=".35" />
      <circle cx="105" cy="90" r="2" fill="currentColor" opacity=".28" />
      <circle cx="20" cy="170" r="1.8" fill="currentColor" opacity=".22" />
    </svg>
  );
}

export default function TryOnModal({ product, onClose, onTryOn, result, loading, error }) {
  const overlayRef = useRef(null);
  const fileRef = useRef(null);
  const [userPhoto, setUserPhoto] = useState(null); // data URL preview of uploaded photo

  /* Close on Escape key */
  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    /* Prevent body scroll while modal open */
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  /* Close on backdrop click */
  function handleOverlayClick(e) {
    if (e.target === overlayRef.current) onClose();
  }

  const emoji = {
    dresses: "👗", tops: "👚", bottoms: "👖", outerwear: "🧥",
    shoes: "👟", bags: "👜", accessories: "✨", activewear: "🏃",
  }[product.category] || "🛍️";

  const hasPhoto =
    product.image_url &&
    (product.image_url.includes("m.media-amazon.com") ||
      product.image_url.includes("images.pexels.com"));

  const handleFile = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result;
      setUserPhoto(dataUrl);
      const base64 = String(dataUrl).split(",")[1];
      onTryOn?.(product.id, base64, file.type || "image/jpeg");
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  // Only show a result if it belongs to THIS product.
  const myResult = result && result.productId === product.id ? result : null;

  return (
    <div
      className="tryon-overlay"
      ref={overlayRef}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-label="Virtual try-on"
    >
      <div className="tryon-modal">
        {/* Close */}
        <button className="tryon-close" onClick={onClose} aria-label="Close">
          ✕
        </button>

        {/* Header */}
        <div className="tryon-header">
          <span className="tryon-badge">✨ AI</span>
          <h2 className="tryon-title">Virtual Try-On</h2>
          <p className="tryon-subtitle">
            See how the {product.name?.split(" ").slice(0, 4).join(" ")} looks on you.
          </p>
        </div>

        {/* Visual area */}
        <div className="tryon-stage">
          {/* Left — product preview */}
          <div className="tryon-product-preview">
            {hasPhoto ? (
              <img
                className="tryon-product-img"
                src={product.image_url}
                alt={product.name}
                loading="lazy"
              />
            ) : (
              <div className="tryon-product-emoji-wrap">
                <span className="tryon-product-emoji">{emoji}</span>
              </div>
            )}
            <span className="tryon-product-label">Item</span>
          </div>

          {/* Connector arrow */}
          <div className="tryon-connector" aria-hidden="true">
            <svg viewBox="0 0 48 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M2 12 H44 M36 4 L44 12 L36 20" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span>+</span>
            <svg viewBox="0 0 48 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M2 12 H44 M36 4 L44 12 L36 20" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>

          {/* Right — result / your photo / silhouette */}
          <div className="tryon-silhouette-wrap">
            {myResult ? (
              <img
                className="tryon-product-img tryon-result-img"
                src={`data:${myResult.mime};base64,${myResult.image}`}
                alt="Virtual try-on result"
              />
            ) : loading ? (
              <>
                <SilhouetteSVG />
                <div className="tryon-shimmer-bar" aria-hidden="true" />
              </>
            ) : userPhoto ? (
              <img className="tryon-product-img" src={userPhoto} alt="Your photo" />
            ) : (
              <SilhouetteSVG />
            )}
            <span className="tryon-product-label">You</span>
          </div>
        </div>

        {/* CTA copy + upload */}
        <div className="tryon-cta-area">
          {loading ? (
            <p className="tryon-magic-text">Styling it on you… this takes a few seconds 🪄</p>
          ) : myResult ? (
            <p className="tryon-magic-text">Here's how it looks on you! ✨</p>
          ) : error ? (
            <p className="tryon-desc" style={{ color: "#c0103a" }}>{error}</p>
          ) : (
            <p className="tryon-desc">
              Upload a clear, front-facing full-body photo and Mira will show this
              piece styled on you — powered by AI.
            </p>
          )}

          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={handleFile}
          />
          <div className="tryon-actions">
            {!loading && (
              <button
                className="tryon-notify-btn"
                type="button"
                onClick={() => fileRef.current?.click()}
              >
                {myResult || error || userPhoto ? "Try another photo" : "Upload your photo"} 📷
              </button>
            )}
            <button className="tryon-skip-btn" type="button" onClick={onClose}>
              {myResult ? "Done" : "Maybe later"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
