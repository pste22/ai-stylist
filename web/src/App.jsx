import { useState } from "react";
import RiveAvatar from "./RiveAvatar.jsx";
import ProductCard from "./ProductCard.jsx";
import NamePrompt from "./NamePrompt.jsx";
import { useMiraVoice } from "./useMiraVoice.js";
import { useUserIdentity } from "./useUserIdentity.js";

export default function App() {
  const { userId, userName, setUserName, isNewUser } = useUserIdentity();
  const { connected, state, mood, captions, products, savedProducts, loved, highlightedId, error, start, stop, wouldBuy, getLevel, buyClick } =
    useMiraVoice({ userId, userName });

  const [showSaved, setShowSaved] = useState(false);

  if (isNewUser) {
    return <NamePrompt onSubmit={setUserName} />;
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Mira</h1>
        <p className="tagline">Hi {userName} 👋 — your personal AI stylist</p>
        {savedProducts.length > 0 && (
          <button
            className="saved-toggle"
            onClick={() => setShowSaved((v) => !v)}
          >
            {showSaved ? "Hide saves" : `💜 Saved (${savedProducts.length})`}
          </button>
        )}
      </header>

      {showSaved && savedProducts.length > 0 && (
        <div className="shelf saved-shelf">
          <p className="shelf-title">💜 Your saved items</p>
          <div className="grid">
            {savedProducts.map((p) => (
              <ProductCard
                key={p.id}
                product={p}
                loved={true}
                onLove={wouldBuy}
                onBuy={buyClick}
              />
            ))}
          </div>
        </div>
      )}

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
                highlighted={p.id === highlightedId}
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
