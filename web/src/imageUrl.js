/**
 * Upgrade product image URLs to sharper CDN sizes.
 * Catalog often stores Amazon "Medium"/UL320 thumbs — fine for lists of old,
 * soft on today's 3-up / retina cards.
 */

const AMAZON_HOST =
  /(?:^|\.)(?:m\.)?media-amazon\.com|(?:^|\.)images-amazon\.com|(?:^|\.)ssl-images-amazon\.com/i;

/**
 * @param {string | null | undefined} url
 * @param {{ longest?: number }} [opts]  longest side in px (Amazon SL)
 */
export function hdProductImageUrl(url, { longest = 1500 } = {}) {
  if (!url || typeof url !== "string") return url;

  try {
    const u = new URL(url);
    if (AMAZON_HOST.test(u.hostname)) {
      const size = Math.max(400, Math.min(2000, longest | 0));
      // Processing block looks like `._AC_UL320_.` / `._SL500_.` (underscores inside).
      // Replace the whole block, or insert SL if the asset has no block yet.
      if (/\._.+\.(?:jpe?g|png|webp)$/i.test(u.pathname)) {
        u.pathname = u.pathname.replace(
          /\._.+\.(jpe?g|png|webp)$/i,
          `._AC_SL${size}_.$1`,
        );
      } else {
        u.pathname = u.pathname.replace(
          /\.(jpe?g|png|webp)$/i,
          `._AC_SL${size}_.$1`,
        );
      }
      return u.toString();
    }

    if (u.hostname.includes("images.pexels.com")) {
      u.searchParams.set("auto", "compress");
      u.searchParams.set("cs", "tinysrgb");
      u.searchParams.set("w", String(Math.min(longest, 1600)));
      u.searchParams.set("dpr", "2");
      return u.toString();
    }
  } catch {
    /* keep original */
  }
  return url;
}

/** srcset for responsive product cards (grid / mobile snap). */
export function productImageSrcSet(url) {
  if (!url) return undefined;
  const s800 = hdProductImageUrl(url, { longest: 800 });
  const s1500 = hdProductImageUrl(url, { longest: 1500 });
  if (!s800 || (s800 === url && s1500 === url)) return undefined;
  return `${s800} 800w, ${s1500} 1500w`;
}

export function isProductPhotoUrl(url) {
  return !!(
    url &&
    (url.includes("m.media-amazon.com") ||
      url.includes("media-amazon.com") ||
      url.includes("images-amazon.com") ||
      url.includes("images.pexels.com"))
  );
}

function bytesToBase64(buf) {
  const bytes = new Uint8Array(buf);
  const chunk = 0x8000;
  let binary = "";
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

export function proxiedProductImageUrl(url, { longest = 1200 } = {}) {
  const hd = hdProductImageUrl(url, { longest }) || url;
  if (!hd) return hd;
  return `/api/product-image?url=${encodeURIComponent(hd)}`;
}

/**
 * Pull garment bytes the browser can actually load (Amazon often 403s Fly IPs).
 * Same-origin proxy first (warms the server cache Gemini uses), then CORS proxies.
 */
export async function fetchProductImageBytes(url, { timeoutMs = 20000 } = {}) {
  if (!url) return null;
  const hd = hdProductImageUrl(url, { longest: 1200 }) || url;
  const sources = [
    { src: proxiedProductImageUrl(url, { longest: 1200 }), timeoutMs },
    { src: `https://wsrv.nl/?url=${encodeURIComponent(hd)}&output=jpg&w=1200&n=-1`, timeoutMs: 8000 },
    { src: `https://images.weserv.nl/?url=${encodeURIComponent(hd)}&output=jpg&w=1200&n=-1`, timeoutMs: 8000 },
    { src: `https://wsrv.nl/?url=${encodeURIComponent(url)}&output=jpg&w=1200&n=-1`, timeoutMs: 8000 },
  ];
  for (const { src, timeoutMs: ms } of sources) {
    const ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timer = ctrl ? setTimeout(() => ctrl.abort(), ms) : null;
    try {
      const resp = await fetch(src, {
        mode: "cors",
        credentials: "omit",
        signal: ctrl?.signal,
      });
      if (!resp.ok) continue;
      const buf = await resp.arrayBuffer();
      if (!buf || buf.byteLength < 32) continue;
      const mime = (resp.headers.get("content-type") || "image/jpeg").split(";")[0];
      if (!mime.startsWith("image/")) continue;
      return { base64: bytesToBase64(buf), mime };
    } catch {
      /* try next source */
    } finally {
      if (timer) clearTimeout(timer);
    }
  }
  return null;
}
