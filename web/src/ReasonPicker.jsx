import { useState, useEffect, useCallback } from "react";

const PRICE_TIERS = [
  { max: 50,       label: "Budget-friendly price" },
  { max: 150,      label: "Mid-range price" },
  { max: 400,      label: "Premium quality" },
  { max: Infinity, label: "Luxury feel" },
];

const STOP = new Set(["the","a","an","and","or","for","with","in","on","at","by","of","to",
  "knee","length","short","long","high","low","plus","size","dress","dresses","top","tops",
  "bag","bags","shoes","boot","boots","style","styles","look","women","mens","unisex"]);

function extractBrand(name) {
  if (!name) return null;
  for (const word of name.split(/\s+/)) {
    // Skip words that start with digits (e.g. "72styles") — not a real brand name
    if (/^\d/.test(word)) continue;
    const clean = word.replace(/[^a-zA-Z]/g, "");
    if (clean.length >= 3 && !STOP.has(clean.toLowerCase())) return clean;
  }
  return null;
}

function buildChips(product) {
  const chips = [];
  if (product.color) chips.push({ key: "color",    label: `${product.color} color` });
  const brand = extractBrand(product.name);
  if (brand)          chips.push({ key: "brand",    label: `${brand} brand` });
  if (product.category) chips.push({ key: "cat",   label: `${product.category} style` });
  (product.style || []).slice(0, 2).forEach((s, i) =>
    chips.push({ key: `style${i}`, label: s.charAt(0).toUpperCase() + s.slice(1) })
  );
  const tier = PRICE_TIERS.find(t => (product.price || 0) <= t.max);
  if (tier) chips.push({ key: "price", label: tier.label });
  chips.push({ key: "look", label: "The overall look" });
  return chips;
}

export function ReasonPicker({ product, onDone, autoSecs = 8 }) {
  const [selected, setSelected] = useState(new Set());
  const [secs, setSecs] = useState(autoSecs);
  const chips = buildChips(product);

  const submit = useCallback((sel) => {
    const labels = chips.filter(c => sel.has(c.key)).map(c => c.label);
    onDone(labels);
  }, [chips, onDone]);

  useEffect(() => {
    if (secs <= 0) return;
    const id = setTimeout(() => {
      setSecs(s => {
        if (s <= 1) { submit(selected); return 0; }
        return s - 1;
      });
    }, 1000);
    return () => clearTimeout(id);
  }, [secs, selected, submit]);

  const toggle = (key) =>
    setSelected(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  return (
    <div className="reason-picker">
      <div className="reason-picker-head">
        <span className="reason-picker-label">Why did you like this?</span>
        <span className="reason-picker-timer">{secs}s</span>
      </div>
      <div className="reason-picker-chips">
        {chips.map(c => (
          <button
            key={c.key}
            className={`reason-chip${selected.has(c.key) ? " selected" : ""}`}
            onClick={() => toggle(c.key)}
          >
            {c.label}
          </button>
        ))}
      </div>
      <div className="reason-picker-footer">
        <button className="reason-done-btn" onClick={() => submit(selected)}>
          {selected.size > 0 ? `Tell Mira (${selected.size}) →` : "Skip →"}
        </button>
      </div>
    </div>
  );
}
