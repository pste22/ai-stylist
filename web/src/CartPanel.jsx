import { useEffect, useMemo, useRef, useState } from "react";

function formatPrice(price, currency) {
  const isINR = (currency || "INR") === "INR";
  const num = Number(price) || 0;
  return isINR ? "₹" + num.toLocaleString("en-IN") : "$" + num.toLocaleString("en-US");
}

function formatTotal(items) {
  const inr = items.filter((p) => (p.currency || "INR") === "INR").reduce((s, p) => s + (Number(p.price) || 0), 0);
  const usd = items.filter((p) => p.currency === "USD").reduce((s, p) => s + (Number(p.price) || 0), 0);
  const parts = [];
  if (inr) parts.push("₹" + inr.toLocaleString("en-IN"));
  if (usd) parts.push("$" + usd.toLocaleString("en-US"));
  return parts.join(" + ") || "₹0";
}

export default function CartPanel({ items, onRemove, onClear, onClose, onTryOn }) {
  const overlayRef = useRef(null);
  const [nextIdx, setNextIdx] = useState(0);
  const [copied, setCopied] = useState(false);

  const openables = useMemo(
    () => items.filter((p) => p.affiliate_url),
    [items],
  );

  useEffect(() => {
    setNextIdx(0);
    setCopied(false);
  }, [items.length]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  const handleBackdrop = (e) => { if (e.target === overlayRef.current) onClose(); };

  const openNext = () => {
    if (!openables.length) return;
    const i = nextIdx % openables.length;
    window.open(openables[i].affiliate_url, "_blank", "noopener,noreferrer");
    setNextIdx(i + 1);
  };

  const copyList = async () => {
    const lines = items.map((p) => {
      const price = formatPrice(p.price, p.currency);
      return `${p.name} — ${price}${p.affiliate_url ? `\n${p.affiliate_url}` : ""}`;
    });
    const text = lines.join("\n\n");
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* ignore */
    }
  };

  const openLabel = !openables.length
    ? "No Amazon links"
    : nextIdx === 0
      ? `Open on Amazon${openables.length > 1 ? ` (1 of ${openables.length})` : ""}`
      : nextIdx >= openables.length
        ? "Open first again"
        : `Open next (${nextIdx + 1} of ${openables.length})`;

  return (
    <div className="cart-backdrop" ref={overlayRef} onClick={handleBackdrop} role="dialog" aria-modal="true" aria-label="Your cart">
      <div className="cart-panel">

        <div className="cart-header">
          <h2 className="cart-title">Your Cart <span className="cart-count">{items.length}</span></h2>
          <button className="cart-close" onClick={onClose} aria-label="Close cart">✕</button>
        </div>

        {items.length === 0 ? (
          <div className="cart-empty">
            <span className="cart-empty-icon">✦</span>
            <p>Your cart is empty.</p>
            <p className="cart-empty-sub">Ask Mira for recommendations and add items here.</p>
          </div>
        ) : (
          <>
            <div className="cart-items">
              {items.map((p) => (
                <div key={p.id} className="cart-item">
                  <div className="cart-item-img-wrap">
                    {p.image_url && (p.image_url.includes("m.media-amazon.com") || p.image_url.includes("images.pexels.com"))
                      ? <img className="cart-item-img" src={p.image_url} alt={p.name} loading="lazy" decoding="async" />
                      : <div className="cart-item-img-fallback">✦</div>
                    }
                  </div>
                  <div className="cart-item-info">
                    <p className="cart-item-name">{p.name}</p>
                    <p className="cart-item-meta">{p.color && <span>{p.color}</span>}{p.category && <span>{p.category}</span>}</p>
                    <strong className="cart-item-price">{formatPrice(p.price, p.currency)}</strong>
                  </div>
                  <div className="cart-item-actions">
                    {onTryOn && (
                      <button
                        className="cart-item-tryon"
                        onClick={() => { onClose?.(); onTryOn(p); }}
                        title="Virtual try-on"
                      >Try on</button>
                    )}
                    <a
                      className="cart-item-buy"
                      href={p.affiliate_url}
                      target="_blank"
                      rel="noopener noreferrer nofollow sponsored"
                      title="Buy on Amazon"
                    >Buy →</a>
                    <button className="cart-item-remove" onClick={() => onRemove(p.id)} aria-label="Remove">✕</button>
                  </div>
                </div>
              ))}
            </div>

            <div className="cart-footer">
              <div className="cart-total-row">
                <span className="cart-total-label">Estimated total</span>
                <strong className="cart-total-price">{formatTotal(items)}</strong>
              </div>
              <p className="cart-total-note">Final prices on Amazon may vary. Mira earns a small commission.</p>
              <button
                className="cart-open-all-btn"
                onClick={openNext}
                disabled={!openables.length}
              >
                {openLabel}
              </button>
              <button className="cart-clear-btn" type="button" onClick={copyList}>
                {copied ? "Copied look list" : "Copy look list"}
              </button>
              <button className="cart-clear-btn" onClick={onClear}>Clear cart</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
