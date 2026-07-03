export default function ProductCard({ product, loved, highlighted, onLove, onBuy, compact }) {
  const actions = (
    <div className="card-actions">
      <button
        className={`love ${loved ? "is-loved" : ""}`}
        onClick={() => onLove(product)}
        aria-label={loved ? "Remove from saved" : "Save item"}
        title={loved ? "Click to unlike" : "Save for later"}
      >
        {loved ? "♥ Saved" : "♡ Save"}
      </button>
      <a
        className="buy"
        href={product.affiliate_url}
        target="_blank"
        rel="noopener noreferrer nofollow sponsored"
        onClick={() => onBuy?.(product)}
      >
        Buy →
      </a>
    </div>
  );

  return (
    <div className={`card${loved ? " loved" : ""}${highlighted ? " highlighted" : ""}${compact ? " compact" : ""}`}>
      <div className="card-thumb" data-cat={product.category}>
        {product.image_url ? (
          <img className="card-img" src={product.image_url} alt={product.name} loading="lazy" />
        ) : (
          <span className="card-swatch" style={{ background: swatch(product.color) }} />
        )}
      </div>
      {compact ? (
        /* Row layout: body holds name + price + actions in one column */
        <div className="card-body">
          <p className="card-name">{product.name}</p>
          <p className="card-meta">{product.color} · ${product.price}</p>
          {actions}
        </div>
      ) : (
        /* Column layout: body and actions are separate rows */
        <>
          <div className="card-body">
            <p className="card-name">{product.name}</p>
            <p className="card-meta">{product.color} · ${product.price}</p>
          </div>
          {actions}
        </>
      )}
    </div>
  );
}

function swatch(color) {
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
