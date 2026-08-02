import { useState, useMemo } from "react";

const SWATCH_COLORS = {
  white: "#f4f4f0", black: "#222", red: "#c0392b", blue: "#3a6abf",
  navy: "#1a2a4a", pink: "#e8709a", green: "#2e7d52", brown: "#7b4f2e",
  grey: "#888", gray: "#888", beige: "#d4c4a8", yellow: "#e8c23a",
  orange: "#d4762a", purple: "#6a3abf", cream: "#efe6d2", tan: "#c19a6b",
  camel: "#c2956a", silver: "#a8a8a8", gold: "#c8a830", multicolor: "linear-gradient(135deg,#e8709a,#3a6abf,#2e7d52)",
};

function ColorSwatch({ color, selected, onClick }) {
  const bg = SWATCH_COLORS[color?.toLowerCase()] || "#ccc";
  return (
    <button
      className={`ob-swatch${selected ? " selected" : ""}`}
      style={{ background: bg }}
      title={color}
      onClick={onClick}
    />
  );
}

function MiniCard({ product, selected, onSelect }) {
  if (!product) return null;
  return (
    <div className={`ob-mini-card${selected ? " selected" : ""}`} onClick={() => onSelect(product)}>
      {product.image_url
        ? <img className="ob-mini-img" src={product.image_url} alt={product.name} loading="lazy" />
        : <div className="ob-mini-img ob-mini-placeholder" />
      }
      <p className="ob-mini-name">{product.name}</p>
      <p className="ob-mini-price">
        {product.price ? `₹${Number(product.price).toLocaleString("en-IN")}` : ""}
      </p>
      {selected && <span className="ob-mini-tick">✓</span>}
    </div>
  );
}

function ItemRow({ item, onSelect, selectedProductId }) {
  const [activeColor, setActiveColor] = useState(item.color || "");

  const matches = useMemo(() => {
    const variants = item.color_variants || {};
    const col = activeColor.toLowerCase();
    return variants[col] || item.matches || [];
  }, [activeColor, item]);

  const allColors = useMemo(() => {
    const cols = new Set();
    if (item.color) cols.add(item.color.toLowerCase());
    Object.keys(item.color_variants || {}).forEach(c => cols.add(c));
    return [...cols].slice(0, 8);
  }, [item]);

  return (
    <div className="ob-item-row">
      <div className="ob-item-head">
        <span className="ob-item-label">{item.label}</span>
        <span className="ob-item-style">{item.style}</span>
      </div>
      <div className="ob-swatches">
        {allColors.map(c => (
          <ColorSwatch key={c} color={c} selected={activeColor.toLowerCase() === c}
            onClick={() => setActiveColor(c)} />
        ))}
      </div>
      <div className="ob-matches">
        {matches.length > 0
          ? matches.map(p => (
              <MiniCard key={p.id} product={p}
                selected={selectedProductId === p.id}
                onSelect={onSelect} />
            ))
          : item.unavailable
            ? <p className="ob-no-match ob-no-match--soon">🛍️ Coming soon — not in catalog yet</p>
            : <p className="ob-no-match">No catalog matches for this item</p>
        }
      </div>
    </div>
  );
}

export function OutfitBuilder({ anatomy: anatomyData, onClose, onTellMira }) {
  // anatomyData is either {items, gender, catalogNote} or a bare array (legacy)
  const anatomy = Array.isArray(anatomyData) ? anatomyData : (anatomyData?.items || []);
  const outfitGender = Array.isArray(anatomyData) ? "women" : (anatomyData?.gender || "women");
  const catalogNote = Array.isArray(anatomyData) ? null : (anatomyData?.catalogNote || null);

  // Map of category → selected product for "My Look"
  const [myLook, setMyLook] = useState(() => {
    const init = {};
    anatomy.forEach(item => {
      if (item.matches?.[0]) init[item.category + "_" + item.label] = item.matches[0];
    });
    return init;
  });

  const selectProduct = (item, product) => {
    setMyLook(prev => ({ ...prev, [item.category + "_" + item.label]: product }));
  };

  const assembled = Object.values(myLook);

  const handleTellMira = () => {
    const pickedItems = anatomy
      .map(item => myLook[item.category + "_" + item.label])
      .filter(Boolean);
    onTellMira?.(pickedItems);
    onClose?.();
  };

  if (!anatomy?.length) return null;

  const genderLabel = outfitGender === "men" ? "Men's" : outfitGender === "unisex" ? "Unisex" : "Women's";

  return (
    <div className="ob-overlay">
      <div className="ob-panel">
        <div className="ob-header">
          <span className="ob-title">👗 Outfit Anatomy · <span className="ob-gender-tag">{genderLabel}</span></span>
          <button className="ob-close" onClick={onClose}>✕</button>
        </div>

        {catalogNote && (
          <div className="ob-catalog-note">
            ℹ️ Our catalog is currently focused on women's fashion — showing the closest style &amp; color matches.
          </div>
        )}

        <div className="ob-body">
          {anatomy.map((item, i) => (
            <ItemRow
              key={i}
              item={item}
              selectedProductId={myLook[item.category + "_" + item.label]?.id}
              onSelect={(p) => selectProduct(item, p)}
            />
          ))}
        </div>

        {assembled.length > 0 && (
          <div className="ob-my-look">
            <p className="ob-my-look-title">My Assembled Look</p>
            <div className="ob-my-look-thumbs">
              {assembled.map((p, i) => p && (
                <div key={i} className="ob-thumb-wrap">
                  {p.image_url
                    ? <img className="ob-thumb" src={p.image_url} alt={p.name} />
                    : <div className="ob-thumb ob-mini-placeholder" />
                  }
                </div>
              ))}
            </div>
            <button className="ob-tell-mira-btn" onClick={handleTellMira}>
              Tell Mira about this look →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
