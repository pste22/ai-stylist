import { useEffect, useMemo, useRef, useState } from "react";
import RiveAvatar from "./RiveAvatar.jsx";
import ProductCard from "./ProductCard.jsx";
import LoginScreen from "./LoginScreen.jsx";
import OnboardingFlow from "./OnboardingFlow.jsx";
import ChatHistory from "./ChatHistory.jsx";
import { useMiraVoice } from "./useMiraVoice.js";
import { useAuth } from "./useAuth.js";
import { useOnboarding } from "./useOnboarding.js";
import { useIdleTimeout } from "./useIdleTimeout.js";
import { useChatHistory } from "./useChatHistory.js";

// ─── User avatar menu (dropdown) ─────────────────────────────────────────────
function UserMenu({ userName, userEmail, userAvatar, onSignOut }) {
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
        </div>
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

// ─── Integrated bubble: text + product images inline ─────────────────────────
// Bullet lines that match a product are rendered as an image+text+actions row.
// Preamble / postamble text and unmatched bullets stay as plain paragraphs/list.
function MiraBubbleContent({ text, products = [], loved, onLove, onBuy }) {
  const byName = {};
  for (const p of products) byName[p.name.toLowerCase()] = p;

  const lines = text.split("\n");
  const blocks = [];
  const unmatchedBullets = [];
  let key = 0;

  const flushUnmatched = () => {
    if (unmatchedBullets.length) {
      blocks.push(
        <ul className="bubble-list" key={key++}>
          {unmatchedBullets.splice(0).map((item, i) => <li key={i}>{item}</li>)}
        </ul>
      );
    }
  };

  lines.forEach((line) => {
    const bullet = line.match(/^[•\-\*]\s+(.*)/);
    if (bullet) {
      const content = bullet[1];
      const dashIdx = content.indexOf("—");
      const reason  = dashIdx > -1 ? content.slice(dashIdx + 1).trim() : "";

      // Robust match: find any product whose name appears anywhere in the bullet.
      // Strips **bold** markers first so formatting never breaks the match.
      const cleaned = content.toLowerCase().replace(/\*\*/g, "").replace(/\*/g, "");
      const product = products.find(p => cleaned.includes(p.name.toLowerCase()));

      if (product) {
        flushUnmatched();
        const isLoved = loved.has(product.id);
        blocks.push(
          <div key={key++} className="product-line">
            <div className="product-line-img-wrap">
              {product.image_url && (product.image_url.includes("m.media-amazon.com") || product.image_url.includes("images.pexels.com"))
                ? <img
                    className="product-line-img"
                    src={product.image_url}
                    alt={product.name}
                    loading="lazy"
                    onError={(e) => { e.currentTarget.style.display = "none"; }}
                  />
                : <span className="product-line-swatch" style={{ background: swatchColor(product.color) }} />}
            </div>
            <div className="product-line-content">
              <p className="product-line-name">{product.name}</p>
              {reason && <p className="product-line-reason">{renderInline(reason)}</p>}
              <p className="product-line-meta">{product.color} · ${product.price}</p>
              <div className="product-line-actions">
                <button
                  className={`love${isLoved ? " is-loved" : ""}`}
                  onClick={() => onLove(product)}
                  title={isLoved ? "Click to unlike" : "Save for later"}
                >{isLoved ? "♥ Saved" : "♡ Save"}</button>
                <a className="buy" href={product.affiliate_url}
                   target="_blank" rel="noopener noreferrer nofollow sponsored"
                   onClick={() => onBuy?.(product)}>Buy →</a>
              </div>
            </div>
          </div>
        );
      } else {
        unmatchedBullets.push(renderInline(content));
      }
    } else {
      flushUnmatched();
      const trimmed = line.trim();
      if (trimmed) blocks.push(<p key={key++}>{renderInline(trimmed)}</p>);
    }
  });
  flushUnmatched();

  // Products not matched to any bullet (e.g. still streaming, or mentioned conversationally)
  // fall through as compact cards. Use same robust matching as above.
  const inlinedIds = new Set(
    lines
      .filter(l => l.match(/^[•\-\*]\s+/))
      .flatMap(l => {
        const content = l.replace(/^[•\-\*]\s+/, "").toLowerCase().replace(/\*\*/g, "").replace(/\*/g, "");
        const match = products.find(p => content.includes(p.name.toLowerCase()));
        return match ? [match.id] : [];
      })
  );
  const overflow = products.filter(p => !inlinedIds.has(p.id));
  if (overflow.length) {
    blocks.push(
      <div key={key++} className="bubble-products">
        {overflow.map(p => (
          <ProductCard key={p.id} product={p} loved={loved.has(p.id)}
            onLove={onLove} onBuy={onBuy} compact />
        ))}
      </div>
    );
  }

  return <>{blocks}</>;
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

  // Stable social-proof figures — consistent for a given product
  const savedCount  = pseudoRandom(product.id, 1337) % 40 + 8;
  const ratingTenths = pseudoRandom(product.id, 4242) % 13 + 37; // 3.7–4.9
  const rating      = (ratingTenths / 10).toFixed(1);
  const filledStars = Math.floor(ratingTenths / 10);
  const starStr     = "★".repeat(filledStars) + "☆".repeat(5 - filledStars);
  const isTrending  = pseudoRandom(product.id, 7777) % 5 === 0;
  const isNew       = pseudoRandom(product.id, 9999) % 8 === 0 && !isTrending;

  return (
    <div className="fp-product">
      {/* ── Hero image with overlays ── */}
      <div className="fp-img-wrap">
        {usePhoto
          ? <img className="fp-img" src={product.image_url} alt={product.name} loading="lazy" />
          : <div className="fp-cat-thumb" style={{ "--swatch": swatchColor(product.color) }}>
              <span className="fp-cat-emoji">{CATEGORY_EMOJI[product.category] || "🛍️"}</span>
            </div>
        }

        {/* Trend / New badge — top-left */}
        {isTrending && <span className="fp-badge fp-badge--hot">🔥 Trending</span>}
        {isNew      && <span className="fp-badge fp-badge--new">✦ New In</span>}

        {/* Heart — top-right */}
        <button
          className={`fp-heart${isLoved ? " is-loved" : ""}`}
          onClick={() => onLove(product)}
          aria-label={isLoved ? "Remove from saved" : "Save"}
        >{isLoved ? "♥" : "♡"}</button>

        {/* Hover-reveal reason (middle layer) */}
        {reason && (
          <div className="fp-img-hover">
            <p className="fp-img-hover-text">"{reason}"</p>
          </div>
        )}

        {/* Persistent bottom bar: price + quick shop */}
        <div className="fp-img-bar">
          <div className="fp-bar-text">
            <p className="fp-bar-name">{product.name}</p>
            <p className="fp-bar-price">${product.price}</p>
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

      {/* ── Details below image ── */}
      <div className="fp-details">
        <div className="fp-miras-pick">✦ Mira's Pick</div>

        {/* Social proof */}
        <div className="fp-social">
          <span className="fp-stars">{starStr}</span>
          <span className="fp-rating">{rating}</span>
          <span className="fp-sep">·</span>
          <span className="fp-saved">{savedCount} saved this week</span>
        </div>

        {/* Why Mira chose this */}
        {reason && (
          <div className="fp-why">
            <p className="fp-why-label">✦ Why Mira chose this</p>
            <p className="fp-why-text">"{reason}"</p>
          </div>
        )}

        {/* Main CTA */}
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

// ─── Full-screen chat view (text mode while connected) ────────────────────────
function ChatView({ state, mood, messages, loved, savedProducts, onLove, onBuy,
                    onStop, onSend, error, userName, userEmail, userAvatar, onSignOut,
                    canShowMore, onShowMore, products, highlightedId }) {
  const [draft, setDraft] = useState("");
  const threadRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom on every new message or chunk
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

  // Find the currently highlighted product for the right panel
  const featuredProduct = useMemo(
    () => products.find((p) => p.id === highlightedId) || null,
    [products, highlightedId]
  );

  // Try to pull out why Mira mentioned the featured product from her last message
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
      {/* ── Header ── */}
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
          <UserMenu userName={userName} userEmail={userEmail} userAvatar={userAvatar} onSignOut={onSignOut} />
        </div>
      </div>

      {/* ── Two-panel body ── */}
      <div className="chat-body">
        {/* ── LEFT: conversation thread ── */}
        <div className="chat-left">
          <div className="chat-thread" ref={threadRef}>
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

          {/* ── Show more ── */}
          {canShowMore && (
            <div className="show-more-bar">
              <button className="show-more-btn" onClick={onShowMore}>
                Show 10 more →
              </button>
            </div>
          )}

          {/* ── Input ── */}
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

        {/* ── RIGHT: featured product spotlight ── */}
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

// ─── Main App ────────────────────────────────────────────────────────────────
export default function App() {
  const {
    user, loading,
    userId, userName, userAvatar,
    signInWithGoogle, signInWithFacebook, signInWithGithub, signOut,
  } = useAuth();

  const { needsOnboarding, prefs, completeOnboarding, updatePrefs } = useOnboarding(userId);
  const { showWarning, countdown, staySignedIn } = useIdleTimeout({ onSignOut: signOut, enabled: !!user });
  const history = useChatHistory(userId);

  const [textMode, setTextMode]     = useState(false);
  const [showSaved, setShowSaved]   = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const {
    connected, state, mood, captions, messages,
    products, savedProducts, loved, highlightedId, error,
    canShowMore, setCanShowMore,
    start, stop, sendText, wouldBuy, getLevel, buyClick, showMore,
  } = useMiraVoice({ userId, userName, userPrefs: prefs, textMode });

  // Splash while checking for existing session or onboarding status
  if (loading || (user && needsOnboarding === null)) {
    return <div className="auth-loading"><span>✦</span></div>;
  }

  // Not signed in → show login screen
  if (!user) {
    return (
      <LoginScreen
        onGoogle={signInWithGoogle}
        onFacebook={signInWithFacebook}
        onGithub={signInWithGithub}
      />
    );
  }

  // New user → show onboarding
  if (needsOnboarding) {
    return <OnboardingFlow userName={userName} onComplete={completeOnboarding} />;
  }

  // Text mode while connected → full-screen chat UI
  if (textMode && connected) {
    return (
      <>
        {showWarning && (
          <SessionWarning countdown={countdown} onStay={staySignedIn} onLeave={signOut} />
        )}
        <ChatView
          state={state}
          mood={mood}
          messages={messages}
          loved={loved}
          savedProducts={savedProducts}
          onLove={wouldBuy}
          onBuy={buyClick}
          onStop={stop}
          onSend={sendText}
          error={error}
          userName={userName}
          userEmail={user?.email}
          userAvatar={userAvatar}
          onSignOut={signOut}
          canShowMore={canShowMore}
          onShowMore={showMore}
          products={products}
          highlightedId={highlightedId}
        />
      </>
    );
  }

  // ── Default layout (voice mode, or text mode before connecting) ──
  return (
    <div className="app">
      {showWarning && (
        <SessionWarning countdown={countdown} onStay={staySignedIn} onLeave={signOut} />
      )}
      {showHistory && (
        <ChatHistory
          {...history}
          onClose={() => setShowHistory(false)}
        />
      )}
      <header className="app-header">
        <div className="app-header-top">
          <h1>Mira</h1>
          <div style={{ display: "flex", alignItems: "center", gap: ".5rem" }}>
            <button className="ch-history-btn" onClick={() => setShowHistory(true)} title="Chat history">
              🕐
            </button>
            <UserMenu
              userName={userName} userEmail={user?.email}
              userAvatar={userAvatar} onSignOut={signOut}
            />
          </div>
        </div>
        <p className="tagline">Your personal AI stylist</p>
        {savedProducts.length > 0 && (
          <button className="saved-toggle" onClick={() => setShowSaved((v) => !v)}>
            {showSaved ? "Hide saves" : `💜 Saved (${savedProducts.length})`}
          </button>
        )}
      </header>

      {showSaved && savedProducts.length > 0 && (
        <div className="shelf saved-shelf">
          <p className="shelf-title">💜 Your saved items</p>
          <div className="grid">
            {savedProducts.map((p) => (
              <ProductCard key={p.id} product={p} loved onLove={wouldBuy} onBuy={buyClick} />
            ))}
          </div>
        </div>
      )}

      <RiveAvatar state={state} mood={mood} getLevel={getLevel} />

      {/* Voice mode captions */}
      {!textMode && (
        <div className="captions">
          {captions.you && <p className="cap you">{captions.you}</p>}
          {captions.mira && <p className="cap mira">{captions.mira}</p>}
        </div>
      )}

      {products.length > 0 && (
        <div className="shelf">
          <p className="shelf-title">Mira's picks for you</p>
          <div className="grid">
            {products.map((p) => (
              <ProductCard
                key={p.id} product={p}
                loved={loved.has(p.id)} highlighted={p.id === highlightedId}
                onLove={wouldBuy} onBuy={buyClick}
              />
            ))}
          </div>
          <p className="disclosure">
            Mira earns a small commission when you buy through these links — it never
            changes your price, and it keeps Mira free.
          </p>
        </div>
      )}

      <div className="controls">
        {/* Mode toggle — only before connecting */}
        {!connected && (
          <div className="mode-toggle" role="group" aria-label="Input mode">
            <button className={`mode-btn${!textMode ? " active" : ""}`} onClick={() => setTextMode(false)}>
              🎙️ Voice
            </button>
            <button className={`mode-btn${textMode ? " active" : ""}`} onClick={() => setTextMode(true)}>
              ⌨️ Silent
            </button>
          </div>
        )}

        {!connected ? (
          <button className="primary" onClick={start}>
            {textMode ? "💬 Chat with Mira" : "🎙️ Talk to Mira"}
          </button>
        ) : (
          <button className="primary stop" onClick={stop}>⏹ End conversation</button>
        )}

        {error && <p className="error">{error}</p>}

        {!connected && (
          <p className="controls-hint">
            {textMode
              ? "Silent mode — Mira replies as text. No mic or speaker needed."
              : <><code>.venv/bin/python prototype/live_server.py</code> must be running.</>}
          </p>
        )}
      </div>

      <footer className="app-footer">
        state: <code>{state}</code> · mood: <code>{mood}</code> ·{" "}
        {connected ? (textMode ? "text" : "live") : "offline"}
      </footer>
    </div>
  );
}
