// A product Mira recommended this turn. "Love it" sends a would-buy signal back to
// the bridge (logged via events.py) — the seed of the commerce loop (P2-8 → Phase 3).
export default function ProductCard({ product, loved, onLove }) {
  return (
    <div className={`card ${loved ? "loved" : ""}`}>
      <div className="card-thumb" data-cat={product.category}>
        <span className="card-swatch" style={{ background: swatch(product.color) }} />
      </div>
      <div className="card-body">
        <p className="card-name">{product.name}</p>
        <p className="card-meta">
          {product.color} · ${product.price}
        </p>
      </div>
      <button
        className={`love ${loved ? "is-loved" : ""}`}
        onClick={() => onLove(product)}
        aria-label={loved ? "Loved" : "Love it"}
      >
        {loved ? "♥ Loved" : "♡ Love it"}
      </button>
    </div>
  );
}

// Map catalog color words to a rough display swatch (real imagery comes in Phase 3).
function swatch(color) {
  const map = {
    sand: "#d8c5a0", white: "#f4f4f0", charcoal: "#3a3a3a", forest: "#2e4a36",
    black: "#222", indigo: "#34406b", cream: "#efe6d2", olive: "#6b6b3a",
    burgundy: "#6b2a35", sage: "#a8b8a0", camel: "#c2956a", "washed blue": "#7e9bbf",
    tan: "#c19a6b", "off-white": "#efece4", nude: "#e3c4ad", rust: "#9c5a32",
    emerald: "#1f6b53", brown: "#6b4a30",
  };
  return map[color] || "#cbb9a8";
}
