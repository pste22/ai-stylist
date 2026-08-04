import { useCallback, useMemo, useState } from "react";

const STORAGE_KEY = "mira_product_reviews_v1";

function loadAll() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveAll(map) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch (e) {
    console.warn("[reviews] persist failed", e);
  }
}

/** Local-first Mira reviews (sketch). Swap for Supabase when P6-3 ships server-side. */
export function useProductReviews(productId) {
  const [version, setVersion] = useState(0);

  const reviews = useMemo(() => {
    void version;
    if (!productId) return [];
    const all = loadAll();
    return Array.isArray(all[productId]) ? all[productId] : [];
  }, [productId, version]);

  const aggregate = useMemo(() => {
    if (!reviews.length) return null;
    const sum = reviews.reduce((a, r) => a + (Number(r.stars) || 0), 0);
    const avg = sum / reviews.length;
    const fitCounts = { tight: 0, true: 0, loose: 0 };
    for (const r of reviews) {
      if (r.fit && fitCounts[r.fit] != null) fitCounts[r.fit] += 1;
    }
    const topFit = Object.entries(fitCounts).sort((a, b) => b[1] - a[1])[0];
    return {
      avg,
      count: reviews.length,
      topFit: topFit && topFit[1] > 0 ? topFit[0] : null,
    };
  }, [reviews]);

  const addReview = useCallback((productIdArg, review) => {
    if (!productIdArg) return;
    const all = loadAll();
    const list = Array.isArray(all[productIdArg]) ? all[productIdArg] : [];
    const entry = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      stars: Math.min(5, Math.max(1, Number(review.stars) || 5)),
      fit: review.fit || null,
      text: (review.text || "").trim().slice(0, 280),
      photo: review.photo || null,
      createdAt: new Date().toISOString(),
    };
    all[productIdArg] = [entry, ...list].slice(0, 50);
    saveAll(all);
    setVersion((v) => v + 1);
    return entry;
  }, []);

  return { reviews, aggregate, addReview };
}

export function formatFitLabel(fit) {
  if (fit === "tight") return "Runs tight";
  if (fit === "loose") return "Runs loose";
  if (fit === "true") return "True to size";
  return null;
}
