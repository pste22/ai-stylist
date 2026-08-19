/**
 * Pending try-on stash — survives the OAuth redirect.
 *
 *   node tests/pending-tryon.spec.mjs
 */
const store = new Map();
globalThis.sessionStorage = {
  getItem(k) { return store.has(k) ? store.get(k) : null; },
  setItem(k, v) { store.set(k, String(v)); },
  removeItem(k) { store.delete(k); },
};

const { stashPendingTryOn, takePendingTryOn } = await import("../src/pendingTryOn.js");

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

assert(takePendingTryOn() === null, "empty stash is null");

stashPendingTryOn({ id: "p1", name: "Allen Solly top", category: "tops", image_url: "https://x/a.jpg" });
const once = takePendingTryOn();
assert(once?.id === "p1", "stashed product comes back");
assert(once?.name === "Allen Solly top", "name preserved");
assert(takePendingTryOn() === null, "stash is single-use");

stashPendingTryOn({ name: "no id" });
assert(takePendingTryOn() === null, "product without id is ignored");

console.log("pending-tryon.spec.mjs ok");
