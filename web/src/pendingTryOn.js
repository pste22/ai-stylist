/** Remember the piece a guest wanted to try on across the OAuth redirect. */

const KEY = "mira.pendingTryOn";

export function stashPendingTryOn(product) {
  if (!product?.id) return;
  try {
    sessionStorage.setItem(KEY, JSON.stringify({
      id: product.id,
      name: product.name,
      category: product.category,
      price: product.price,
      currency: product.currency,
      image_url: product.image_url,
      image_urls: product.image_urls,
      affiliate_url: product.affiliate_url,
    }));
  } catch {
    /* private mode / quota */
  }
}

export function takePendingTryOn() {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    sessionStorage.removeItem(KEY);
    const product = JSON.parse(raw);
    return product?.id ? product : null;
  } catch {
    return null;
  }
}

const LOOK_KEY = "mira.pendingLookOnMe";

function slimLookPiece(p) {
  if (!p?.id) return null;
  return {
    id: p.id,
    name: p.name,
    category: p.category,
    price: p.price,
    currency: p.currency,
    image_url: p.image_url,
    image_urls: p.image_urls,
    affiliate_url: p.affiliate_url,
    color: p.color,
  };
}

/** Remember the assembled look (bottom / shoes / bag) across the OAuth redirect. */
export function stashPendingLookOnMe(pieces) {
  const slim = (Array.isArray(pieces) ? pieces : []).map(slimLookPiece).filter(Boolean);
  if (!slim.length) return;
  try {
    sessionStorage.setItem(LOOK_KEY, JSON.stringify(slim));
  } catch {
    /* private mode / quota */
  }
}

export function takePendingLookOnMe() {
  try {
    const raw = sessionStorage.getItem(LOOK_KEY);
    if (!raw) return [];
    sessionStorage.removeItem(LOOK_KEY);
    const pieces = JSON.parse(raw);
    return Array.isArray(pieces) ? pieces.filter((p) => p?.id) : [];
  } catch {
    return [];
  }
}
