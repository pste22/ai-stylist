/**
 * Look-slot pin / unpin — used by VTO “like a bottom onto the Bottom rail”.
 *
 *   node tests/look-progress.spec.mjs
 */
const store = new Map();
globalThis.localStorage = {
  getItem(k) { return store.has(k) ? store.get(k) : null; },
  setItem(k, v) { store.set(k, String(v)); },
  removeItem(k) { store.delete(k); },
};

const {
  assignProductToSlot,
  clearLookProgress,
  finishLookPrompt,
  isLookIncomplete,
  matchesLookSlot,
  nextEmptySlot,
  progressLabel,
  removeProductFromSlots,
  slotForCategory,
  slotProductIds,
  visibleSlots,
  VTO_SLOT_LABELS,
} = await import("../src/lookProgress.js");

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

clearLookProgress();
let state = { slots: { top: null, bottom: null, accent: null, shoes: null } };

const top = { id: "t1", name: "Silk top", category: "tops", price: 1200 };
const bottom = { id: "b1", name: "Wide jeans", category: "bottoms", price: 2400 };
const shoes = { id: "s1", name: "Mules", category: "shoes", price: 1800 };
const bag = { id: "a1", name: "Mini bag", category: "bags", price: 900 };

assert(slotForCategory("bottoms") === "bottom", "bottoms → bottom slot");
assert(matchesLookSlot(bottom, "bottom"), "jeans match bottom slot");
assert(matchesLookSlot(bag, "accent"), "bag matches accent/bag slot");

state = assignProductToSlot(state, top);
state = assignProductToSlot(state, bottom);
assert(state.slots.bottom.id === "b1", "liked bottom lands on bottom slot");
assert(slotProductIds(state).has("b1"), "pinned ids include bottom");

const vto = visibleSlots(state, VTO_SLOT_LABELS);
assert(vto.find((s) => s.key === "accent").label === "Bag", "VTO labels accessory as Bag");
assert(vto.find((s) => s.key === "bottom").product.id === "b1", "bottom rail shows the liked jeans");

const next = nextEmptySlot(state, VTO_SLOT_LABELS);
assert(next && next.key === "accent", `next empty should be bag, got ${next && next.key}`);

state = assignProductToSlot(state, shoes);
state = assignProductToSlot(state, bag);
assert(!nextEmptySlot(state, VTO_SLOT_LABELS), "look complete has no empty slot");

state = removeProductFromSlots(state, "b1");
assert(!state.slots.bottom, "unpin clears the bottom slot");
assert(!slotProductIds(state).has("b1"), "unpinned id leaves the set");
assert(nextEmptySlot(state, VTO_SLOT_LABELS)?.key === "bottom", "bottom is next again after unpin");

clearLookProgress();
const dress = { id: "d1", name: "Green slip dress", category: "dresses", price: 3200 };
const jacket = { id: "j1", name: "Crop jacket", category: "outerwear", price: 4100 };
let dressLook = assignProductToSlot(clearLookProgress(), dress);
dressLook = assignProductToSlot(dressLook, bag);
dressLook = assignProductToSlot(dressLook, shoes);
assert(slotForCategory("outerwear") === "layer", "jacket is its own slot — must not overwrite the dress");
assert(dressLook.slots.top.id === "d1", "dress stays pinned");
assert(dressLook.slots.top._dress, "dress mode flag");
const dressVisible = visibleSlots(dressLook);
assert(dressVisible.map((s) => s.key).join(",") === "dress,accent,shoes,layer", "dress look shows jacket as 4th");
assert(isLookIncomplete(dressLook), "dress + bag + shoes still needs a jacket");
assert(progressLabel(dressLook).startsWith("3 of 4"), `progress should be 3 of 4, got ${progressLabel(dressLook)}`);
assert(nextEmptySlot(dressLook)?.key === "layer", "empty slot is the jacket");
assert(finishLookPrompt(dressLook).toLowerCase().includes("jacket"), "finish prompt asks for jackets, not a vague missing line");
dressLook = assignProductToSlot(dressLook, jacket);
assert(dressLook.slots.top.id === "d1", "adding a jacket does not replace the dress");
assert(dressLook.slots.layer.id === "j1", "jacket lands on layer");
assert(!isLookIncomplete(dressLook), "dress + bag + shoes + jacket is complete");

console.log("look-progress.spec.mjs ok");
