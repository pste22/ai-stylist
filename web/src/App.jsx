import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import ProductCard from "./ProductCard.jsx";
import LoginScreen from "./LoginScreen.jsx";
import { useMiraVoice } from "./useMiraVoice.js";
import { useAuth } from "./useAuth.js";
import { useOnboarding } from "./useOnboarding.js";
import { useIdleTimeout } from "./useIdleTimeout.js";
import { useChatHistory } from "./useChatHistory.js";
import { useCart } from "./useCart.js";
import { usePhotoProfile } from "./usePhotoProfile.js";
import { saveTryOn, getTryOn, listTryOns, photoSignature } from "./tryOnDB.js";
import { track, identify } from "./analytics.js";
import { useNetworkMode, checkNetworkNow } from "./useNetworkMode.js";
import { ReasonPicker } from "./ReasonPicker.jsx";
import { usePlatformPulse } from "./usePlatformPulse.js";
import PlatformPulse from "./PlatformPulse.jsx";
import ChatSketchWallpaper from "./ChatSketchWallpaper.jsx";
import { hdProductImageUrl, isProductPhotoUrl } from "./imageUrl.js";
import { shopLabel, trackedAffiliateUrl } from "./retailer.js";
import { BrandsStrip, BrandsSheet, useBrandOptions } from "./BrandsDiscovery.jsx";
import LookProgressStrip, { FinishLookNudge } from "./LookProgressStrip.jsx";
import {
  assignProductToSlot,
  isLookIncomplete,
  isStripHiddenThisSession,
  loadLookProgress,
  removeProductFromSlots,
  shouldShowFinishNudge,
} from "./lookProgress.js";

const CatalogFilters = lazy(() => import("./CatalogFilters.jsx"));
const ForBrands = lazy(() => import("./ForBrands.jsx"));

// Modal / rare flows — keep off the critical path so first paint stays light.
const OnboardingFlow = lazy(() => import("./OnboardingFlow.jsx"));
const EventBriefFlow = lazy(() => import("./EventBriefFlow.jsx"));
const ChatHistory = lazy(() => import("./ChatHistory.jsx"));
const PrivacyPolicy = lazy(() => import("./PrivacyPolicy.jsx"));
const ProductQuickView = lazy(() => import("./ProductQuickView.jsx"));
const CartPanel = lazy(() => import("./CartPanel.jsx"));
const FittingRoom = lazy(() => import("./FittingRoom.jsx"));
const OutfitBuilder = lazy(() => import("./OutfitBuilder.jsx"));
const TryOnModal = lazy(() => import("./TryOnModal.jsx"));
const SessionWatcherPanel = lazy(() =>
  import("./SessionWatcherPanel.jsx").then((m) => ({ default: m.SessionWatcherPanel }))
);

// Activate in dev mode or when ?debug appears in the URL
const DEBUG_MODE = import.meta.env.DEV || new URLSearchParams(location.search).has("debug");
if (DEBUG_MODE) {
  import("./SessionWatcher.js").then((m) => m.install());
}

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

// Unified product display — grid for browse, snap-rail for chat.
const PRODUCTS_PER_TURN = 3;
function ProductGrid({ products, loved, onLove, onBuy, highlightedId, onSelect, inCart, onAddToCart, showAll, label, onShopAll, userSize, onTryOn, rail }) {
  if (!products?.length) return null;
  const shown = showAll ? products : products.slice(0, PRODUCTS_PER_TURN);
  return (
    <div className={`product-grid-wrap${rail ? " product-grid-wrap--rail" : ""}`}>
      {label && <div className="product-grid-label"><span>{label}</span></div>}
      <div className={rail ? "product-rail" : "product-grid"}>
        {shown.map((p) => (
          <ProductCard key={p.id} product={p} loved={loved.has(p.id)}
            onLove={onLove} onBuy={onBuy} highlight={p.id === highlightedId} onSelect={onSelect}
            inCart={inCart?.(p.id)} onAddToCart={onAddToCart} userSize={userSize} onTryOn={onTryOn} />
        ))}
      </div>
      {onShopAll && (
        <div className="product-grid-shop-all-row">
          <button className="product-grid-shop-all" onClick={() => onShopAll(products)}>
            🛒 Shop all {products.length} items
          </button>
        </div>
      )}
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
function BubbleProducts({ products, loved, onLove, onBuy, onSelect }) {
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
          onSelect={onSelect}
          compact
        />
      ))}
    </div>
  );
}

function pickRelatedProducts(product, pools) {
  if (!product?.id) return [];
  const seen = new Set([product.id]);
  const out = [];
  for (const pool of pools) {
    if (!Array.isArray(pool)) continue;
    for (const p of pool) {
      if (!p?.id || seen.has(p.id)) continue;
      if (product.category && p.category && p.category !== product.category) continue;
      seen.add(p.id);
      out.push(p);
      if (out.length >= 8) return out;
    }
  }
  return out;
}

// ─── Slot label config ────────────────────────────────────────────────────────
const SLOT_META = {
  outfit:      { label: "Outfit",      emoji: "👗" },
  shoes:       { label: "Shoes",       emoji: "👠" },
  bag:         { label: "Bag",         emoji: "👜" },
  accessories: { label: "Accessories", emoji: "✨" },
};

function LookSlot({ slotKey, product, loved, onLove, onBuy, onAddToCart, inCart }) {
  if (!product) return null;
  const { label, emoji } = SLOT_META[slotKey] || { label: slotKey, emoji: "🛍️" };
  const isLoved = loved?.has(product.id);
  return (
    <div className="look-slot">
      <span className="look-slot-label">{emoji} {label}</span>
      <div className="look-slot-card" onClick={() => onBuy?.(product)}>
        <img
          className="look-slot-img"
          src={hdProductImageUrl(product.image_url, { longest: 1000 }) || product.image_url}
          alt={product.name}
          loading="lazy"
          onError={(e) => { e.target.style.display = "none"; }}
        />
        <div className="look-slot-info">
          <p className="look-slot-name">{product.name}</p>
          <p className="look-slot-price">₹{Number(product.price || 0).toLocaleString("en-IN")}</p>
        </div>
        <div className="look-slot-actions">
          <button
            className={`look-slot-love${isLoved ? " loved" : ""}`}
            onClick={(e) => { e.stopPropagation(); onLove?.(product); }}
            aria-label={isLoved ? "Saved" : "Save"}
          >{isLoved ? "♥" : "♡"}</button>
          <button
            className={`look-slot-cart${inCart?.(product.id) ? " in-cart" : ""}`}
            onClick={(e) => { e.stopPropagation(); if (!inCart?.(product.id)) onAddToCart?.(product); }}
            aria-label={inCart?.(product.id) ? "In cart" : "Add to cart"}
          >{inCart?.(product.id) ? "🛒✓" : "🛒"}</button>
        </div>
      </div>
    </div>
  );
}

function LookCard({ look, loved, onLove, onBuy, onSaveLook, onAddAllToCart, onAddToCart, inCart }) {
  const [expanded, setExpanded] = useState(false);
  const slots = look.slots || {};
  const outfitItems = slots.outfit || look.items || [];
  const allItems = look.items || [];
  const allSaved = allItems.every((p) => loved?.has(p.id));
  const total = allItems.reduce((s, p) => s + (Number(p.price) || 0), 0);

  return (
    <article className="look-card-v2">
      {/* Header */}
      <div className="look-card-v2-head">
        <div>
          <h3 className="look-card-v2-name">{look.name}</h3>
          <p className="look-card-v2-rationale">{look.rationale}</p>
        </div>
        <div className="look-card-v2-price-block">
          <span className="look-card-v2-total">₹{total.toLocaleString("en-IN")}</span>
          <span className="look-card-v2-count">{allItems.length} pieces</span>
        </div>
      </div>

      {/* Outfit anchor — hero images */}
      <div className="look-outfit-row">
        {outfitItems.map((p) => (
          <div className="look-outfit-img-wrap" key={p.id} onClick={() => onBuy?.(p)}>
            <img
              className="look-outfit-img"
              src={p.image_url}
              alt={p.name}
              loading="lazy"
              onError={(e) => { e.target.style.display = "none"; }}
            />
            <span className="look-outfit-tag">{p.category}</span>
          </div>
        ))}
      </div>

      {/* Accessories strip */}
      <div className="look-accessories-strip">
        {["shoes", "bag", "accessories"].map((key) => {
          const p = slots[key];
          if (!p) return null;
          return (
            <div className="look-acc-thumb" key={key} onClick={() => onBuy?.(p)}>
              <img
                src={p.image_url}
                alt={p.name}
                loading="lazy"
                onError={(e) => { e.target.style.display = "none"; }}
              />
              <span className="look-acc-label">{SLOT_META[key]?.emoji} {SLOT_META[key]?.label}</span>
              <span className="look-acc-price">₹{Number(p.price || 0).toLocaleString("en-IN")}</span>
            </div>
          );
        })}
      </div>

      {/* Expandable detail slots */}
      <button className="look-expand-btn" onClick={() => setExpanded(v => !v)}>
        {expanded ? "▴ Less detail" : "▾ View all pieces"}
      </button>
      {expanded && (
        <div className="look-slots-list">
          {["outfit", "shoes", "bag", "accessories"].map((key) => {
            if (key === "outfit") {
              return outfitItems.map((p) => (
                <LookSlot key={p.id} slotKey="outfit" product={p}
                  loved={loved} onLove={onLove} onBuy={onBuy}
                  onAddToCart={onAddToCart} inCart={inCart} />
              ));
            }
            const p = slots[key];
            if (!p) return null;
            return (
              <LookSlot key={key} slotKey={key} product={p}
                loved={loved} onLove={onLove} onBuy={onBuy}
                onAddToCart={onAddToCart} inCart={inCart} />
            );
          })}
        </div>
      )}

      {/* Actions */}
      <div className="look-card-v2-actions">
        <button
          className={`look-save${allSaved ? " look-save--saved" : ""}`}
          onClick={() => !allSaved && onSaveLook?.(allItems)}
        >{allSaved ? "♥ Saved" : "♡ Save look"}</button>
        <button
          className="look-cart-btn"
          onClick={() => onAddAllToCart?.(allItems)}
        >🛒 Shop this look</button>
      </div>
    </article>
  );
}

function LookDeck({ looks, loved, onLove, onBuy, onSaveLook, onAddAllToCart, onAddToCart, inCart }) {
  if (!looks?.length) return null;
  return (
    <section className="look-deck" aria-label="Mira's complete look drafts">
      <div className="look-deck-heading">
        <p className="look-deck-eyebrow">✦ Mira Event Edit</p>
        <h2>Complete looks for your occasion</h2>
        <p className="look-deck-sub">Each look is head-to-toe — outfit, shoes, bag, and accessories.</p>
      </div>
      <div className="look-grid">
        {looks.map((look) => (
          <LookCard key={look.id} look={look} loved={loved}
            onLove={onLove} onBuy={onBuy} onSaveLook={onSaveLook}
            onAddAllToCart={onAddAllToCart} onAddToCart={onAddToCart} inCart={inCart} />
        ))}
      </div>
    </section>
  );
}

const CATEGORY_EMOJI = {
  dresses: "👗", tops: "👚", bottoms: "👖", outerwear: "🧥",
  shoes: "👟", bags: "👜", accessories: "✨", activewear: "🏃",
};

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
  const usePhoto = isProductPhotoUrl(product.image_url);

  return (
    <div className="fp-product">
      <div className="fp-img-wrap">
        {usePhoto
          ? <img className="fp-img" src={hdProductImageUrl(product.image_url, { longest: 1500 })} alt={product.name} loading="lazy" decoding="async" />
          : <div className="fp-cat-thumb" style={{ "--swatch": swatchColor(product.color) }}>
              <span className="fp-cat-emoji">{CATEGORY_EMOJI[product.category] || "🛍️"}</span>
            </div>
        }

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
            href={trackedAffiliateUrl(product)}
            target="_blank"
            rel="noopener noreferrer nofollow sponsored"
            onClick={() => onBuy?.(product)}
          >{shopLabel(product, { short: true })}</a>
        </div>
      </div>

      <div className="fp-details">
        <div className="fp-miras-pick">✦ Mira's edit</div>

        {reason && (
          <div className="fp-why">
            <p className="fp-why-label">✦ Why Mira chose this</p>
            <p className="fp-why-text">"{reason}"</p>
          </div>
        )}

        <a
          className="fp-cta"
          href={trackedAffiliateUrl(product)}
          target="_blank"
          rel="noopener noreferrer nofollow sponsored"
          onClick={() => onBuy?.(product)}
        >
          {shopLabel(product)}
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
                    canShowMore, onShowMore, products, looks, onSaveLook, highlightedId,
                    inCart, onAddToCart, onAddAllToCart }) {
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
            <LookDeck looks={looks} loved={loved} onLove={onLove} onBuy={onBuy} onSaveLook={onSaveLook}
              onAddAllToCart={onAddAllToCart} onAddToCart={onAddToCart} inCart={inCart} />
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


function YouMightLike({ data, onBuy, onLove, loved, onAddToCart, inCart, onDismiss, onSelect }) {
  if (!data?.items?.length) return null;
  return (
    <div className="yml-strip">
      <div className="yml-header">
        <span className="yml-title">✦ You might also like</span>
        <button className="yml-dismiss" onClick={onDismiss} aria-label="Dismiss">✕</button>
      </div>
      <div className="yml-scroll">
        {data.items.map(p => (
          <div key={p.id} className="yml-card" onClick={() => onSelect?.(p)}>
            <div className="yml-img-wrap">
              {p.image_url
                ? <img className="yml-img" src={p.image_url} alt={p.name} loading="lazy" />
                : <div className="yml-img yml-img--placeholder" />
              }
              <button
                className={`yml-heart${loved?.has(p.id) ? " is-loved" : ""}`}
                onClick={(e) => { e.stopPropagation(); onLove?.(p); }}
              >{loved?.has(p.id) ? "♥" : "♡"}</button>
            </div>
            <p className="yml-name">{p.name}</p>
            <div className="yml-footer">
              <span className="yml-price">₹{Number(p.price).toLocaleString("en-IN")}</span>
              <a className="yml-shop" href={trackedAffiliateUrl(p)} target="_blank" rel="noopener noreferrer nofollow sponsored" onClick={(e) => { e.stopPropagation(); onBuy?.(p); }}>{shopLabel(p, { short: true })}</a>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ShopTheLookStrip({ looks, onShopLook, onLove, loved, onAddToCart, inCart }) {
  if (!looks?.length) return null;
  return (
    <div className="stl-strip">
      <div className="stl-header">
        <span className="stl-title">✦ Shop the look</span>
      </div>
      <div className="stl-scroll">
        {looks.map((look, i) => {
          const items = look.items || [];
          const images = items.filter(p => p.image_url).slice(0, 4);
          const totalPrice = items.reduce((s, p) => s + (Number(p.price) || 0), 0);
          return (
            <div key={look.id || i} className="stl-card">
              <div className="stl-collage">
                {images.slice(0, 4).map((p, j) => (
                  <div key={p.id} className={`stl-collage-cell stl-cell-${j}`}>
                    <img src={p.image_url} alt={p.name} loading="lazy" className="stl-collage-img" />
                  </div>
                ))}
                {images.length === 0 && (
                  <div className="stl-collage-empty">
                    <span>👗</span>
                  </div>
                )}
              </div>
              <div className="stl-card-body">
                <p className="stl-occasion">{look.occasion || look.name || "Complete look"}</p>
                {totalPrice > 0 && (
                  <p className="stl-price">From ₹{totalPrice.toLocaleString("en-IN")}</p>
                )}
                <button className="stl-shop-btn" onClick={() => onShopLook(look)}>
                  Shop this look →
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TrendingStrip({ products, onBuy, onLove, loved, inCart, onAddToCart, onSelect }) {
  if (!products?.length) return null;
  return (
    <div className="trending-strip">
      <div className="trending-strip-header">
        <span className="trending-strip-title">✦ From Mira's edit</span>
      </div>
      <div className="trending-strip-scroll">
        {products.map(p => (
          <div key={p.id} className="trending-card" onClick={() => onSelect?.(p)}>
            <div className="trending-card-img-wrap">
              {p.image_url
                ? <img className="trending-card-img" src={p.image_url} alt={p.name} loading="lazy" />
                : <div className="trending-card-img trending-card-img--placeholder">{p.category}</div>
              }
              <button
                className={`trending-card-heart${loved?.has(p.id) ? " is-loved" : ""}`}
                onClick={(e) => { e.stopPropagation(); onLove?.(p); }}
              >{loved?.has(p.id) ? "♥" : "♡"}</button>
            </div>
            <p className="trending-card-name">{p.name}</p>
            <div className="trending-card-footer">
              <span className="trending-card-price">
                ₹{Number(p.price).toLocaleString("en-IN")}
              </span>
              <a
                className="trending-card-shop"
                href={trackedAffiliateUrl(p)}
                target="_blank"
                rel="noopener noreferrer nofollow sponsored"
                onClick={(e) => { e.stopPropagation(); onBuy?.(p); }}
              >{shopLabel(p, { short: true })}</a>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const OCCASION_CHIPS = [
  { emoji: "💍", label: "Wedding guest",    prompt: "I need an outfit for a wedding — suggest something elegant and appropriate." },
  { emoji: "🍷", label: "Date night",       prompt: "I have a date tonight — suggest something stylish and flattering." },
  { emoji: "☕", label: "Casual everyday",  prompt: "I want a comfortable but stylish everyday casual outfit." },
  { emoji: "💼", label: "Office look",      prompt: "Help me put together a polished office outfit for work." },
  { emoji: "🌅", label: "Beach holiday",    prompt: "I'm going on a beach holiday — what should I pack and wear?" },
  { emoji: "🎉", label: "Party / festival", prompt: "I'm going to a party or festival — help me find a fun, standout look." },
  { emoji: "🎓", label: "Graduation",       prompt: "I need an outfit for a graduation ceremony — something smart and celebratory." },
  { emoji: "🛍️", label: "Just browsing",   prompt: "Show me stylish picks for inspiration — I'm just browsing." },
];

const PRIMARY_OCCASIONS = OCCASION_CHIPS.slice(0, 3);

function ChatWelcome({ onOccasion, onEventBrief, textMode }) {
  const [showMore, setShowMore] = useState(false);
  const chips = showMore ? OCCASION_CHIPS : PRIMARY_OCCASIONS;
  return (
    <div className="hero-welcome hero-welcome--photo">
      <picture className="hero-welcome-media" aria-hidden="true">
        <source media="(max-width: 720px)" srcSet="/hero-home-sm.jpg" />
        <img
          className="hero-welcome-img"
          src="/hero-home.jpg"
          alt=""
          width={1600}
          height={900}
          loading="eager"
          decoding="async"
        />
      </picture>

      <div className="hero-content hero-content--over">
        <h1 className="hero-brand-mark" aria-label="Mira">MIRA</h1>
        <p className="hero-sub hero-sub--light">Tell Mira your occasion</p>

        <div className="occasion-chips occasion-chips--editorial">
          {chips.map(({ label, prompt }) => (
            <button
              key={label}
              className="occasion-chip occasion-chip--editorial"
              onClick={() => onOccasion(prompt)}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="hero-secondary-actions">
          {!showMore && (
            <button type="button" className="hero-more-occasions hero-more-occasions--light" onClick={() => setShowMore(true)}>
              More occasions
            </button>
          )}
          {onEventBrief && (
            <button type="button" className="hero-more-occasions hero-more-occasions--light" onClick={onEventBrief}>
              Plan an event
            </button>
          )}
        </div>

        <p className="hero-cta-hint hero-cta-hint--light">
          {textMode ? "or type below" : "or tap Start chatting"}
        </p>
      </div>
    </div>
  );
}

// ─── Message bubble — user or Mira, with inline product cards ────────────────
function MessageBubble({ msg, loved, onLove, onBuy, highlightedId, onSelect, inCart, onAddToCart,
                         reasonPickerProductId, onReasonDone, onAddAllToCart, userSize, onTryOn }) {
  const isMira = msg.role === "mira";
  const showPicker = isMira && reasonPickerProductId &&
    msg.products?.some(p => p.id === reasonPickerProductId);
  const pickerProduct = showPicker
    ? msg.products.find(p => p.id === reasonPickerProductId)
    : null;

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
            showAll={!!msg.label}
            label={msg.label}
            onShopAll={msg.label && onAddAllToCart ? (items) => { onAddAllToCart(items); } : null}
            userSize={userSize}
            onTryOn={onTryOn}
            rail
          />
        )}
        {pickerProduct && (
          <ReasonPicker product={pickerProduct} onDone={onReasonDone} />
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
function TextInputRow({ onSend, onStop, onSwitchVoice, onVisualSearch, onOutfitSearch, onOutfitUrl, vsLoading, outfitLoading, placeholder }) {
  const [draft, setDraft] = useState("");
  const [outfitPopover, setOutfitPopover] = useState(false);
  const [urlDraft, setUrlDraft] = useState("");
  const send = () => { if (draft.trim()) { onSend(draft.trim()); setDraft(""); } };

  const makeFileHandler = (cb) => (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => { cb(reader.result.split(",")[1], file.type); };
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  const submitOutfitUrl = () => {
    const url = urlDraft.trim();
    if (!url) return;
    onOutfitUrl?.(url);
    setUrlDraft("");
    setOutfitPopover(false);
  };

  return (
    <div className="text-input-row" style={{ position: "relative" }}>
      <button className="mode-switch-btn" onClick={onSwitchVoice} title="Switch to voice">🎙️</button>
      <input className="chat-input" value={draft} onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), send())}
        placeholder={placeholder || "Message Mira…"} autoFocus />
      <button className="send-btn" onClick={send} disabled={!draft.trim()}>Send</button>

      {/* Visual search — single item */}
      <input type="file" accept="image/*" id="vs-file-input" style={{ display: "none" }}
        disabled={vsLoading} onChange={makeFileHandler((b64, mime) => onVisualSearch?.(b64, mime))} />
      <label htmlFor="vs-file-input"
        className={`chat-camera-btn${vsLoading ? " vs-loading-btn" : ""}`}
        title={vsLoading ? "Analysing…" : "Search by photo"}
        style={vsLoading ? { pointerEvents: "none", opacity: 0.5 } : {}}>
        {vsLoading
          ? <span className="vs-loading-spinner" style={{ width: 14, height: 14 }} />
          : <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
              <circle cx="12" cy="13" r="4"/>
            </svg>
        }
      </label>

      {/* Outfit anatomy — URL paste or photo upload */}
      {outfitPopover && !outfitLoading && (
        <div className="outfit-url-popover">
          <p className="outfit-url-label">Paste an Instagram or Pinterest link</p>
          <div className="outfit-url-row">
            <input
              className="outfit-url-input"
              value={urlDraft}
              onChange={(e) => setUrlDraft(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submitOutfitUrl()}
              placeholder="https://www.instagram.com/p/..."
              autoFocus
            />
            <button className="outfit-url-go" onClick={submitOutfitUrl} disabled={!urlDraft.trim()}>Go</button>
          </div>
          <div className="outfit-url-divider"><span>or</span></div>
          <input type="file" accept="image/*" id="outfit-file-input" style={{ display: "none" }}
            onChange={makeFileHandler((b64, mime) => { onOutfitSearch?.(b64, mime); setOutfitPopover(false); })} />
          <label htmlFor="outfit-file-input" className="outfit-upload-alt">
            📷 Upload a screenshot instead
          </label>
          <button className="outfit-url-cancel" onClick={() => setOutfitPopover(false)}>Cancel</button>
        </div>
      )}

      <button
        className={`chat-camera-btn${outfitLoading ? " vs-loading-btn" : ""}`}
        title={outfitLoading ? "Analysing outfit…" : "Shop this outfit"}
        style={outfitLoading ? { pointerEvents: "none", opacity: 0.5 } : {}}
        onClick={() => !outfitLoading && setOutfitPopover(p => !p)}
      >
        {outfitLoading
          ? <span className="vs-loading-spinner" style={{ width: 14, height: 14 }} />
          : "👗"
        }
      </button>

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
    authError, clearAuthError,
    signInWithGoogle, signInWithFacebook, signInWithGithub, signOut, deleteAccount,
  } = useAuth();

  const { needsOnboarding, prefs, completeOnboarding, updatePrefs } = useOnboarding(userId);
  const { showWarning, countdown, staySignedIn } = useIdleTimeout({ onSignOut: signOut, enabled: !!user });
  const history = useChatHistory(userId);

  const { isSlow, isRecovered, quality }  = useNetworkMode();
  const autoSwitchedRef                   = useRef(false);
  const threadRef                         = useRef(null);
  const msgsEndRef                        = useRef(null); // sentinel above show-more button
  const [isGuest, setIsGuest]             = useState(false);
  // Leaving guest mode via a "Sign in" button should land on the auth sheet,
  // not the marketing hero with the sheet closed.
  const [wantsSignIn, setWantsSignIn]     = useState(false);
  const [textMode, setTextMode]           = useState(true); // default silent chat — voice is opt-in
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
  const [activeFilter, setActiveFilter]   = useState("all");
  const [filterResults, setFilterResults] = useState(null); // { products, total } from faceted browse
  // Defer discovery shelves so the occasion CTA paints first.
  const [showDiscovery, setShowDiscovery] = useState(false);
  const [brandFocus, setBrandFocus] = useState(null); // apply Brand filter from discovery strip/sheet
  const [brandsSheetOpen, setBrandsSheetOpen] = useState(false);
  const brandOptions = useBrandOptions();
  const [lookProgress, setLookProgress] = useState(() => loadLookProgress());
  const [lookStripHidden, setLookStripHidden] = useState(() => isStripHiddenThisSession());
  const [finishNudgeVisible, setFinishNudgeVisible] = useState(false);
  const [uiMode, setUiMode] = useState(() => {
    try { return localStorage.getItem("mira.uiMode") || "atelier"; } catch { return "atelier"; }
  });

  useEffect(() => {
    document.documentElement.dataset.mira = uiMode === "classic" ? "classic" : "atelier";
    try { localStorage.setItem("mira.uiMode", uiMode); } catch { /* */ }
  }, [uiMode]);

  useEffect(() => {
    // Soft return nudge once/day when look is incomplete
    setFinishNudgeVisible(shouldShowFinishNudge(lookProgress));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const addToLookProgress = (product) => {
    if (!product) return;
    setLookProgress((prev) => assignProductToSlot(prev, product));
    setLookStripHidden(false);
  };
  const pendingOccasionRef = useRef(null);
  const pendingOccasionStartRef = useRef(false);
  const pendingTryOnStartRef = useRef(false);
  const pendingAskRef = useRef(null); // { product, promptKey } after Quick View Ask Mira
  const [vsResults, setVsResults]         = useState([]);
  const [vsQuery, setVsQuery]             = useState("");
  const [vsCatalogNote, setVsCatalogNote] = useState(null);
  const { items: cartItems, addItem: addToCart, addItems: addAllToCart, removeItem: removeFromCart, clearCart, inCart } = useCart();
  const { photo: savedPhoto, savePhoto, clearPhoto } = usePhotoProfile();
  // Sizes set inline (Size Advisor) — persisted for logged-in users, in-memory for guests.
  const [sizeOverride, setSizeOverride] = useState({});
  const effectivePrefs = useMemo(() => {
    const base = user ? (prefs || {}) : { ...(prefs || {}), pin_code: guestPinCode };
    return { ...base, ...sizeOverride };
  }, [user, prefs, guestPinCode, sizeOverride]);
  const setUserSize = (field, value) => {
    setSizeOverride((o) => ({ ...o, [field]: value }));
    if (user) updatePrefs({ [field]: value });
  };

  const [reasonPickerProductId, setReasonPickerProductId] = useState(null);
  const [tryOnProduct, setTryOnProduct] = useState(null);
  const [savedTryOn, setSavedTryOn] = useState(null);   // this product's stored try-on (IndexedDB)
  const [showFittingRoom, setShowFittingRoom] = useState(false);
  const [fittingRoomCount, setFittingRoomCount] = useState(0);
  const [signInPrompt, setSignInPrompt] = useState(false);   // guest tapped a paid feature
  const [showForBrands, setShowForBrands] = useState(false);
  const pulseBlocked = !!(quickViewProduct || tryOnProduct || showCart || showFittingRoom || signInPrompt || showForBrands);
  const {
    visible: pulseVisible,
    step: pulseStep,
    recordAction: recordPulseAction,
    dismiss: dismissPulse,
    submitHelpful,
    submitWhy,
    submitMiss,
  } = usePlatformPulse({ enabled: true });
  const youMsgCountRef = useRef(0);

  const {
    connected, state, mood, captions, messages,
    products, looks, editorialLooks, trendingProducts, youMightLike, setYouMightLike,
    savedProducts, loved, highlightedId, error, retryCount,
    canShowMore, setCanShowMore,
    productTimeline, switchAudio, updateLocation, addSystemEvent, clearHistory,
    start, stop, retry, sendText, wouldBuy, getLevel, buyClick, showMore, browseCategory, sendVisualSearch, vsLoading, setVsLoading,
    sendLikeReason, quickReplies, dismissQuickReplies,
    sendOutfitImage, sendOutfitUrl, sendOutfitAssembled, addAssembledLookToChat, askAboutProduct,
    outfitAnatomy, setOutfitAnatomy, outfitLoading, outfitError, setOutfitError,
    sendTryOn, tryOnResult, tryOnLoading, tryOnError, clearTryOn, tryOnLookItems,
    sendTryOnVideo, tryOnVideo, tryOnVideoLoadingKind, tryOnVideoError,
  } = useMiraVoice({
    userId, userName, userEmail: user?.email, userPrefs: effectivePrefs, eventBrief, textMode, onAddToCart: addToCart,
    onVisualSearchResults: (items, query, note) => { setVsResults(items); setVsQuery(query); setVsCatalogNote(note || null); setVsLoading(false); },
  });

  const relatedProducts = useMemo(() => {
    if (!quickViewProduct) return [];
    const fromMessages = messages.flatMap((m) => m.products || []);
    return pickRelatedProducts(quickViewProduct, [
      filterResults?.products,
      products,
      vsResults,
      trendingProducts,
      savedProducts,
      fromMessages,
    ]);
  }, [quickViewProduct, filterResults, products, vsResults, trendingProducts, savedProducts, messages]);

  // Auto-scroll thread to bottom on new messages/products
  useEffect(() => {
    const el = threadRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  // Count user chat turns toward the occasional platform pulse
  useEffect(() => {
    const youCount = messages.filter((m) => m.role === "you").length;
    if (youCount > youMsgCountRef.current) {
      const gained = youCount - youMsgCountRef.current;
      youMsgCountRef.current = youCount;
      for (let i = 0; i < gained; i++) recordPulseAction("chat");
    }
  }, [messages, recordPulseAction]);

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

  // Silent chat entry: always surface the bubble; auto-start WS in text mode if needed.
  const sendChat = (text) => {
    const trimmed = (text || "").trim();
    if (!trimmed) return;
    // Catalog filter panel was hiding the thread — close it so chat is visible
    if (filterResults) {
      setFilterResults(null);
      setActiveFilter("all");
    }
    if (!connected) {
      sendText(trimmed); // queues + shows bubble (pendingTextRef in useMiraVoice)
      if (!textMode) {
        // Wait for textMode flip so start() opens with text_mode: true
        pendingOccasionStartRef.current = true;
        setTextMode(true);
      } else {
        start(); // already text mode — boot now; queued text becomes initial_request
      }
      return;
    }
    if (!textMode) setTextMode(true);
    sendText(trimmed);
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

  // Fire a deferred occasion text once the session connects
  useEffect(() => {
    if (connected && pendingOccasionRef.current) {
      sendText(pendingOccasionRef.current);
      pendingOccasionRef.current = null;
    }
  }, [connected, sendText]);

  // Start session AFTER textMode has been set to true (occasion chip flow).
  // Can't call start() and setTextMode(true) in the same handler because start()
  // is memoized with the old textMode closure — this useEffect sees the updated value.
  // We pass the pending text as initial_request so Mira skips the greeting.
  useEffect(() => {
    if (pendingOccasionStartRef.current && !connected) {
      pendingOccasionStartRef.current = false;
      const initialText = pendingOccasionRef.current;
      pendingOccasionRef.current = null; // clear so the connected useEffect doesn't double-send
      start(initialText);
    }
  }, [textMode, connected, start]);

  // Start a (text-mode) session for try-on once textMode flips, so sendTryOn works.
  useEffect(() => {
    if (pendingTryOnStartRef.current && !connected) {
      pendingTryOnStartRef.current = false;
      start();
    }
  }, [textMode, connected, start]);

  // Flush deferred Ask Mira once the websocket is up (UI already injected).
  useEffect(() => {
    if (!connected || !pendingAskRef.current) return;
    const { product, promptKey } = pendingAskRef.current;
    pendingAskRef.current = null;
    askAboutProduct(product, promptKey, { inject: false });
  }, [connected, askAboutProduct]);

  // Open the try-on modal for a product; ensure a session is running so the
  // photo upload can reach the server (text mode → no mic popup).
  const openTryOn = (product) => {
    recordPulseAction("try_on");
    // Gate the paid try-on behind sign-in (guest video/image gen is a cost vector).
    if (!user) {
      setSignInPrompt(true);
      track("signin_prompt_shown", { from: "try_on", product_id: product?.id });
      return;
    }
    track("try_on_opened", { product_id: product?.id, category: product?.category });
    clearTryOn();
    setTryOnProduct(product);
    setShowFittingRoom(false);
    // Restore a previously saved try-on for this product (instant, free).
    setSavedTryOn(null);
    getTryOn(product.id).then((rec) => { if (rec) setSavedTryOn(rec); });
    if (!connected) {
      if (!textMode) { pendingTryOnStartRef.current = true; setTextMode(true); }
      else start();
    }
  };

  // Persist a try-on to the Fitting Room (IndexedDB) as results/videos arrive.
  useEffect(() => {
    if (!tryOnProduct) return;
    const r = tryOnResult && tryOnResult.productId === tryOnProduct.id ? tryOnResult : null;
    const v = tryOnVideo && tryOnVideo.productId === tryOnProduct.id ? tryOnVideo : null;
    const hasViews = r && Object.keys(r.views || {}).length > 0;
    const hasClips = v && Object.keys(v.clips || {}).length > 0;
    if (!hasViews && !hasClips) return;
    if (hasViews) addToLookProgress(tryOnProduct);
    const p = tryOnProduct;
    saveTryOn({
      productId: p.id,
      product: {
        id: p.id, name: p.name, price: p.price, currency: p.currency,
        image_url: p.image_url, category: p.category, affiliate_url: p.affiliate_url,
      },
      views: { ...(savedTryOn?.views || {}), ...(r?.views || {}) },
      clips: { ...(savedTryOn?.clips || {}), ...(v?.clips || {}) },
      stills: { ...(savedTryOn?.stills || {}), ...(v?.stills || {}) },
      lookItems: tryOnLookItems.length ? tryOnLookItems : (savedTryOn?.lookItems || []),
      photoSig: photoSignature(savedPhoto?.image),
    }).then(() => setFittingRoomCount((c) => (savedTryOn ? c : c + 1)));
  }, [tryOnResult, tryOnVideo, tryOnProduct, tryOnLookItems]); // eslint-disable-line react-hooks/exhaustive-deps

  // Whether the saved try-on was made with a now-replaced profile photo.
  const savedTryOnStale = !!(
    savedTryOn && savedPhoto?.image && savedTryOn.photoSig &&
    savedTryOn.photoSig !== photoSignature(savedPhoto.image)
  );

  // Fitting Room badge count on mount.
  useEffect(() => { listTryOns().then((r) => setFittingRoomCount(r.length)); }, []);

  useEffect(() => {
    let idleId;
    let timeoutId;
    const reveal = () => setShowDiscovery(true);
    if (typeof window !== "undefined" && "requestIdleCallback" in window) {
      idleId = requestIdleCallback(reveal, { timeout: 1500 });
    } else {
      timeoutId = setTimeout(reveal, 400);
    }
    return () => {
      if (idleId != null && "cancelIdleCallback" in window) cancelIdleCallback(idleId);
      if (timeoutId != null) clearTimeout(timeoutId);
    };
  }, []);

  // Analytics: identify the signed-in user so events tie to them.
  useEffect(() => { if (userId) identify(userId, { name: userName }); }, [userId, userName]);

  const startEventEdit = (brief) => {
    setEventBrief(brief);
    setTextMode(true);
    setShowEventBrief(false);
    setStartRequested(true);
  };

  const handleLove = (product) => {
    const wasLoved = loved.has(product.id);
    wouldBuy(product);
    if (!wasLoved) recordPulseAction("save");
    if (!wasLoved) {
      addToLookProgress(product);
      // Always clear previous picker first so no two pickers are visible at once,
      // then set the new one in the next tick so React re-mounts it fresh.
      setReasonPickerProductId(null);
      setTimeout(() => setReasonPickerProductId(product.id), 0);
    } else {
      // Unliked — dismiss picker
      setReasonPickerProductId(null);
    }
  };

  const handleReasonDone = (reasons) => {
    const product = products.find(p => p.id === reasonPickerProductId);
    setReasonPickerProductId(null);
    if (product) sendLikeReason(product, reasons);
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
        onGuest={() => { setWantsSignIn(false); setIsGuest(true); }}
        autoOpen={wantsSignIn}
        authError={authError}
        onDismissError={clearAuthError}
      />
    );
  }

  // New user → show onboarding
  if (needsOnboarding) {
    return (
      <Suspense fallback={<div className="auth-loading"><span>✦</span></div>}>
        <OnboardingFlow userName={userName} onComplete={completeOnboarding} />
      </Suspense>
    );
  }

  if (showEventBrief) {
    return (
      <Suspense fallback={<div className="auth-loading"><span>✦</span></div>}>
        <EventBriefFlow onStart={startEventEdit} onCancel={() => setShowEventBrief(false)} />
      </Suspense>
    );
  }

  // ── Unified chat-first layout ────────────────────────────────────────────────
  return (
    <>
      {showWarning && (
        <SessionWarning countdown={countdown} onStay={staySignedIn} onLeave={signOut} />
      )}
      {showHistory && (
        <Suspense fallback={null}>
          <ChatHistory
            {...history}
            onClose={() => setShowHistory(false)}
          />
        </Suspense>
      )}

      <div className="app-chat">
        <header className="chat-header">
          <MiraDot state={state} mood={mood} audioActive={!textMode && connected} />
          <span className="chat-title">Mira</span>
          <div className="chat-header-right">
            <button
              type="button"
              className="ui-mode-toggle"
              title="Preview Premium Atelier vs classic UI — easy to flip back"
              onClick={() => setUiMode((m) => (m === "atelier" ? "classic" : "atelier"))}
            >
              {uiMode === "atelier" ? "Atelier" : "Classic"}
            </button>
            {/* Fitting Room — past try-ons ("seen on me") */}
            {fittingRoomCount > 0 && (
              <button className="cart-icon-btn" onClick={() => setShowFittingRoom(true)} title={`Fitting Room (${fittingRoomCount})`}>
                🪞
                <span className="cart-icon-badge">{fittingRoomCount}</span>
              </button>
            )}
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
              <button className="guest-signin-btn"
                onClick={() => { setWantsSignIn(true); setIsGuest(false); }}>Sign in</button>
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
                <ProductCard key={p.id} product={p} loved onLove={wouldBuy} onBuy={buyClick} onSelect={setQuickViewProduct} inCart={inCart(p.id)} onAddToCart={addToCart} onTryOn={openTryOn} />
              ))}
            </div>
          </div>
        )}

        <Suspense fallback={<div className="filter-bar" />}>
          <CatalogFilters
            category={activeFilter}
            onCategory={setActiveFilter}
            brandFocus={brandFocus}
            onBrandFocusConsumed={() => setBrandFocus(null)}
            onBrowseBrands={() => setBrandsSheetOpen(true)}
            calm={uiMode === "atelier"}
            onResults={(data) => {
              if (!data) { setFilterResults(null); return; }
              setFilterResults({
                products: data.products || [],
                total: data.total ?? (data.products || []).length,
                summary: data.summary || null,
                showMore: !!data.show_more,
                reachedEnd: !!data.reachedEnd,
                onLoadMore: data.onLoadMore || null,
              });
              // Jump only on a fresh filter (not when appending pages). Scroll the
              // panel itself into view: the thread sits below the filter bar, so
              // scrolling the thread to its top can still leave the results off-screen.
              if (!data.append) {
                requestAnimationFrame(() => {
                  threadRef.current?.scrollTo?.({ top: 0, behavior: "smooth" });
                  document
                    .getElementById("cf-results-panel")
                    ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
                });
              }
            }}
          />
        </Suspense>

        <div className="chat-canvas">
          <ChatSketchWallpaper />
          <div className="chat-thread" ref={threadRef}>
          {finishNudgeVisible && isLookIncomplete(lookProgress) && (
            <FinishLookNudge
              state={lookProgress}
              onFinish={() => {
                setFinishNudgeVisible(false);
                sendChat("Help me finish my look — suggest what's still missing");
              }}
              onDismiss={() => setFinishNudgeVisible(false)}
            />
          )}

          {filterResults && (
            <div className="cf-results" id="cf-results-panel">
              <div className="cf-results-head">
                <div>
                  <p className="cf-results-title">
                    Showing {filterResults.products.length.toLocaleString("en-IN")}
                    {filterResults.total != null ? ` of ${filterResults.total.toLocaleString("en-IN")}` : ""} matching items
                  </p>
                  {filterResults.summary && (
                    <p className="cf-results-summary">{filterResults.summary}</p>
                  )}
                </div>
                <button
                  type="button"
                  className="cf-results-close"
                  onClick={() => { setFilterResults(null); setActiveFilter("all"); }}
                >✕</button>
              </div>
              {filterResults.products.length > 0 ? (
                <>
                  <ProductGrid
                    products={filterResults.products}
                    loved={loved}
                    onLove={handleLove}
                    onBuy={buyClick}
                    onSelect={setQuickViewProduct}
                    inCart={inCart}
                    onAddToCart={addToCart}
                    showAll
                    userSize={effectivePrefs?.top_size || effectivePrefs?.bottom_size || null}
                    onTryOn={openTryOn}
                  />
                  {filterResults.showMore && filterResults.onLoadMore && (
                    <div className="cf-end-actions">
                      <button
                        type="button"
                        className="show-more-btn"
                        onClick={() => filterResults.onLoadMore()}
                      >
                        Show more →
                      </button>
                    </div>
                  )}
                  {filterResults.reachedEnd && (
                    <p className="cf-end-note" role="status">
                      You’ve reached the end — no more products to show.
                    </p>
                  )}
                </>
              ) : (
                <p className="cf-results-empty">No items match these filters. Clear one filter and try again.</p>
              )}
            </div>
          )}

          {/* When filters are active, hide unfiltered discovery so results aren't ambiguous */}
          {!filterResults && (
            <>
          {/* Visual search — loading / results / empty */}
          {vsLoading && (
            <div className="vs-loading">
              <span className="vs-loading-spinner" />
              <span>Analysing your photo…</span>
            </div>
          )}
          {!vsLoading && vsResults.length > 0 && (
            <div className="vs-results">
              <div className="vs-results-head">
                <p className="vs-results-title">🔍 {vsQuery || "Similar to your photo"}</p>
                <button className="vs-results-close" onClick={() => { setVsResults([]); setVsQuery(""); setVsCatalogNote(null); }}>✕</button>
              </div>
              {vsCatalogNote && (
                <div className="vs-catalog-note">ℹ️ {vsCatalogNote}</div>
              )}
              <ProductGrid products={vsResults} loved={loved} onLove={wouldBuy} onBuy={buyClick}
                onSelect={setQuickViewProduct} inCart={inCart} onAddToCart={addToCart} onTryOn={openTryOn} />
            </div>
          )}

          {/* Look deck at the top of thread */}
          {looks.length > 0 && (
            <LookDeck looks={looks} loved={loved} onLove={wouldBuy} onBuy={buyClick} onSaveLook={saveLook}
              onAddAllToCart={(items) => { addAllToCart(items); setShowCart(true); }}
              onAddToCart={addToCart} inCart={inCart} />
          )}

          {messages.length === 0 && (
            <ChatWelcome
              onEventBrief={() => setShowEventBrief(true)}
              onOccasion={(prompt) => {
                if (!connected) {
                  if (!textMode) {
                    // Force text mode so no mic popup blocks the experience.
                    // The useEffect above calls start(prompt) once textMode updates.
                    pendingOccasionRef.current = prompt;
                    pendingOccasionStartRef.current = true;
                    setTextMode(true);
                  } else {
                    // Already text mode — start immediately with the prompt as initial_request.
                    start(prompt);
                  }
                } else {
                  sendText(prompt);
                }
              }}
              textMode={textMode}
            />
          )}
          {messages.length === 0 && showDiscovery && (
            <BrandsStrip
              brands={brandOptions}
              onSelectBrand={(brand) => setBrandFocus(brand)}
              onOpenAll={() => setBrandsSheetOpen(true)}
            />
          )}
          {messages.length === 0 && showDiscovery && trendingProducts.length > 0 && (
            <TrendingStrip products={trendingProducts} loved={loved} onLove={handleLove} onBuy={buyClick} inCart={inCart} onAddToCart={addToCart} onSelect={setQuickViewProduct} />
          )}
          {messages.length === 0 && showDiscovery && editorialLooks.length > 0 && (
            <ShopTheLookStrip
              looks={editorialLooks}
              loved={loved}
              onLove={handleLove}
              onAddToCart={addToCart}
              inCart={inCart}
              onShopLook={(look) => { addAllToCart(look.items || []); setShowCart(true); }}
            />
          )}
          {youMightLike && (
            <YouMightLike data={youMightLike} loved={loved} onLove={handleLove} onBuy={buyClick} inCart={inCart} onAddToCart={addToCart} onDismiss={() => setYouMightLike(null)} onSelect={setQuickViewProduct} />
          )}
            </>
          )}
          {/* Chat thread always visible — was previously hidden whenever filters were open */}
          {messages.map((msg) =>
            msg.role === "event"
              ? <EventDivider key={msg.id} text={msg.text} />
              : <MessageBubble key={msg.id} msg={msg} loved={loved} onLove={handleLove} onBuy={buyClick}
                  highlightedId={highlightedId} onSelect={setQuickViewProduct} inCart={inCart} onAddToCart={addToCart}
                  reasonPickerProductId={reasonPickerProductId} onReasonDone={handleReasonDone}
                  onAddAllToCart={(items) => { addAllToCart(items); setShowCart(true); }}
                  userSize={effectivePrefs?.top_size || effectivePrefs?.bottom_size || null}
                  onTryOn={openTryOn} />
          )}
          {state === "thinking" && <ThinkingBubble />}
          {/* Scroll anchor — always at the very bottom of thread content */}
          <div ref={msgsEndRef} style={{ height: 0 }} />
        </div>

        {/* Show more — sticky strip between thread and input, never inside scroll */}
        {DEBUG_MODE && connected && (
          <div style={{ textAlign: "center", fontSize: ".65rem", color: "var(--ink-3)", padding: "2px 0" }}>
            dbg: connected={String(connected)} canShowMore={String(canShowMore)}
          </div>
        )}
        {!filterResults && canShowMore && (
          <div className="show-more-strip">
            <button className="show-more-btn" onClick={showMore}>Show 3 more →</button>
          </div>
        )}
        {!filterResults && !canShowMore && products.length > 0 && (
          <div className="show-more-strip">
            <p className="cf-end-note" role="status">
              You’ve reached the end — no more products to show.
            </p>
          </div>
        )}

        {!lookStripHidden && (
          <LookProgressStrip
            state={lookProgress}
            onComplete={() => sendChat("Complete the look — fill what's missing")}
            onEmptySlot={(prompt) => sendChat(prompt)}
            onSelectProduct={(p) => setQuickViewProduct(p)}
            onHide={() => setLookStripHidden(true)}
          />
        )}

        {quickReplies.length > 0 && connected && (
          <div className="quick-reply-bar">
            {quickReplies.map((opt) => (
              <button key={opt} className="quick-reply-chip"
                onClick={() => { sendChat(opt); dismissQuickReplies(); }}>
                {opt}
              </button>
            ))}
            <button className="quick-reply-dismiss" onClick={dismissQuickReplies} title="Dismiss">✕</button>
          </div>
        )}

        <div className="chat-input-bar">
          {!connected ? (
            <div className="start-row start-row--stack">
              <ModeToggle textMode={textMode} connected={connected} quality={quality}
                onVoice={switchToVoice} onText={switchToSilent} />
              {textMode ? (
                <TextInputRow
                  onSend={sendChat}
                  onStop={stop}
                  onSwitchVoice={switchToVoice}
                  onVisualSearch={sendVisualSearch}
                  onOutfitSearch={sendOutfitImage}
                  onOutfitUrl={sendOutfitUrl}
                  vsLoading={vsLoading}
                  outfitLoading={outfitLoading}
                  placeholder="Ask Mira anything — e.g. purple dresses"
                />
              ) : (
                <button className="chat-start-btn" onClick={() => start()}>
                  Start talking →
                </button>
              )}
            </div>
          ) : textMode ? (
            <TextInputRow onSend={sendChat} onStop={stop} onSwitchVoice={switchToVoice} onVisualSearch={sendVisualSearch} onOutfitSearch={sendOutfitImage} onOutfitUrl={sendOutfitUrl} vsLoading={vsLoading} outfitLoading={outfitLoading} />
          ) : (
            <VoiceActiveBar level={getLevel} onStop={stop} captions={captions} onSwitchText={switchToSilent} />
          )}
          {error && <ConnectionError retryCount={retryCount} onRetry={retry} />}
        </div>
        </div>{/* /.chat-canvas */}
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
        <Suspense fallback={null}>
          <ProductQuickView
            product={quickViewProduct}
            loved={loved.has(quickViewProduct.id)}
            inCart={inCart(quickViewProduct.id)}
            onLove={wouldBuy}
            onBuy={buyClick}
            onAddToCart={addToCart}
            onClose={() => setQuickViewProduct(null)}
            prefs={effectivePrefs}
            onSetSize={setUserSize}
            onAskMira={(product, promptKey) => {
              recordPulseAction("ask_product");
              setQuickViewProduct(null);
              const sent = askAboutProduct(product, promptKey);
              if (!sent) {
                pendingAskRef.current = { product, promptKey };
                if (!textMode) {
                  pendingTryOnStartRef.current = true; // reuse: flip to text then start()
                  setTextMode(true);
                } else {
                  start();
                }
              }
              // Scroll chat into view after closing the sheet
              requestAnimationFrame(() => {
                threadRef.current?.scrollTo?.({ top: threadRef.current.scrollHeight, behavior: "smooth" });
              });
            }}
            related={relatedProducts}
            onSelectRelated={setQuickViewProduct}
            onTryOn={(product) => {
              setQuickViewProduct(null);
              openTryOn(product);
            }}
          />
        </Suspense>
      )}
      {showCart && (
        <Suspense fallback={null}>
          <CartPanel
            items={cartItems}
            onRemove={removeFromCart}
            onClear={clearCart}
            onClose={() => setShowCart(false)}
            onTryOn={openTryOn}
          />
        </Suspense>
      )}
      {showFittingRoom && (
        <Suspense fallback={null}>
          <FittingRoom
            onClose={() => setShowFittingRoom(false)}
            onOpenTryOn={(product) => openTryOn(product)}
            onCountChange={setFittingRoomCount}
            onAddToCart={(p) => { addToCart(p); setShowFittingRoom(false); setShowCart(true); }}
            inCart={inCart}
          />
        </Suspense>
      )}
      {pulseVisible && !pulseBlocked && (
        <PlatformPulse
          step={pulseStep}
          onDismiss={() => { track("platform_feedback", { dismissed: true }); dismissPulse(); }}
          onHelpful={submitHelpful}
          onWhy={submitWhy}
          onMiss={submitMiss}
        />
      )}
      {signInPrompt && (
        <div className="delete-overlay" onClick={(e) => { if (e.target.classList.contains("delete-overlay")) setSignInPrompt(false); }}>
          <div className="delete-modal">
            <div className="delete-modal-icon">✨</div>
            <h3 className="delete-modal-title">Sign in to try it on</h3>
            <p className="delete-modal-body">
              Create a free account to see outfits on you, save your Fitting Room, and share your looks.
            </p>
            <div className="delete-modal-actions">
              <button className="delete-btn-confirm" style={{ background: "var(--accent)" }}
                onClick={() => { setSignInPrompt(false); setWantsSignIn(true); setIsGuest(false); track("signin_prompt_accepted", { from: "try_on" }); }}>
                Sign in / Sign up
              </button>
              <button className="delete-btn-cancel" onClick={() => setSignInPrompt(false)}>Maybe later</button>
            </div>
          </div>
        </div>
      )}
      {showPrivacy && (
        <Suspense fallback={null}>
          <PrivacyPolicy onClose={() => setShowPrivacy(false)} />
        </Suspense>
      )}
      {showDeleteModal && (
        <DeleteAccountModal
          onConfirm={deleteAccount}
          onCancel={() => setShowDelete(false)}
        />
      )}

      <footer className="app-footer" style={{ textAlign: "center", padding: ".5rem", fontSize: ".75rem", color: "var(--ink-3)" }}>
        {DEBUG_MODE && (
          <>state: <code>{state}</code> · mood: <code>{mood}</code> ·{" "}
          {connected ? (textMode ? "text" : "live") : "offline"} ·{" "}</>
        )}
        <button className="privacy-link" onClick={() => setShowForBrands(true)}>For brands</button>
        {" · "}
        <button className="privacy-link" onClick={() => setShowPrivacy(true)}>Privacy</button>
      </footer>

      {showForBrands && (
        <Suspense fallback={null}>
          <ForBrands
            onClose={() => setShowForBrands(false)}
            onStartDemo={() => setShowForBrands(false)}
          />
        </Suspense>
      )}

      {outfitLoading && (
        <div className="ob-overlay">
          <div className="ob-loading-panel">
            <div className="ob-loading-spinner" />
            <p className="ob-loading-text">Analysing your outfit…</p>
            <p className="ob-loading-sub">Mira is identifying each item and finding matches</p>
          </div>
        </div>
      )}
      {outfitError && !outfitLoading && (
        <div className="ob-error-toast">
          <span>{outfitError}</span>
          <button onClick={() => setOutfitError(null)}>✕</button>
        </div>
      )}
      <BrandsSheet
        open={brandsSheetOpen}
        brands={brandOptions}
        onClose={() => setBrandsSheetOpen(false)}
        onSelectBrand={(brand) => setBrandFocus(brand)}
      />

      {tryOnProduct && (
        <Suspense fallback={null}>
          <TryOnModal
            product={tryOnProduct}
            onClose={() => { setTryOnProduct(null); clearTryOn(); }}
            onTryOn={sendTryOn}
            result={tryOnResult}
            loading={tryOnLoading}
            error={tryOnError}
            onVideo={sendTryOnVideo}
            video={tryOnVideo}
            videoLoadingKind={tryOnVideoLoadingKind}
            videoError={tryOnVideoError}
            savedPhoto={savedPhoto}
            onSavePhoto={savePhoto}
            onClearPhoto={clearPhoto}
            savedTryOn={savedTryOn}
            savedStale={savedTryOnStale}
            userPrefs={effectivePrefs}
            onSetSize={setUserSize}
            lookItems={tryOnLookItems.length ? tryOnLookItems : (savedTryOn?.lookItems || [])}
            lookProgress={lookProgress}
            loved={loved}
            onLikeLookItem={(item) => {
              if (!item) return;
              const wasLoved = loved.has(item.id);
              if (!wasLoved) {
                wouldBuy(item);
                recordPulseAction("save");
              }
              addToLookProgress(item);
              track("try_on_look_like", { product_id: tryOnProduct?.id, like_id: item.id, category: item.category });
            }}
            onUnpinLookItem={(item) => {
              if (!item?.id) return;
              setLookProgress((prev) => removeProductFromSlots(prev, item.id));
              if (loved.has(item.id)) wouldBuy(item);
              track("try_on_look_unpin", { product_id: tryOnProduct?.id, unlike_id: item.id, category: item.category });
            }}
            onOpenLookItem={(item) => {
              if (!item) return;
              track("try_on_look_open", { product_id: tryOnProduct?.id, open_id: item.id, category: item.category });
              setQuickViewProduct(item);
            }}
            onShopLookItem={(item) => {
              if (!item) return;
              addToCart(item);
              track("try_on_look_add", { product_id: tryOnProduct?.id, add_id: item.id, category: item.category });
            }}
            onTryLookItem={(item) => {
              if (!item) return;
              track("try_on_look_switch", { product_id: tryOnProduct?.id, next_id: item.id, category: item.category });
              clearTryOn();
              setTryOnProduct(item);
              getTryOn(item.id).then((rec) => { if (rec) setSavedTryOn(rec); else setSavedTryOn(null); });
              if (savedPhoto?.image) sendTryOn(item.id, savedPhoto.image, savedPhoto.mime || "image/jpeg");
            }}
            onCompleteLook={(p) => {
              addToLookProgress(p);
              const label = p?.name ? ` around the ${p.name}` : "";
              sendText(`Complete the look${label} — tops, accessories, the works`);
            }}
          />
        </Suspense>
      )}
      {outfitAnatomy && (
        <Suspense fallback={null}>
          <OutfitBuilder
            anatomy={outfitAnatomy}
            onClose={() => setOutfitAnatomy(null)}
            onTellMira={(products) => {
              if (!products?.length) return;
              // Show the assembled look cards immediately, then let the server
              // trigger ONE clean Mira response (comment + offer similar items).
              // We send product IDs — NOT a verbose fake-user message — so Mira
              // knows these are catalog items and doesn't greet or say she can't
              // find them.
              addAssembledLookToChat(products);
              sendOutfitAssembled(products.map((p) => p.id));
            }}
          />
        </Suspense>
      )}
      {DEBUG_MODE && (
        <Suspense fallback={null}>
          <SessionWatcherPanel />
        </Suspense>
      )}
    </>
  );
}
