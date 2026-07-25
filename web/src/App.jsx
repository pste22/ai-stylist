import { useEffect, useMemo, useRef, useState } from "react";
import RiveAvatar from "./RiveAvatar.jsx";
import ProductCard from "./ProductCard.jsx";
import LoginScreen from "./LoginScreen.jsx";
import OnboardingFlow from "./OnboardingFlow.jsx";
import EventBriefFlow from "./EventBriefFlow.jsx";
import ChatHistory from "./ChatHistory.jsx";
import { useMiraVoice } from "./useMiraVoice.js";
import { useAuth } from "./useAuth.js";
import { useOnboarding } from "./useOnboarding.js";
import { useIdleTimeout } from "./useIdleTimeout.js";
import { useChatHistory } from "./useChatHistory.js";
import PrivacyPolicy from "./PrivacyPolicy.jsx";
import ProductQuickView from "./ProductQuickView.jsx";
import CartPanel from "./CartPanel.jsx";
import { useCart } from "./useCart.js";
import { useNetworkMode, checkNetworkNow } from "./useNetworkMode.js";

// ─── User avatar menu (dropdown) ─────────────────────────────────────────────
function UserMenu({ userName, userEmail, userAvatar, onSignOut, onDeleteAccount }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  return (
    <div className="user-menu-wrap" ref={ref}>
      <button className="user-pill" onClick={() => setOpen(v => !v)} title="Account">
        {userAvatar
          ? <img className="user-avatar" src={userAvatar} alt={userName} referrerPolicy="no-referrer" />
          : <span className="user-initials">{userName[0]?.toUpperCase()}</span>}
        <span className="user-name">{userName}</span>
        <span className="user-chevron">{open ? "▴" : "▾"}</span>
      </button>
      {open && (
        <div className="user-dropdown">
          <div className="user-dropdown-info">
            <p className="user-dropdown-name">{userName}</p>
            {userEmail && <p className="user-dropdown-email">{userEmail}</p>}
          </div>
          <hr className="user-dropdown-divider" />
          <button className="user-dropdown-signout" onClick={() => { setOpen(false); onSignOut(); }}>
            Sign out
          </button>
          <button className="user-dropdown-signout" style={{ color: "#c0103a", marginTop: ".25rem" }}
            onClick={() => { setOpen(false); onDeleteAccount(); }}>
            Delete account
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Signal strength indicator ───────────────────────────────────────────────
function SignalBars({ quality }) {
  const levels = { good: 3, moderate: 2, slow: 1, datasaver: 0, unknown: 3 };
  const colors = { good: "#22c55e", moderate: "#f59e0b", slow: "#ef4444", datasaver: "#ef4444", unknown: "#94a3b8" };
  const level = levels[quality] ?? 3;
  const color = colors[quality] ?? "#94a3b8";
  const label = quality === "datasaver" ? "Data Saver on" : `Network: ${quality}`;
  return (
    <span className="signal-bars" title={label} aria-label={label}>
      {[1, 2, 3].map((i) => (
        <span key={i} className={`sig-bar sig-bar-${i}`} style={i <= level ? { background: color } : {}} />
      ))}
    </span>
  );
}

// ─── Network quality toast ────────────────────────────────────────────────────
function NetworkToast({ message, action, onAction, onDismiss }) {
  return (
    <div className="net-toast">
      <span className="net-toast-icon">📶</span>
      <span className="net-toast-msg">{message}</span>
      {action && (
        <button className="net-toast-action" onClick={onAction}>{action}</button>
      )}
      <button className="net-toast-dismiss" onClick={onDismiss} aria-label="Dismiss">✕</button>
    </div>
  );
}

// ─── Delete account confirmation modal ───────────────────────────────────────
function DeleteAccountModal({ onConfirm, onCancel }) {
  const [deleting, setDeleting] = useState(false);
  const confirm = async () => {
    setDeleting(true);
    await onConfirm();
  };
  return (
    <div className="delete-overlay">
      <div className="delete-modal">
        <div className="delete-modal-icon">🗑️</div>
        <h3 className="delete-modal-title">Delete your account?</h3>
        <p className="delete-modal-body">
          This permanently removes your profile, style preferences, saved products,
          and session history. This cannot be undone.
        </p>
        <div className="delete-modal-actions">
          <button className="delete-btn-confirm" onClick={confirm} disabled={deleting}>
            {deleting ? "Deleting…" : "Yes, delete my account"}
          </button>
          <button className="delete-btn-cancel" onClick={onCancel} disabled={deleting}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Connection error card ────────────────────────────────────────────────────
const CONN_MESSAGES = [
  "Mira is taking a quick break — tap to try again.",
  "Still having trouble connecting — one more try?",
  "Something's wrong on our end. We'll be back soon.",
];
function ConnectionError({ retryCount, onRetry }) {
  const msg = CONN_MESSAGES[Math.min(retryCount - 1, CONN_MESSAGES.length - 1)];
  const isTerminal = retryCount >= 3;
  return (
    <div className="conn-error-card">
      <span className="conn-error-icon">{isTerminal ? "⚠️" : "📡"}</span>
      <p className="conn-error-msg">{msg}</p>
      {!isTerminal && (
        <button className="conn-error-retry" onClick={onRetry}>Try again</button>
      )}
    </div>
  );
}

// ─── Session expiry warning modal ────────────────────────────────────────────
function SessionWarning({ countdown, onStay, onLeave }) {
  return (
    <div className="session-overlay">
      <div className="session-modal">
        <div className="session-icon">⏱</div>
        <h3 className="session-title">Still there?</h3>
        <p className="session-body">
          You've been away for a while. For your security, we'll sign you out in
        </p>
        <p className="session-countdown">{countdown}s</p>
        <div className="session-actions">
          <button className="session-btn-stay" onClick={onStay}>Keep me signed in</button>
          <button className="session-btn-leave" onClick={onLeave}>Sign out now</button>
        </div>
      </div>
    </div>
  );
}

// ─── Inline rendering helper ──────────────────────────────────────────────────
function renderInline(str) {
  return str.split(/(\*\*[^*]+\*\*)/).map((seg, i) =>
    seg.startsWith("**") && seg.endsWith("**")
      ? <strong key={i}>{seg.slice(2, -2)}</strong>
      : seg
  );
}

// Returns true for lines that look like a bare product title Mira leaked into text.
// Heuristic: long (>30 chars), no sentence-ending verb cues, title-case or all-caps words.
// We drop these so product cards are the only representation of the item.
function _looksLikeProductTitle(line) {
  const t = line.trim();
  if (t.length < 20 || t.length > 200) return false;
  // Must not contain a verb-y word that makes it a real sentence
  if (/\b(is|are|was|were|will|would|can|could|should|love|think|feel|looks?|sounds?|perfect|great|amazing|fits?|suits?)\b/i.test(t)) return false;
  // Looks like a product name: starts with a year, brand word, or Women's/Men's/etc.
  if (/^(20\d\d\b|women'?s?\b|men'?s?\b|girls?\b|boys?\b)/i.test(t)) return true;
  // Very long noun phrase (no punctuation, many title-case words)
  const words = t.split(/\s+/);
  const titleCaseCount = words.filter(w => /^[A-Z]/.test(w)).length;
  return words.length >= 4 && titleCaseCount >= words.length * 0.6 && !/[.!?]$/.test(t);
}

// ─── Integrated bubble: text + product images inline ─────────────────────────
// Renders Mira's text with markdown-lite formatting — NO product cards.
// Products always appear in the ProductGrid below the bubble.
function MiraBubbleContent({ text }) {
  const lines = text.split("\n");
  const blocks = [];
  const pendingBullets = [];
  let key = 0;

  const flushBullets = () => {
    if (pendingBullets.length) {
      blocks.push(
        <ul className="bubble-list" key={key++}>
          {pendingBullets.splice(0).map((item, i) => <li key={i}>{item}</li>)}
        </ul>
      );
    }
  };

  lines.forEach((line) => {
    const bullet = line.match(/^[•\-\*\d+\.]\s+(.*)/);
    if (bullet) {
      // Drop bullet lines that are just product names — cards show below
      const content = bullet[1];
      if (_looksLikeProductTitle(content)) return;
      const nameOnly = content.split("—")[0].trim();
      pendingBullets.push(renderInline(nameOnly || content));
    } else {
      flushBullets();
      const trimmed = line.trim();
      // Drop plain lines that are bare product titles leaked into the text
      if (trimmed && !_looksLikeProductTitle(trimmed)) {
        blocks.push(<p key={key++}>{renderInline(trimmed)}</p>);
      }
    }
  });
  flushBullets();
  return <>{blocks}</>;
}

// Unified 3-column product grid — single source of truth for product display.
const PRODUCTS_PER_TURN = 3;
function ProductGrid({ products, loved, onLove, onBuy, highlightedId, onSelect, inCart, onAddToCart }) {
  if (!products?.length) return null;
  const shown = products.slice(0, PRODUCTS_PER_TURN);
  return (
    <div className="product-grid">
      {shown.map((p) => (
        <ProductCard key={p.id} product={p} loved={loved.has(p.id)}
          onLove={onLove} onBuy={onBuy} highlight={p.id === highlightedId} onSelect={onSelect}
          inCart={inCart?.(p.id)} onAddToCart={onAddToCart} />
      ))}
    </div>
  );
}

// Colour swatch helper (mirrors ProductCard.jsx)
function swatchColor(color) {
  const map = {
    sand: "#d8c5a0", white: "#f4f4f0", charcoal: "#3a3a3a", forest: "#2e4a36",
    black: "#222", indigo: "#34406b", cream: "#efe6d2", olive: "#6b6b3a",
    burgundy: "#6b2a35", sage: "#a8b8a0", camel: "#c2956a", "washed blue": "#7e9bbf",
    tan: "#c19a6b", "off-white": "#efece4", nude: "#e3c4ad", rust: "#9c5a32",
    emerald: "#1f6b53", brown: "#6b4a30",
    gray: "#999", grey: "#999", beige: "#d4c4a8", khaki: "#c2a96a",
    natural: "#e8dcc8", blue: "#7e9bbf",
  };
  return map[color?.toLowerCase()] || "#cbb9a8";
}

// ─── Mini avatar shown in the chat header ────────────────────────────────────
function MiniAvatar({ state, mood }) {
  return (
    <div className={`mini-avatar state-${state} mood-${mood}`}>
      <div className="mini-brows">
        <div className="mini-brow left" />
        <div className="mini-brow right" />
      </div>
      <div className="mini-eyes">
        <div className="mini-eye" />
        <div className="mini-eye" />
      </div>
      <div className={`mini-mouth${state === "talking" ? " talking" : ""}`} />
    </div>
  );
}

// ─── Product strip below a Mira bubble (outside the text bubble itself) ──────
function BubbleProducts({ products, loved, onLove, onBuy }) {
  if (!products?.length) return null;
  return (
    <div className="bubble-products">
      {products.map((p) => (
        <ProductCard
          key={p.id}
          product={p}
          loved={loved.has(p.id)}
          onLove={onLove}
          onBuy={onBuy}
          compact
        />
      ))}
    </div>
  );
}

function LookDeck({ looks, loved, onLove, onBuy, onSaveLook, onAddAllToCart }) {
  if (!looks?.length) return null;
  return (
    <section className="look-deck" aria-label="Mira's complete look drafts">
      <div className="look-deck-heading">
        <p className="look-deck-eyebrow">✦ Mira Event Edit</p>
        <h2>Three ways to make it yours</h2>
      </div>
      <div className="look-grid">
        {looks.map((look) => {
          const allSaved = look.items.every((p) => loved.has(p.id));
          const total = look.items.reduce((s, p) => s + (Number(p.price) || 0), 0);
          return (
            <article className="look-card" key={look.id}>
              <div className="look-card-head">
                <h3>{look.name}</h3>
                <strong className="look-total">₹{total.toLocaleString("en-IN")}</strong>
              </div>
              <p className="look-rationale">{look.rationale}</p>
              <div className="look-items">
                {look.items.map((product) => (
                  <ProductCard key={product.id} product={product} compact
                    loved={loved.has(product.id)} onLove={onLove} onBuy={onBuy} />
                ))}
              </div>
              <div className="look-actions">
                <button
                  className={`look-save${allSaved ? " look-save--saved" : ""}`}
                  onClick={() => !allSaved && onSaveLook(look.items)}
                >
                  {allSaved ? "♥ Saved" : "♡ Save"}
                </button>
                <button
                  className="look-cart-btn"
                  onClick={() => onAddAllToCart?.(look.items)}
                >
                  🛒 Add look to cart
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

const CATEGORY_EMOJI = {
  dresses: "👗", tops: "👚", bottoms: "👖", outerwear: "🧥",
  shoes: "👟", bags: "👜", accessories: "✨", activewear: "🏃",
};

// ─── Deterministic social-proof numbers (stable per product id) ──────────────
function pseudoRandom(id, seed) {
  let h = seed | 0;
  for (const c of String(id || "")) h = (Math.imul(31, h) + c.charCodeAt(0)) | 0;
  return Math.abs(h);
}

// ─── Empty right-panel state ──────────────────────────────────────────────────
function EmptyProductSpot({ onSendPrompt }) {
  const prompts = [
    "Show me summer dresses under $80",
    "What's trending in sneakers right now?",
    "I need a cozy weekend outfit",
  ];
  return (
    <div className="featured-empty">
      <div className="featured-empty-glow">✦</div>
      <p className="featured-empty-head">Your style spotlight</p>
      <p className="featured-empty-sub">
        Products Mira recommends will appear here with full details
      </p>
      {onSendPrompt && (
        <div className="featured-empty-prompts">
          {prompts.map((p) => (
            <button key={p} className="featured-prompt-chip" onClick={() => onSendPrompt(p)}>
              {p}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Large featured product in the right panel ────────────────────────────────
function FeaturedProduct({ product, loved, onLove, onBuy, reason, onSendPrompt }) {
  if (!product) return <EmptyProductSpot onSendPrompt={onSendPrompt} />;

  const isLoved = loved.has(product.id);
  const usePhoto = product.image_url && (
    product.image_url.includes("m.media-amazon.com") ||
    product.image_url.includes("images.pexels.com")
  );

  const savedCount  = pseudoRandom(product.id, 1337) % 40 + 8;
  const ratingTenths = pseudoRandom(product.id, 4242) % 13 + 37;
  const rating      = (ratingTenths / 10).toFixed(1);
  const filledStars = Math.floor(ratingTenths / 10);
  const starStr     = "★".repeat(filledStars) + "☆".repeat(5 - filledStars);
  const isTrending  = pseudoRandom(product.id, 7777) % 5 === 0;
  const isNew       = pseudoRandom(product.id, 9999) % 8 === 0 && !isTrending;

  return (
    <div className="fp-product">
      <div className="fp-img-wrap">
        {usePhoto
          ? <img className="fp-img" src={product.image_url} alt={product.name} loading="lazy" />
          : <div className="fp-cat-thumb" style={{ "--swatch": swatchColor(product.color) }}>
              <span className="fp-cat-emoji">{CATEGORY_EMOJI[product.category] || "🛍️"}</span>
            </div>
        }

        {isTrending && <span className="fp-badge fp-badge--hot">🔥 Trending</span>}
        {isNew      && <span className="fp-badge fp-badge--new">✦ New In</span>}

        <button
          className={`fp-heart${isLoved ? " is-loved" : ""}`}
          onClick={() => onLove(product)}
          aria-label={isLoved ? "Remove from saved" : "Save"}
        >{isLoved ? "♥" : "♡"}</button>

        {reason && (
          <div className="fp-img-hover">
            <p className="fp-img-hover-text">"{reason}"</p>
          </div>
        )}

        <div className="fp-img-bar">
          <div className="fp-bar-text">
            <p className="fp-bar-name">{product.name}</p>
            <p className="fp-bar-price">{product.currency === "INR" ? "₹" : "$"}{product.price}</p>
          </div>
          <a
            className="fp-bar-cta"
            href={product.affiliate_url}
            target="_blank"
            rel="noopener noreferrer nofollow sponsored"
            onClick={() => onBuy?.(product)}
          >Shop →</a>
        </div>
      </div>

      <div className="fp-details">
        <div className="fp-miras-pick">✦ Mira's Pick</div>

        <div className="fp-social">
          <span className="fp-stars">{starStr}</span>
          <span className="fp-rating">{rating}</span>
          <span className="fp-sep">·</span>
          <span className="fp-saved">{savedCount} saved this week</span>
        </div>

        {reason && (
          <div className="fp-why">
            <p className="fp-why-label">✦ Why Mira chose this</p>
            <p className="fp-why-text">"{reason}"</p>
          </div>
        )}

        <a
          className="fp-cta"
          href={product.affiliate_url}
          target="_blank"
          rel="noopener noreferrer nofollow sponsored"
          onClick={() => onBuy?.(product)}
        >
          Shop Now
          <span className="fp-cta-arrow">→</span>
        </a>

        <p className="fp-disclosure">Affiliate link · Mira earns a small commission</p>
      </div>
    </div>
  );
}

// ─── Full-screen chat view (kept for reference; not rendered in main path) ────
function ChatView({ state, mood, messages, loved, savedProducts, onLove, onBuy,
                    onStop, onSend, error, userName, userEmail, userAvatar, onSignOut, onDeleteAccount,
                    canShowMore, onShowMore, products, looks, onSaveLook, highlightedId }) {
  const [draft, setDraft] = useState("");
  const threadRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    const el = threadRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const submit = () => {
    const text = draft.trim();
    if (!text) return;
    onSend(text);
    setDraft("");
    inputRef.current?.focus();
  };

  const onKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
  };

  const statusLabel = state === "thinking" ? "thinking…"
                    : state === "talking"  ? "replying…"
                    : "online";

  const sendChip = (text) => onSend(text);

  const featuredProduct = useMemo(
    () => products.find((p) => p.id === highlightedId) || null,
    [products, highlightedId]
  );

  const featuredReason = useMemo(() => {
    if (!featuredProduct) return null;
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.role === "mira" && m.text) {
        const lower = m.text.toLowerCase();
        const name = featuredProduct.name.toLowerCase();
        if (lower.includes(name.split(" ")[0])) {
          const sentences = m.text.split(/(?<=[.!?])\s+/);
          const hit = sentences.find((s) => s.toLowerCase().includes(name.split(" ")[0]));
          if (hit && hit.length < 200) return hit.trim();
        }
      }
    }
    return null;
  }, [featuredProduct, messages]);

  return (
    <div className="chat-layout">
      <div className="chat-header">
        <MiniAvatar state={state} mood={mood} />
        <div className="chat-header-info">
          <span className="chat-name">Mira</span>
          <span className={`chat-status status-${state}`}>{statusLabel}</span>
        </div>
        <div className="chat-header-actions">
          {savedProducts.length > 0 && (
            <span className="chat-saved-badge">💜 {savedProducts.length}</span>
          )}
          <button className="chat-end-btn" onClick={onStop}>⏹ End</button>
          <UserMenu userName={userName} userEmail={userEmail} userAvatar={userAvatar} onSignOut={onSignOut} onDeleteAccount={onDeleteAccount} />
        </div>
      </div>

      <div className="chat-body">
        <div className="chat-left">
          <div className="chat-thread" ref={threadRef}>
            <LookDeck looks={looks} loved={loved} onLove={onLove} onBuy={onBuy} onSaveLook={onSaveLook} />
            {messages.length === 0 && (
              <div className="chat-empty">
                <span>Mira is thinking of a greeting…</span>
              </div>
            )}
            {messages.map((msg) => (
              <div key={msg.id} className={`bubble-row row-${msg.role}`}>
                {msg.role === "mira" && <div className="bubble-avatar-dot" />}
                <div className="bubble-col">
                  <div className={`bubble bubble-${msg.role}`}>
                    {msg.role === "mira"
                      ? <MiraBubbleContent
                          text={msg.text}
                          products={msg.products}
                          loved={loved}
                          onLove={onLove}
                          onBuy={onBuy}
                        />
                      : msg.text}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {canShowMore && (
            <div className="show-more-bar">
              <button className="show-more-btn" onClick={onShowMore}>
                Show 3 more →
              </button>
            </div>
          )}

          <div className="chat-input-area">
            {error && <p className="chat-error">{error}</p>}
            <div className="chat-input-bar">
              <textarea
                ref={inputRef}
                className="chat-input"
                rows={1}
                placeholder="Message Mira…"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={onKey}
                autoFocus
              />
              <button
                className="chat-send-btn"
                onClick={submit}
                disabled={!draft.trim()}
                aria-label="Send"
              >
                ↑
              </button>
            </div>
            <p className="chat-hint">Enter to send · Shift+Enter for new line</p>
          </div>
        </div>

        <div className="chat-right">
          <FeaturedProduct
            key={featuredProduct?.id || "empty"}
            product={featuredProduct}
            loved={loved}
            onLove={onLove}
            onBuy={onBuy}
            reason={featuredReason}
            onSendPrompt={sendChip}
          />
        </div>
      </div>
    </div>
  );
}

// ─── Persistent location chip — always visible, always editable ──────────────
async function _fetchCity(pin) {
  try {
    const r = await fetch(`https://api.postalpincode.in/pincode/${pin}`);
    const d = await r.json();
    if (d?.[0]?.Status === "Success") {
      const po = d[0].PostOffice?.[0];
      return po ? po.District : null;
    }
  } catch { /* ignore */ }
  return null;
}

function PinChip({ pinCode, onSave }) {
  // All hooks at the top — no hooks after conditionals
  const [editing, setEditing]       = useState(false);
  const [draft, setDraft]           = useState(pinCode || "");
  const [city, setCity]             = useState(null);
  const [cityLoading, setCityLoading] = useState(false);
  const [draftCity, setDraftCity]   = useState(null);
  const [draftLoading, setDraftLoading] = useState(false);
  const inputRef = useRef(null);

  // Resolve saved pin code → city on mount / when pinCode prop changes
  useEffect(() => {
    if (!pinCode) return;
    setCityLoading(true);
    _fetchCity(pinCode).then(c => { setCity(c); setCityLoading(false); });
  }, [pinCode]);

  const resolveDraft = (pin) => {
    if (pin.length !== 6) { setDraftCity(null); return; }
    setDraftLoading(true);
    _fetchCity(pin).then(c => { setDraftCity(c); setDraftLoading(false); });
  };

  const open = () => {
    setDraft(pinCode || "");
    setDraftCity(null);
    setEditing(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const save = async () => {
    const clean = draft.replace(/\D/g, "");
    if (clean.length !== 6) return;
    onSave(clean);
    setCity(draftCity);
    setEditing(false);
  };

  if (editing) {
    return (
      <div className="location-bar location-bar--editing">
        <span className="location-bar-icon">📍</span>
        <input
          ref={inputRef}
          className="location-bar-input"
          value={draft}
          maxLength={6}
          inputMode="numeric"
          placeholder="Enter 6-digit PIN code"
          onChange={(e) => {
            const v = e.target.value.replace(/\D/g, "");
            setDraft(v);
            resolveDraft(v);
          }}
          onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") setEditing(false); }}
        />
        {draftLoading && <span className="location-bar-resolving">Looking up…</span>}
        {draftCity && !draftLoading && <span className="location-bar-city-preview">{draftCity}</span>}
        <button className="location-bar-confirm" onClick={save} disabled={draft.replace(/\D/g, "").length !== 6}>Save</button>
        <button className="location-bar-cancel" onClick={() => setEditing(false)}>✕</button>
      </div>
    );
  }

  return (
    <button className="location-bar" onClick={open}>
      <span className="location-bar-icon">📍</span>
      <span className="location-bar-text">
        {cityLoading
          ? "Locating…"
          : city
            ? <><strong>{city}</strong><span className="location-bar-pin"> · {pinCode}</span></>
            : pinCode
              ? pinCode
              : <span className="location-bar-prompt">Tap to set your location for better recommendations</span>
        }
      </span>
      <span className="location-bar-edit">Edit</span>
    </button>
  );
}

// ─── Small pulsing Mira dot — expands when talking ───────────────────────────
function MiraDot({ state, mood, audioActive }) {
  const isTalking = state === "talking";
  return (
    <div className={`mira-dot ${state} ${audioActive ? "audio-on" : ""} ${isTalking ? "expanded" : ""}`}
      aria-label={`Mira is ${state}`}>
      <span className="mira-dot-inner" />
    </div>
  );
}

// ─── Mode toggle — compact, lives in header ───────────────────────────────────
function ModeToggle({ textMode, connected, quality, onVoice, onText }) {
  const isSlow = quality === "slow" || quality === "datasaver";
  return (
    <div className="mode-toggle-compact" role="group" aria-label="Input mode">
      <button className={`mtc-btn${!textMode ? " active" : ""}`} onClick={onVoice}
        title={isSlow ? "Slow connection" : "Voice mode"}>
        🎙️{!textMode && connected && <SignalBars quality={quality} />}
      </button>
      <button className={`mtc-btn${textMode ? " active" : ""}`} onClick={onText}>
        ⌨️
      </button>
    </div>
  );
}

// ─── Chat welcome / empty state — shown before first message ─────────────────
function ChatWelcome({ onEventBrief, textMode }) {
  return (
    <div className="chat-welcome">
      <p className="chat-welcome-title">Hi, I'm Mira ✦</p>
      <p className="chat-welcome-sub">
        {textMode ? "Type to ask me anything about style." : "Tap Start talking and ask me anything."}
      </p>
      <button className="event-brief-chip" onClick={onEventBrief}>
        ✦ Plan an outfit for an event
      </button>
    </div>
  );
}

// ─── Message bubble — user or Mira, with inline product cards ────────────────
function MessageBubble({ msg, loved, onLove, onBuy, highlightedId, onSelect, inCart, onAddToCart }) {
  const isMira = msg.role === "mira";
  return (
    <div className={`msg-row ${isMira ? "mira" : "you"}`}>
      {isMira && <span className="msg-avatar-dot" />}
      <div className="msg-bubble-wrap">
        <div className={`msg-bubble ${isMira ? "mira" : "you"}`}>
          {isMira ? <MiraBubbleContent text={msg.text} /> : msg.text}
        </div>
        {isMira && (
          <ProductGrid
            products={msg.products}
            loved={loved}
            onLove={onLove}
            onBuy={onBuy}
            highlightedId={highlightedId}
            onSelect={onSelect}
            inCart={inCart}
            onAddToCart={onAddToCart}
          />
        )}
      </div>
    </div>
  );
}

// ─── Mode-switch / system event divider ──────────────────────────────────────
function EventDivider({ text }) {
  return (
    <div className="event-divider">
      <span className="event-divider-line" />
      <span className="event-divider-text">{text}</span>
      <span className="event-divider-line" />
    </div>
  );
}

// ─── Typing/thinking indicator ────────────────────────────────────────────────
function ThinkingBubble() {
  return (
    <div className="msg-row mira">
      <span className="msg-avatar-dot" />
      <div className="msg-bubble mira thinking-bubble">
        <span /><span /><span />
      </div>
    </div>
  );
}

// ─── Text input row (silent mode) ────────────────────────────────────────────
function TextInputRow({ onSend, onStop, onSwitchVoice }) {
  const [draft, setDraft] = useState("");
  const send = () => { if (draft.trim()) { onSend(draft.trim()); setDraft(""); } };
  return (
    <div className="text-input-row">
      <button className="mode-switch-btn" onClick={onSwitchVoice} title="Switch to voice">🎙️</button>
      <input className="chat-input" value={draft} onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), send())}
        placeholder="Message Mira…" autoFocus />
      <button className="send-btn" onClick={send} disabled={!draft.trim()}>Send</button>
      <button className="stop-btn-sm" onClick={onStop} title="End conversation">⏹</button>
    </div>
  );
}

// ─── Voice active bar — shows waveform level + stop ──────────────────────────
function VoiceActiveBar({ level, onStop, captions, onSwitchText }) {
  return (
    <div className="voice-active-bar">
      <span className="voice-listening-dot" />
      <span className="voice-caption">{captions.you || "Listening…"}</span>
      <button className="mode-switch-btn" onClick={onSwitchText} title="Switch to text">⌨️</button>
      <button className="stop-btn-sm" onClick={onStop} title="End conversation">⏹</button>
    </div>
  );
}

// ─── Main App ────────────────────────────────────────────────────────────────
export default function App() {
  const {
    user, loading,
    userId, userName, userAvatar,
    signInWithGoogle, signInWithFacebook, signInWithGithub, signOut, deleteAccount,
  } = useAuth();

  const { needsOnboarding, prefs, completeOnboarding, updatePrefs } = useOnboarding(userId);
  const { showWarning, countdown, staySignedIn } = useIdleTimeout({ onSignOut: signOut, enabled: !!user });
  const history = useChatHistory(userId);

  const { isSlow, isRecovered, quality }  = useNetworkMode();
  const autoSwitchedRef                   = useRef(false);
  const threadRef                         = useRef(null);
  const [isGuest, setIsGuest]             = useState(false);
  const [textMode, setTextMode]           = useState(false);
  const [networkToast, setNetworkToast]   = useState(null);
  const [showSaved, setShowSaved]         = useState(false);
  const [showHistory, setShowHistory]     = useState(false);
  const [showEventBrief, setShowEventBrief] = useState(false);
  const [eventBrief, setEventBrief]       = useState(null);
  const [startRequested, setStartRequested] = useState(false);
  const [showPrivacy, setShowPrivacy]     = useState(false);
  const [showDeleteModal, setShowDelete]  = useState(false);
  const [guestPinCode, setGuestPinCode]   = useState(null);
  const [quickViewProduct, setQuickViewProduct] = useState(null);
  const [showCart, setShowCart]           = useState(false);
  const { items: cartItems, addItem: addToCart, addItems: addAllToCart, removeItem: removeFromCart, clearCart, inCart } = useCart();
  const effectivePrefs = useMemo(
    () => user ? prefs : { ...(prefs || {}), pin_code: guestPinCode },
    [user, prefs, guestPinCode]
  );

  const {
    connected, state, mood, captions, messages,
    products, looks, savedProducts, loved, highlightedId, error, retryCount,
    canShowMore, setCanShowMore,
    productTimeline, switchAudio, updateLocation, addSystemEvent, clearHistory,
    start, stop, retry, sendText, wouldBuy, getLevel, buyClick, showMore,
  } = useMiraVoice({ userId, userName, userPrefs: effectivePrefs, eventBrief, textMode, onAddToCart: addToCart });

  // Auto-scroll thread on new messages
  useEffect(() => {
    const el = threadRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  // ── Mode switch functions (no stop/restart — switchAudio handles it) ────────
  const switchToVoice = async () => {
    const q = checkNetworkNow();
    if (q === "slow" || q === "datasaver") {
      const warn = q === "datasaver"
        ? "Data Saver is on. Voice will use mobile data."
        : "Connection is slow. Voice may be choppy.";
      setNetworkToast({
        message: warn,
        action: "Use voice anyway",
        onAction: async () => {
          setTextMode(false);
          if (connected) await switchAudio(true);
          addSystemEvent("🎙️ Switched to voice");
          setNetworkToast(null);
        },
      });
    } else {
      setTextMode(false);
      if (connected) await switchAudio(true);
      if (messages.length > 0) addSystemEvent("🎙️ Switched to voice");
    }
  };

  const switchToSilent = async () => {
    setTextMode(true);
    if (connected) await switchAudio(false);
    if (messages.length > 0) addSystemEvent("⌨️ Switched to text");
  };

  // Network degradation — auto-switch to text
  useEffect(() => {
    if (!isSlow) return;
    const msg = quality === "datasaver"
      ? "Data Saver is on — switched to text mode to save your data."
      : "Connection is slow — switched to text mode.";
    autoSwitchedRef.current = true;
    setNetworkToast({ message: msg, action: null });
    switchToSilent();
  }, [isSlow]); // eslint-disable-line react-hooks/exhaustive-deps

  // Connection recovered — offer to go back to voice
  useEffect(() => {
    if (isRecovered && autoSwitchedRef.current && !connected) {
      setNetworkToast({
        message: "Connection improved!",
        action: "Switch to voice",
        onAction: () => {
          setTextMode(false);
          autoSwitchedRef.current = false;
          setNetworkToast(null);
        },
      });
    }
  }, [isRecovered]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (startRequested && eventBrief && !connected) {
      setStartRequested(false);
      start();
    }
  }, [startRequested, eventBrief, connected, start]);

  const startEventEdit = (brief) => {
    setEventBrief(brief);
    setTextMode(true);
    setShowEventBrief(false);
    setStartRequested(true);
  };

  const saveLook = (items) => {
    items.forEach((product) => {
      if (!loved.has(product.id)) wouldBuy(product);
    });
  };

  // Splash while checking for existing session or onboarding status
  if (loading || (user && needsOnboarding === null)) {
    return <div className="auth-loading"><span>✦</span></div>;
  }

  // Not signed in → show login screen (unless guest mode chosen)
  if (!user && !isGuest) {
    return (
      <LoginScreen
        onGoogle={signInWithGoogle}
        onFacebook={signInWithFacebook}
        onGithub={signInWithGithub}
        onGuest={() => setIsGuest(true)}
      />
    );
  }

  // New user → show onboarding
  if (needsOnboarding) {
    return <OnboardingFlow userName={userName} onComplete={completeOnboarding} />;
  }

  if (showEventBrief) {
    return <EventBriefFlow onStart={startEventEdit} onCancel={() => setShowEventBrief(false)} />;
  }

  // ── Unified chat-first layout ────────────────────────────────────────────────
  return (
    <>
      {showWarning && (
        <SessionWarning countdown={countdown} onStay={staySignedIn} onLeave={signOut} />
      )}
      {showHistory && (
        <ChatHistory
          {...history}
          onClose={() => setShowHistory(false)}
        />
      )}

      <div className="app-chat">
        <header className="chat-header">
          <MiraDot state={state} mood={mood} audioActive={!textMode && connected} />
          <span className="chat-title">Mira</span>
          <div className="chat-header-right">
            {/* Cart icon */}
            <button className="cart-icon-btn" onClick={() => setShowCart(true)} title={`Cart (${cartItems.length})`}>
              🛒
              {cartItems.length > 0 && (
                <span className="cart-icon-badge">{cartItems.length}</span>
              )}
            </button>
            {savedProducts.length > 0 && (
              <button
                className="mtc-btn"
                onClick={() => setShowSaved((v) => !v)}
                title={showSaved ? "Hide saved" : `Saved items (${savedProducts.length})`}
              >
                💜{savedProducts.length > 0 && <span style={{ fontSize: ".75rem" }}>{savedProducts.length}</span>}
              </button>
            )}
            {user && (
              <button className="mtc-btn" onClick={() => setShowHistory(true)} title="Chat history">
                🕐
              </button>
            )}
            {user ? (
              <UserMenu userName={userName} userEmail={user?.email}
                userAvatar={userAvatar} onSignOut={signOut}
                onDeleteAccount={() => setShowDelete(true)} />
            ) : (
              <button className="guest-signin-btn" onClick={() => setIsGuest(false)}>Sign in</button>
            )}
          </div>
        </header>

        {/* Location bar — always visible below header */}
        <PinChip
          pinCode={effectivePrefs?.pin_code || null}
          onSave={(pin) => {
            if (user) updatePrefs({ pin_code: pin });
            else setGuestPinCode(pin);
            updateLocation(pin);
          }}
        />

        {/* Saved products shelf — collapsible */}
        {showSaved && savedProducts.length > 0 && (
          <div className="shelf saved-shelf" style={{ flexShrink: 0, borderBottom: "1px solid var(--surface-2)", padding: ".75rem 1rem" }}>
            <p className="shelf-title">💜 Your saved items</p>
            <div className="grid">
              {savedProducts.map((p) => (
                <ProductCard key={p.id} product={p} loved onLove={wouldBuy} onBuy={buyClick} onSelect={setQuickViewProduct} inCart={inCart(p.id)} onAddToCart={addToCart} />
              ))}
            </div>
          </div>
        )}

        <div className="chat-thread" ref={threadRef}>
          {/* Look deck at the top of thread */}
          {looks.length > 0 && (
            <LookDeck looks={looks} loved={loved} onLove={wouldBuy} onBuy={buyClick} onSaveLook={saveLook} onAddAllToCart={addAllToCart} />
          )}

          {messages.length === 0 && !connected && (
            <ChatWelcome onEventBrief={() => setShowEventBrief(true)} textMode={textMode} />
          )}
          {messages.map((msg) =>
            msg.role === "event"
              ? <EventDivider key={msg.id} text={msg.text} />
              : <MessageBubble key={msg.id} msg={msg} loved={loved} onLove={wouldBuy} onBuy={buyClick} highlightedId={highlightedId} onSelect={setQuickViewProduct} inCart={inCart} onAddToCart={addToCart} />
          )}
          {state === "thinking" && <ThinkingBubble />}

          {/* Show more products button */}
          {canShowMore && connected && (
            <div style={{ textAlign: "center", padding: ".5rem 0" }}>
              <button className="show-more-btn" onClick={showMore}>Show 3 more →</button>
            </div>
          )}
        </div>

        <div className="chat-input-bar">
          {!connected ? (
            <div className="start-row">
              <ModeToggle textMode={textMode} connected={connected} quality={quality}
                onVoice={switchToVoice} onText={switchToSilent} />
              <button className="chat-start-btn" onClick={start}>
                {textMode ? "Start chatting →" : "Start talking →"}
              </button>
            </div>
          ) : textMode ? (
            <TextInputRow onSend={sendText} onStop={stop} onSwitchVoice={switchToVoice} />
          ) : (
            <VoiceActiveBar level={getLevel} onStop={stop} captions={captions} onSwitchText={switchToSilent} />
          )}
          {error && <ConnectionError retryCount={retryCount} onRetry={retry} />}
        </div>
      </div>

      {networkToast && (
        <NetworkToast
          message={networkToast.message}
          action={networkToast.action}
          onAction={networkToast.onAction}
          onDismiss={() => setNetworkToast(null)}
        />
      )}
      {quickViewProduct && (
        <ProductQuickView
          product={quickViewProduct}
          loved={loved.has(quickViewProduct.id)}
          inCart={inCart(quickViewProduct.id)}
          onLove={wouldBuy}
          onBuy={buyClick}
          onAddToCart={addToCart}
          onClose={() => setQuickViewProduct(null)}
        />
      )}
      {showCart && (
        <CartPanel
          items={cartItems}
          onRemove={removeFromCart}
          onClear={clearCart}
          onClose={() => setShowCart(false)}
        />
      )}
      {showPrivacy && <PrivacyPolicy onClose={() => setShowPrivacy(false)} />}
      {showDeleteModal && (
        <DeleteAccountModal
          onConfirm={deleteAccount}
          onCancel={() => setShowDelete(false)}
        />
      )}

      <footer className="app-footer" style={{ textAlign: "center", padding: ".5rem", fontSize: ".75rem", color: "var(--ink-3)" }}>
        state: <code>{state}</code> · mood: <code>{mood}</code> ·{" "}
        {connected ? (textMode ? "text" : "live") : "offline"} ·{" "}
        <button className="privacy-link" onClick={() => setShowPrivacy(true)}>Privacy</button>
      </footer>
    </>
  );
}
