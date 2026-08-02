// Size Advisor — a data/logic size recommendation (NOT derived from the AI try-on
// image, which is only a style preview). Heuristic MVP: the user's usual size +
// fit signals parsed from the product name. No structured size chart required.

const LADDER = ["XS", "S", "M", "L", "XL", "XXL"];
const TOP_CATS = new Set(["tops", "dresses", "outerwear", "activewear"]);
const BOTTOM_CATS = new Set(["bottoms"]);
const NO_SIZE_CATS = new Set(["bags", "accessories", "jewellery", "jewelry"]);

// Fit signals in the product name.
const SNUG = ["bodycon", "body-con", "body con", "slim", "skinny", "fitted", "stretch",
  "compression", "bandage", "pencil", "bodysuit"];
const LOOSE = ["oversized", "oversize", "relaxed", "loose", "baggy", "boyfriend",
  "flowy", "flowing", "wide leg", "wide-leg", "a-line"];

// "M / 28" | "m" → "M"; returns null if not on the ladder.
function normalizeSize(s) {
  if (!s) return null;
  const m = String(s).trim().toUpperCase().match(/^(XXL|XL|XS|S|M|L)\b/);
  return m ? m[1] : null;
}

function step(size, n) {
  const i = LADDER.indexOf(size);
  if (i < 0) return size;
  return LADDER[Math.max(0, Math.min(LADDER.length - 1, i + n))];
}

/**
 * @returns one of:
 *   { kind: "onesize" }                              — bags/accessories, no advice
 *   { kind: "shoes", note }                          — shoes (no size captured yet)
 *   { kind: "need_size", field }                     — ask the user their usual size
 *   { kind: "advice", field, usual, rec, alt, fit, note }
 */
export function getSizeAdvice(product, prefs) {
  const cat = (product?.category || "").toLowerCase();
  if (NO_SIZE_CATS.has(cat)) return { kind: "onesize" };
  if (cat === "shoes") {
    return { kind: "shoes", note: "Shoe fit varies by brand — check the size chart before buying." };
  }
  const field = BOTTOM_CATS.has(cat) ? "bottom_size" : "top_size";
  const usual = normalizeSize(field === "bottom_size" ? prefs?.bottom_size : prefs?.top_size);
  if (!usual) return { kind: "need_size", field };

  const name = (product?.name || "").toLowerCase();
  const isSnug = SNUG.some((k) => name.includes(k));
  const isLoose = LOOSE.some((k) => name.includes(k));

  let fit = "regular", alt = null, note;
  if (isSnug) {
    fit = "fitted"; alt = step(usual, +1);
    note = `Runs fitted — your usual ${usual} for a body-hugging look, or ${alt} for comfort.`;
  } else if (isLoose) {
    fit = "relaxed"; alt = step(usual, -1);
    note = `Runs relaxed — your usual ${usual}, or ${alt} for a closer fit.`;
  } else {
    note = `Should fit true to size — go with your usual ${usual}.`;
  }
  return { kind: "advice", field, usual, rec: usual, alt, fit, note };
}
