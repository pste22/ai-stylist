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
