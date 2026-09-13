/** Session look-in-progress — localStorage only (easy to wipe / ignore). */

const KEY = "mira.lookProgress.v1";
const HIDE_KEY = "mira.lookProgress.hideSession";
const NUDGE_KEY = "mira.lookNudge.dismissedDate";

const SLOT_ORDER = ["top", "bottom", "accent", "shoes"];

const SLOT_LABELS = {
  top: "Top",
  bottom: "Bottom",
  accent: "Accent",
  shoes: "Shoes",
  dress: "Dress",
  layer: "Jacket",
};

function emptyState() {
  return {
    slots: { top: null, bottom: null, accent: null, shoes: null, layer: null },
    updatedAt: Date.now(),
  };
}

export function loadLookProgress() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return emptyState();
    const parsed = JSON.parse(raw);
    if (!parsed?.slots) return emptyState();
    return { ...emptyState(), ...parsed, slots: { ...emptyState().slots, ...parsed.slots } };
  } catch {
    return emptyState();
  }
}

export function saveLookProgress(state) {
  const next = { ...state, updatedAt: Date.now() };
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch { /* quota */ }
  return next;
}

export function clearLookProgress() {
  try { localStorage.removeItem(KEY); } catch { /* */ }
  return emptyState();
}

/** Map catalog category → look slot. Dress/ethnic collapses top+bottom visually. */
export function slotForCategory(category) {
  const c = (category || "").toLowerCase();
  if (c === "dresses" || c === "ethnic") return "dress";
  if (c === "outerwear") return "layer";
  if (c === "tops") return "top";
  if (c === "bottoms") return "bottom";
  if (c === "accessories" || c === "bags") return "accent";
  if (c === "shoes") return "shoes";
  return "accent";
}

export function assignProductToSlot(state, product) {
  if (!product?.id) return state;
  const slot = slotForCategory(product.category);
  const slots = { ...state.slots };
  const card = {
    id: product.id,
    name: product.name,
    category: product.category,
    color: product.color,
    price: product.price,
    image_url: product.image_url,
    affiliate_url: product.affiliate_url,
  };
  if (slot === "dress") {
    slots.top = { ...card, _dress: true };
    slots.bottom = null; // dress owns the silhouette
  } else if (slot === "layer") {
    slots.layer = card;
  } else {
    slots[slot] = card;
  }
  return saveLookProgress({ ...state, slots });
}

export function isDressLook(state) {
  const s = state?.slots || {};
  return !!(s.top && s.top._dress && !s.bottom);
}

export function filledCount(state) {
  return visibleSlots(state).filter((slot) => slot.product).length;
}

export function lookSlotTarget(state) {
  return visibleSlots(state).length;
}

export function isLookIncomplete(state) {
  const slots = visibleSlots(state);
  const n = slots.filter((slot) => slot.product).length;
  return n >= 1 && n < slots.length;
}

export function progressLabel(state) {
  const slots = visibleSlots(state);
  const n = slots.filter((slot) => slot.product).length;
  if (n === 0) return "";
  if (n >= slots.length) return "Look complete";
  return `${n} of ${slots.length} — looking good`;
}

/** VTO rail: accessory slot reads as Bag, not Accent. */
export const VTO_SLOT_LABELS = {
  top: "Top",
  bottom: "Bottom",
  accent: "Bag",
  shoes: "Shoes",
  dress: "Dress",
  layer: "Jacket",
};

export function visibleSlots(state, labels = SLOT_LABELS) {
  const s = state?.slots || {};
  const dressMode = !!(s.top && s.top._dress && !s.bottom);
  const labelOf = (key) => labels[key] || SLOT_LABELS[key];
  if (dressMode) {
    return [
      { key: "dress", label: labelOf("dress"), product: s.top },
      { key: "accent", label: labelOf("accent"), product: s.accent },
      { key: "shoes", label: labelOf("shoes"), product: s.shoes },
      { key: "layer", label: labelOf("layer"), product: s.layer },
    ];
  }
  const slots = SLOT_ORDER.map((key) => ({
    key,
    label: labelOf(key),
    product: s[key],
  }));
  if (s.layer) {
    slots.splice(2, 0, { key: "layer", label: labelOf("layer"), product: s.layer });
  }
  return slots;
}

export function slotProductIds(state) {
  const s = state?.slots || {};
  return new Set(Object.values(s).filter(Boolean).map((p) => p.id));
}

export function matchesLookSlot(product, slotKey) {
  const slot = slotForCategory(product?.category);
  if (slotKey === "dress") return slot === "dress" || slot === "top";
  if (slotKey === "top" && slot === "dress") return true;
  return slot === slotKey;
}

export function nextEmptySlot(state, labels = SLOT_LABELS) {
  return visibleSlots(state, labels).find((s) => !s.product) || null;
}

export function removeProductFromSlots(state, productId) {
  if (!productId) return state;
  const slots = { ...state.slots };
  let changed = false;
  for (const key of Object.keys(slots)) {
    if (slots[key]?.id === productId) {
      slots[key] = null;
      changed = true;
    }
  }
  if (!changed) return state;
  return saveLookProgress({ ...state, slots });
}

export function categoryForLookSlot(slotKey) {
  if (slotKey === "top" || slotKey === "dress") return "tops";
  if (slotKey === "bottom") return "bottoms";
  if (slotKey === "accent") return "bags";
  if (slotKey === "shoes") return "shoes";
  if (slotKey === "layer") return "outerwear";
  return "accessories";
}

export function lookHero(state) {
  const s = state?.slots || {};
  return s.top || s.bottom || s.layer || s.accent || s.shoes || null;
}

export function emptySlotPrompt(slotKey, state) {
  const hero = lookHero(state);
  const withBit = hero?.name ? ` to go with my ${hero.name}` : "";
  if (slotKey === "top" || slotKey === "dress") {
    return `Show me tops${withBit}`;
  }
  if (slotKey === "bottom") return `Show me bottoms${withBit}`;
  if (slotKey === "accent") {
    return `Show me bags${withBit}`;
  }
  if (slotKey === "shoes") return `Show me shoes${withBit}`;
  if (slotKey === "layer") return `Show me jackets${withBit}`;
  return `Show me pieces to finish this look${withBit}`;
}

/** Concrete shop ask for the next empty slot — never the vague phrase shop_agent ignores. */
export function finishLookPrompt(state) {
  const empty = nextEmptySlot(state);
  if (empty) return emptySlotPrompt(empty.key, state);
  if (isDressLook(state) && !state?.slots?.layer) {
    return emptySlotPrompt("layer", state);
  }
  return "Show me jackets to finish this look";
}

export function isStripHiddenThisSession() {
  try { return sessionStorage.getItem(HIDE_KEY) === "1"; } catch { return false; }
}

export function hideStripThisSession() {
  try { sessionStorage.setItem(HIDE_KEY, "1"); } catch { /* */ }
}

function todayKey() {
  return new Date().toISOString().slice(0, 10);
}

export function shouldShowFinishNudge(state) {
  if (!isLookIncomplete(state)) return false;
  try {
    return localStorage.getItem(NUDGE_KEY) !== todayKey();
  } catch {
    return true;
  }
}

export function dismissFinishNudgeForToday() {
  try { localStorage.setItem(NUDGE_KEY, todayKey()); } catch { /* */ }
}

export { SLOT_LABELS, SLOT_ORDER };
