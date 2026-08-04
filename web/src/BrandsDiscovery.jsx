import { useEffect, useMemo, useState } from "react";

/** Letter monogram when we don't have brand logos yet. */
function BrandMark({ name }) {
  const letter = (name || "?").trim().charAt(0).toUpperCase() || "?";
  return (
    <span className="brand-mark" aria-hidden="true">{letter}</span>
  );
}

/**
 * Horizontal discovery strip — brands Mira carries (not a left nav).
 * Tap a brand → parent applies CatalogFilters brand facet.
 */
export function BrandsStrip({ brands = [], onSelectBrand, onOpenAll }) {
  const top = useMemo(
    () => (brands || []).filter((b) => b?.value && (b.count ?? 0) > 0).slice(0, 10),
    [brands],
  );
  if (!top.length) return null;

  return (
    <div className="brands-strip">
      <div className="brands-strip-header">
        <span className="brands-strip-title">Brands we carry</span>
        {onOpenAll && (
          <button type="button" className="brands-strip-all" onClick={onOpenAll}>
            See all →
          </button>
        )}
      </div>
      <div className="brands-strip-scroll" role="list">
        {top.map((b) => (
          <button
            key={b.value}
            type="button"
            role="listitem"
            className="brands-chip"
            onClick={() => onSelectBrand?.(b.value)}
            title={`Shop ${b.label || b.value}`}
          >
            <BrandMark name={b.label || b.value} />
            <span className="brands-chip-name">{b.label || b.value}</span>
            {b.count != null && (
              <span className="brands-chip-count">{b.count}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

/**
 * Full-screen-ish sheet of brands with search — discovery moment, not a sidebar.
 */
export function BrandsSheet({ open, brands = [], onClose, onSelectBrand }) {
  const [q, setQ] = useState("");

  useEffect(() => {
    if (!open) setQ("");
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === "Escape") onClose?.(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const list = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const all = (brands || []).filter((b) => b?.value && (b.count ?? 0) > 0);
    if (!needle) return all;
    return all.filter((b) =>
      (b.label || b.value || "").toLowerCase().includes(needle),
    );
  }, [brands, q]);

  if (!open) return null;

  return (
    <div className="brands-sheet-overlay" onClick={onClose} role="presentation">
      <div
        className="brands-sheet"
        role="dialog"
        aria-modal="true"
        aria-label="Brands we carry"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="brands-sheet-head">
          <div>
            <h2 className="brands-sheet-title">Brands we carry</h2>
            <p className="brands-sheet-sub">Pick a brand to shop just their pieces</p>
          </div>
          <button type="button" className="brands-sheet-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        <input
          className="brands-sheet-search"
          type="search"
          placeholder="Search brands…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          autoFocus
        />
        <div className="brands-sheet-list">
          {list.length === 0 ? (
            <p className="brands-sheet-empty">No brands match that search.</p>
          ) : (
            list.map((b) => (
              <button
                key={b.value}
                type="button"
                className="brands-sheet-row"
                onClick={() => {
                  onSelectBrand?.(b.value);
                  onClose?.();
                }}
              >
                <BrandMark name={b.label || b.value} />
                <span className="brands-sheet-name">{b.label || b.value}</span>
                <span className="brands-sheet-count">{b.count} items</span>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

/** Fetch brand facet options once for strip/sheet. */
export function useBrandOptions() {
  const [brands, setBrands] = useState([]);
  useEffect(() => {
    let cancelled = false;
    fetch("/api/filters")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (cancelled || !d) return;
        setBrands(d.filters?.brand || []);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);
  return brands;
}

export default function BrandsDiscovery({
  visible,
  onSelectBrand,
  sheetOpen: controlledOpen,
  onSheetOpenChange,
}) {
  const brands = useBrandOptions();
  const [internalOpen, setInternalOpen] = useState(false);
  const sheetOpen = controlledOpen ?? internalOpen;
  const setSheetOpen = onSheetOpenChange ?? setInternalOpen;

  if (!visible && !sheetOpen) return null;

  return (
    <>
      {visible && (
        <BrandsStrip
          brands={brands}
          onSelectBrand={onSelectBrand}
          onOpenAll={() => setSheetOpen(true)}
        />
      )}
      <BrandsSheet
        open={sheetOpen}
        brands={brands}
        onClose={() => setSheetOpen(false)}
        onSelectBrand={onSelectBrand}
      />
    </>
  );
}
