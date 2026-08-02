// IndexedDB store for the "Fitting Room" — past try-ons, kept ON-DEVICE only
// (never sent to our servers). Handles the multi-MB images/videos that would blow
// past localStorage's ~5MB limit.
//
// Record shape (keyed by productId):
//   {
//     productId, product: {id,name,price,currency,image_url,category,affiliate_url},
//     views:  { front:{image,mime}, side:{...}, back:{...} },   // base64 stills
//     clips:  { spin:{video,mime}, beach:{...}, ... },          // base64 videos
//     stills: { beach:{image,mime}, ... },                      // scene composite previews
//     photoSig,   // fingerprint of the source photo → detect a stale result
//     ts          // Date.now()
//   }

const DB_NAME = "mira_fitting_room";
const STORE = "tryons";
const VERSION = 1;

let _dbPromise = null;

function openDB() {
  if (_dbPromise) return _dbPromise;
  _dbPromise = new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") { reject(new Error("no-indexeddb")); return; }
    const req = indexedDB.open(DB_NAME, VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const os = db.createObjectStore(STORE, { keyPath: "productId" });
        os.createIndex("ts", "ts");
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return _dbPromise;
}

async function tx(mode, fn) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, mode);
    const store = t.objectStore(STORE);
    let out;
    Promise.resolve(fn(store)).then((v) => { out = v; });
    t.oncomplete = () => resolve(out);
    t.onerror = () => reject(t.error);
    t.onabort = () => reject(t.error);
  });
}

const reqP = (r) => new Promise((res, rej) => { r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });

export async function saveTryOn(record) {
  try {
    return await tx("readwrite", (s) => reqP(s.put({ ...record, ts: record.ts || Date.now() })));
  } catch { return null; } // storage full / unavailable — non-fatal
}

export async function getTryOn(productId) {
  try { return await tx("readonly", (s) => reqP(s.get(productId))); }
  catch { return null; }
}

export async function listTryOns() {
  try {
    const all = await tx("readonly", (s) => reqP(s.getAll()));
    return (all || []).sort((a, b) => (b.ts || 0) - (a.ts || 0)); // newest first
  } catch { return []; }
}

export async function deleteTryOn(productId) {
  try { return await tx("readwrite", (s) => reqP(s.delete(productId))); }
  catch { return null; }
}

export async function clearTryOns() {
  try { return await tx("readwrite", (s) => reqP(s.clear())); }
  catch { return null; }
}

// Cheap fingerprint of a base64 photo so we can flag a saved try-on as stale
// if the user later swaps their profile photo.
export function photoSignature(base64) {
  if (!base64) return "";
  let h = 0;
  const step = Math.max(1, Math.floor(base64.length / 2048));
  for (let i = 0; i < base64.length; i += step) h = (Math.imul(31, h) + base64.charCodeAt(i)) | 0;
  return `${base64.length}:${h >>> 0}`;
}
