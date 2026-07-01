import RiveAvatar from "./RiveAvatar.jsx";
import ProductCard from "./ProductCard.jsx";
import { useMiraVoice } from "./useMiraVoice.js";

// Web shell (P2-3) wired to the live voice bridge (P2-2).
// Press "Talk to Mira" → mic streams to prototype/live_server.py → Gemini Live →
// Mira's audio plays back and the avatar state/mood update from real events.
export default function App() {
  const { connected, state, mood, captions, products, loved, error, start, stop, wouldBuy, getLevel, buyClick } =
    useMiraVoice();

  return (
    <div className="app">
      <header className="app-header">
        <h1>Mira</h1>
        <p className="tagline">your AI stylist — voice-first, character-driven</p>
      </header>

      <RiveAvatar state={state} mood={mood} getLevel={getLevel} />

      <div className="captions">
        {captions.you && <p className="cap you">{captions.you}</p>}
        {captions.mira && <p className="cap mira">{captions.mira}</p>}
      </div>

      {products.length > 0 && (
        <div className="shelf">
          <p className="shelf-title">Mira's picks for you</p>
          <div className="grid">
            {products.map((p) => (
              <ProductCard
                key={p.id}
                product={p}
                loved={loved.has(p.id)}
                onLove={wouldBuy}
                onBuy={buyClick}
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
        {!connected ? (
          <button className="primary" onClick={start}>
            🎙️ Talk to Mira
          </button>
        ) : (
          <button className="primary stop" onClick={stop}>
            ⏹ End conversation
          </button>
        )}
        {error && <p className="error">{error}</p>}
        <p className="controls-hint">
          Needs the voice bridge running:{" "}
          <code>.venv/bin/python prototype/live_server.py</code>
        </p>
      </div>

      <footer className="app-footer">
        state: <code>{state}</code> · mood: <code>{mood}</code> ·{" "}
        {connected ? "live" : "offline"}
      </footer>
    </div>
  );
}
