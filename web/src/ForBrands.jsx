import { useEffect } from "react";

/**
 * Brand partnership landing — what to show Myntra / Snitch / D2Cs in demos.
 * Accessible without auth so BD can share a link.
 */
export default function ForBrands({ onClose, onStartDemo }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose?.(); };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <div className="fb-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
      <div className="fb-panel" role="dialog" aria-modal="true" aria-label="Partner with Mira">
        <button type="button" className="fb-close" onClick={onClose} aria-label="Close">✕</button>

        <p className="fb-eyebrow">Partner with Mira</p>
        <h1 className="fb-title">Send high-intent shoppers to your store</h1>
        <p className="fb-lead">
          Mira is an AI stylist for India. We don’t sell inventory — we style people and
          hand them off to you with a tracked link. You keep checkout, shipping, and the customer.
        </p>

        <section className="fb-section">
          <h2>What brands get</h2>
          <ul>
            <li>Outfit-context traffic (not coupon spam)</li>
            <li>Deep links to your product pages</li>
            <li>UTM / SubID attribution on every click</li>
            <li>Premium positioning — we filter for elevated fashion</li>
            <li>Optional virtual try-on that showcases your product on the shopper</li>
          </ul>
        </section>

        <section className="fb-section">
          <h2>How integration works</h2>
          <ol className="fb-steps">
            <li><strong>Feed</strong> — CSV or API: id, name, brand, price, images, sizes, deep link, category</li>
            <li><strong>Commercials</strong> — CPS commission + cookie window (or fixed CPA test)</li>
            <li><strong>Go live</strong> — products appear in Mira’s catalog &amp; styling chats</li>
            <li><strong>Report</strong> — weekly clicks + attributed orders from your side</li>
          </ol>
        </section>

        <section className="fb-section">
          <h2>What we need from you</h2>
          <ul>
            <li>Product feed (daily or weekly refresh)</li>
            <li>Commission terms &amp; brand guidelines</li>
            <li>A partner contact for creative + catalog QA</li>
          </ul>
          <p className="fb-note">
            Template: <code>prototype/data/brand_feed_template.csv</code> in our repo —
            or email a Google Sheet with the same columns.
          </p>
        </section>

        <section className="fb-section fb-section--cta">
          <h2>Ready to talk?</h2>
          <p>
            Email your BD inbox with subject <em>Mira × [Brand] affiliate</em>
            {" "}and attach a sample feed (CSV template in repo).
          </p>
          <div className="fb-actions">
            <button type="button" className="fb-btn fb-btn--primary" onClick={onStartDemo}>
              See Mira live →
            </button>
            <button type="button" className="fb-btn" onClick={onClose}>
              Close
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
