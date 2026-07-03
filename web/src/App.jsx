import { useEffect, useRef, useState } from "react";
import RiveAvatar from "./RiveAvatar.jsx";
import ProductCard from "./ProductCard.jsx";
import NamePrompt from "./NamePrompt.jsx";
import { useMiraVoice } from "./useMiraVoice.js";
import { useUserIdentity } from "./useUserIdentity.js";

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
      // Mira is instructed to write "• [Exact Product Name] — [reason]"
      const dashIdx = content.indexOf("—");
      const namePart = dashIdx > -1 ? content.slice(0, dashIdx).trim() : content.trim();
      const reason   = dashIdx > -1 ? content.slice(dashIdx + 1).trim() : "";
      const product  = byName[namePart.toLowerCase()];

      if (product) {
        flushUnmatched();
        const isLoved = loved.has(product.id);
        blocks.push(
          <div key={key++} className="product-line">
            <div className="product-line-img-wrap">
              {product.image_url
                ? <img className="product-line-img" src={product.image_url} alt={product.name} loading="lazy" />
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

  // Any products not mentioned in text bullets (e.g. still streaming) appear at bottom
  const inlinedIds = new Set(
    lines
      .filter(l => l.match(/^[•\-\*]\s+/))
      .map(l => {
        const content = l.replace(/^[•\-\*]\s+/, "");
        const name = content.split("—")[0].trim().toLowerCase();
        return byName[name]?.id;
      })
      .filter(Boolean)
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

// ─── Full-screen chat view (text mode while connected) ────────────────────────
function ChatView({ state, mood, messages, loved, savedProducts, onLove, onBuy,
                    onStop, onSend, error, userName }) {
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
        </div>
      </div>

      {/* ── Thread ── */}
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
  );
}

// ─── Main App ────────────────────────────────────────────────────────────────
export default function App() {
  const { userId, userName, setUserName, isNewUser } = useUserIdentity();
  const [textMode, setTextMode] = useState(false);
  const [showSaved, setShowSaved] = useState(false);

  const {
    connected, state, mood, captions, messages,
    products, savedProducts, loved, highlightedId, error,
    start, stop, sendText, wouldBuy, getLevel, buyClick,
  } = useMiraVoice({ userId, userName, textMode });

  if (isNewUser) return <NamePrompt onSubmit={setUserName} />;

  // Text mode while connected → full-screen chat UI
  if (textMode && connected) {
    return (
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
      />
    );
  }

  // ── Default layout (voice mode, or text mode before connecting) ──
  return (
    <div className="app">
      <header className="app-header">
        <h1>Mira</h1>
        <p className="tagline">Hi {userName} 👋 — your personal AI stylist</p>
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
