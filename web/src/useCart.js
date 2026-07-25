import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "mira_cart";

function load() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); }
  catch { return []; }
}

export function useCart() {
  const [items, setItems] = useState(load);

  // Persist to localStorage on every change
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  }, [items]);

  const addItem = useCallback((product) => {
    setItems((prev) => prev.some((p) => p.id === product.id) ? prev : [...prev, product]);
  }, []);

  const addItems = useCallback((products) => {
    setItems((prev) => {
      const existing = new Set(prev.map((p) => p.id));
      const fresh = products.filter((p) => !existing.has(p.id));
      return fresh.length ? [...prev, ...fresh] : prev;
    });
  }, []);

  const removeItem = useCallback((id) => {
    setItems((prev) => prev.filter((p) => p.id !== id));
  }, []);

  const clearCart = useCallback(() => setItems([]), []);

  const inCart = useCallback((id) => items.some((p) => p.id === id), [items]);

  const total = items.reduce((sum, p) => sum + (Number(p.price) || 0), 0);

  return { items, addItem, addItems, removeItem, clearCart, inCart, total };
}
