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
};

function emptyState() {
  return { slots: { top: null, bottom: null, accent: null, shoes: null }, updatedAt: Date.now() };
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
  if (c === "tops" || c === "outerwear") return "top";
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
  } else {
    slots[slot] = card;
  }
  return saveLookProgress({ ...state, slots });
}

export function filledCount(state) {
  const s = state?.slots || {};
  let n = 0;
  if (s.top) n += 1;
  if (s.bottom) n += 1;
  if (s.accent) n += 1;
  if (s.shoes) n += 1;
  return n;
}

export function isLookIncomplete(state) {
  const n = filledCount(state);
  return n >= 1 && n < 4;
}

export function progressLabel(state) {
  const n = filledCount(state);
  if (n === 0) return "";
  if (n >= 4) return "Look complete";
  return `${n} of 4 — looking good`;
}

export function visibleSlots(state) {
  const s = state?.slots || {};
  const dressMode = !!(s.top && s.top._dress && !s.bottom);
  if (dressMode) {
    return [
      { key: "dress", label: SLOT_LABELS.dress, product: s.top },
      { key: "accent", label: SLOT_LABELS.accent, product: s.accent },
      { key: "shoes", label: SLOT_LABELS.shoes, product: s.shoes },
    ];
  }
  return SLOT_ORDER.map((key) => ({
    key,
    label: SLOT_LABELS[key],
    product: s[key],
  }));
}

export function emptySlotPrompt(slotKey, state) {
  const hero = state?.slots?.bottom || state?.slots?.top;
  const withBit = hero?.name ? ` to go with my ${hero.name}` : "";
  if (slotKey === "top" || slotKey === "dress") {
    return `Show me tops${withBit}`;
  }
  if (slotKey === "bottom") return `Show me bottoms${withBit}`;
  if (slotKey === "accent") {
    return `Show me accessories, glasses or a bag${withBit}`;
  }
  if (slotKey === "shoes") return `Show me shoes${withBit}`;
  return "Help me finish my look";
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

export { SLOT_LABELS };
