/**
 * Retailer-aware shop CTAs + click tracking helpers.
 * Mira is multi-retailer; never hardcode "Amazon" when the product isn't.
 */

const HOST_MAP = [
  { test: /amazon\.(in|com|co\.uk)/i, id: "amazon", label: "Amazon" },
  { test: /amzn\.to/i, id: "amazon", label: "Amazon" },
  { test: /myntra\.com/i, id: "myntra", label: "Myntra" },
  { test: /ajio\.com/i, id: "ajio", label: "Ajio" },
  { test: /nykaa(fashion)?\.com/i, id: "nykaa", label: "Nykaa Fashion" },
  { test: /snitch\.(co|in)/i, id: "snitch", label: "Snitch" },
  { test: /bewakoof\.com/i, id: "bewakoof", label: "Bewakoof" },
  { test: /urbanic\.com/i, id: "urbanic", label: "Urbanic" },
  { test: /tatacliq\.com/i, id: "tatacliq", label: "Tata CLiQ" },
  { test: /flipkart\.com/i, id: "flipkart", label: "Flipkart" },
  { test: /cuelinks\.com/i, id: "cuelinks", label: "Partner store" },
  { test: /vcommission\.com/i, id: "vcommission", label: "Partner store" },
];

const SOURCE_MAP = {
  amazon: { id: "amazon", label: "Amazon" },
  curated: { id: "amazon", label: "Amazon" },
  myntra: { id: "myntra", label: "Myntra" },
  ajio: { id: "ajio", label: "Ajio" },
  snitch: { id: "snitch", label: "Snitch" },
  nykaa: { id: "nykaa", label: "Nykaa Fashion" },
  bewakoof: { id: "bewakoof", label: "Bewakoof" },
  urbanic: { id: "urbanic", label: "Urbanic" },
  cuelinks: { id: "partner", label: "Partner store" },
  brand: { id: "brand", label: "Brand store" },
};

function fromSource(source) {
  if (!source) return null;
  const s = String(source).toLowerCase();
  for (const [key, val] of Object.entries(SOURCE_MAP)) {
    if (s === key || s.includes(key)) return val;
  }
  if (s.startsWith("vcommission_")) {
    const key = s.replace("vcommission_", "");
    return SOURCE_MAP[key] || { id: key, label: key.charAt(0).toUpperCase() + key.slice(1) };
  }
  if (s.startsWith("brand_")) {
    const key = s.replace("brand_", "");
    return { id: key, label: key.charAt(0).toUpperCase() + key.slice(1) };
  }
  if (s.startsWith("cuelinks_")) {
    const key = s.replace("cuelinks_", "");
    return SOURCE_MAP[key] || { id: key, label: key.charAt(0).toUpperCase() + key.slice(1) };
  }
  return null;
}

export function resolveRetailer(product) {
  if (!product) return { id: "partner", label: "Partner store" };
  if (product.retailer_label) {
    return { id: product.retailer || "partner", label: product.retailer_label };
  }
  if (product.retailer && SOURCE_MAP[product.retailer]) {
    return SOURCE_MAP[product.retailer];
  }
  const fromSrc = fromSource(product.source);
  if (fromSrc) return fromSrc;

  const url = product.affiliate_url || "";
  try {
    const host = new URL(url).hostname;
    for (const row of HOST_MAP) {
      if (row.test.test(host) || row.test.test(url)) {
        return { id: row.id, label: row.label };
      }
    }
  } catch { /* invalid url */ }

  if (product.brand) {
    return { id: "brand", label: String(product.brand) };
  }
  return { id: "partner", label: "Partner store" };
}

export function shopLabel(product, { short = false } = {}) {
  const { label } = resolveRetailer(product);
  return short ? `Shop · ${label}` : `Shop on ${label} →`;
}

/** Append Mira click attribution params without breaking existing tracking. */
export function trackedAffiliateUrl(product, { sessionId } = {}) {
  const raw = product?.affiliate_url;
  if (!raw) return "#";
  try {
    const u = new URL(raw);
    if (!u.searchParams.has("mira_pid")) {
      u.searchParams.set("mira_pid", String(product.id || ""));
    }
    if (sessionId && !u.searchParams.has("mira_sid")) {
      u.searchParams.set("mira_sid", String(sessionId).slice(0, 32));
    }
    if (!u.searchParams.has("utm_source")) {
      u.searchParams.set("utm_source", "mira");
      u.searchParams.set("utm_medium", "affiliate");
      u.searchParams.set("utm_campaign", resolveRetailer(product).id);
    }
    return u.toString();
  } catch {
    return raw;
  }
}
