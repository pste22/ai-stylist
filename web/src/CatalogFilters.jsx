import { useEffect, useMemo, useRef, useState } from "react";

/** Zara-style filter pills — Brand is early for discoverability. */
const FILTER_DEFS = [
  { key: "brand", label: "Brand" },
  { key: "sort", label: "Sort by" },
  { key: "new_in", label: "New in" },
  { key: "size", label: "Size" },
  { key: "price", label: "Price" },
  { key: "colour", label: "Colour" },
  { key: "material", label: "Material" },
  { key: "specialty_size", label: "Specialty sizes" },
  { key: "collection", label: "Collection" },
  { key: "length", label: "Length" },
  { key: "pattern", label: "Pattern" },
  { key: "campaigns", label: "Campaigns" },
  { key: "fit", label: "Fit" },
  { key: "shape", label: "Shape" },
  { key: "multipack", label: "Multipack" },
  { key: "product_standard", label: "Product standard" },
  { key: "collar", label: "Collar" },
  { key: "adaptive", label: "Adaptive Features" },
  { key: "licensed", label: "Licensed characters" },
  { key: "occasion", label: "Occasion" },
  { key: "delivery", label: "Delivery" },
];

function BrandMark({ name }) {
  const letter = (name || "?").trim().charAt(0).toUpperCase() || "?";
  return <span className="brand-mark brand-mark--sm" aria-hidden="true">{letter}</span>;
}

const CATEGORY_CHIPS = [
  { key: "all", label: "All" },
  { key: "dresses", label: "Dresses" },
  { key: "tops", label: "Tops" },
  { key: "bottoms", label: "Bottoms" },
  { key: "bags", label: "Bags" },
  { key: "shoes", label: "Shoes" },
  { key: "outerwear", label: "Outerwear" },
];

const PAGE_SIZE = 24;

function buildQuery(filters, offset = 0) {
  const qs = new URLSearchParams();
  Object.entries(filters || {}).forEach(([k, v]) => {
    if (v != null && v !== "" && v !== "all") qs.set(k, v);
  });
  qs.set("limit", String(PAGE_SIZE));
  if (offset > 0) qs.set("offset", String(offset));
  return qs.toString();
}

function summarizeFilters(filters, options) {
  const bits = [];
  const order = ["category", "price", "colour", "brand", "material", "size", "fit", "occasion", "new_in"];
  for (const key of order) {
    const val = filters[key];
    if (!val || val === "all" || (key === "sort")) continue;
    const opt = (options[key] || []).find((o) => o.value === val);
    bits.push(opt?.label || String(val).replace(/_/g, " "));
  }
  for (const [key, val] of Object.entries(filters)) {
    if (!val || key === "sort" || order.includes(key)) continue;
    const opt = (options[key] || []).find((o) => o.value === val);
    bits.push(opt?.label || String(val).replace(/_/g, " "));
  }
  return bits.join(" · ");
}

export default function CatalogFilters({
  category,
  onCategory,
  onResults,
  brandFocus,
  onBrandFocusConsumed,
  onBrowseBrands,
  calm = false,
}) {
  const [filters, setFilters] = useState({ sort: "featured" });
  const [options, setOptions] = useState({});
  const [total, setTotal] = useState(null);
  const [openKey, setOpenKey] = useState(null);
  const [filtersExpanded, setFiltersExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const barRef = useRef(null);
  const onResultsRef = useRef(onResults);
  const productsRef = useRef([]);
  const offsetRef = useRef(0);
  const filtersRef = useRef(filters);
  onResultsRef.current = onResults;
  filtersRef.current = filters;

  // External brand pick from Brands we carry strip / sheet
  useEffect(() => {
    if (!brandFocus) return;
    setFilters((prev) => ({ ...prev, brand: brandFocus }));
    setOpenKey(null);
    onBrandFocusConsumed?.();
  }, [brandFocus, onBrandFocusConsumed]);

  const activeFilters = useMemo(() => {
    const next = { ...filters };
    if (category && category !== "all") next.category = category;
    return next;
  }, [filters, category]);

  useEffect(() => {
    const onDoc = (e) => {
      if (barRef.current && !barRef.current.contains(e.target)) setOpenKey(null);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const publish = (data, { append = false, active = activeFilters } = {}) => {
    const page = data.products || [];
    const products = append ? [...productsRef.current, ...page] : page;
    productsRef.current = products;
    const totalCount = typeof data.total === "number" ? data.total : products.length;
    const showMore = !!data.show_more;
    const summary = summarizeFilters(active, data.filters || options);

    const onLoadMore = showMore
      ? async () => {
          if (loadingMore) return;
          setLoadingMore(true);
          try {
            const nextOffset = offsetRef.current + PAGE_SIZE;
            const af = { ...filtersRef.current };
            if (category && category !== "all") af.category = category;
            const resp = await fetch(`/api/browse?${buildQuery(af, nextOffset)}`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const more = await resp.json();
            offsetRef.current = nextOffset;
            if (more.filters) setOptions(more.filters);
            if (typeof more.total === "number") setTotal(more.total);
            publish(more, { append: true, active: af });
          } catch (e) {
            console.error("[CatalogFilters.loadMore]", e);
          } finally {
            setLoadingMore(false);
          }
        }
      : null;

    onResultsRef.current?.({
      products,
      total: totalCount,
      show_more: showMore,
      summary,
      onLoadMore,
      reachedEnd: products.length > 0 && !showMore,
      append,
    });
  };

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      setLoading(true);
      offsetRef.current = 0;
      productsRef.current = [];
      try {
        const qs = buildQuery(activeFilters, 0);
        const resp = await fetch(`/api/browse?${qs}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        if (cancelled) return;
        setOptions(data.filters || {});
        setTotal(typeof data.total === "number" ? data.total : null);
        publish(data, { append: false, active: activeFilters });
      } catch (e) {
        console.error("[CatalogFilters]", e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    const facetActive = Object.entries(filters).some(
      ([k, v]) => k !== "sort" && v && v !== "featured"
    ) || (filters.sort && filters.sort !== "featured") || (category && category !== "all");
    if (facetActive) run();
    else {
      productsRef.current = [];
      offsetRef.current = 0;
      onResultsRef.current?.(null);
      fetch("/api/filters")
        .then((r) => r.json())
        .then((d) => { if (!cancelled) { setOptions(d.filters || {}); setTotal(d.total ?? null); } })
        .catch(() => {});
    }
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeFilters, filters, category]);

  const setFilter = (key, value) => {
    setFilters((prev) => {
      const next = { ...prev };
      if (!value || (key === "sort" && value === "featured")) {
        if (key === "sort") next.sort = "featured";
        else delete next[key];
      } else {
        next[key] = value;
      }
      return next;
    });
    setOpenKey(null);
  };

  const clearAll = () => {
    setFilters({ sort: "featured" });
    onCategory?.("all");
    productsRef.current = [];
    offsetRef.current = 0;
    onResultsRef.current?.(null);
  };

  const activeCount = Object.entries(filters).filter(
    ([k, v]) => v && !(k === "sort" && v === "featured")
  ).length + (category && category !== "all" ? 1 : 0);

  // Stay collapsed until the shopper actually asks for filters. Expanding on any
  // active facet meant tapping a category unfurled ~16 dropdowns, which on a phone
  // fills the screen and pushes the results the tap was meant to show off-screen.
  const isCalm = calm && !filtersExpanded;

  return (
    <div className={`cf-wrap${isCalm ? " cf-wrap--calm" : ""}`} ref={barRef}>
      <div className="filter-bar cf-categories">
        {CATEGORY_CHIPS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            className={`filter-chip${category === key ? " active" : ""}`}
            onClick={() => {
              onCategory?.(key);
              if (key === "all") onResultsRef.current?.(null);
            }}
          >
            {label}
          </button>
        ))}
        {isCalm && (
          <button
            type="button"
            className="filter-chip cf-filters-reveal"
            onClick={() => setFiltersExpanded(true)}
          >
            {activeCount ? `Filters · ${activeCount}` : "Filters"}
          </button>
        )}
        {calm && onBrowseBrands && (
          <button
            type="button"
            className="filter-chip"
            onClick={() => onBrowseBrands()}
          >
            Brands
          </button>
        )}
      </div>

      <div className="cf-pills" role="toolbar" aria-label="Product filters">
        {FILTER_DEFS.map(({ key, label }) => {
          const opts = options[key] || [];
          const selected = filters[key];
          const hasOpts = key === "sort" || opts.length > 0;
          const isOpen = openKey === key;
          return (
            <div key={key} className="cf-pill-wrap">
              <button
                type="button"
                className={`cf-pill${selected && selected !== "featured" ? " cf-pill--on" : ""}${isOpen ? " cf-pill--open" : ""}`}
                disabled={!hasOpts && key !== "sort"}
                onClick={() => setOpenKey(isOpen ? null : key)}
                aria-haspopup="listbox"
                aria-expanded={isOpen}
              >
                <span>{selected && selected !== "featured" && key !== "sort"
                  ? (opts.find((o) => o.value === selected)?.label || selected)
                  : key === "sort" && selected && selected !== "featured"
                    ? (opts.find((o) => o.value === selected)?.label || selected)
                    : label}</span>
                <span className="cf-chevron" aria-hidden="true">▾</span>
              </button>
              {isOpen && (
                <div
                  className={`cf-menu${key === "brand" ? " cf-menu--brands" : ""}`}
                  role="listbox"
                >
                  {key === "brand" && onBrowseBrands && (
                    <button
                      type="button"
                      className="cf-option cf-option--link"
                      onClick={() => { setOpenKey(null); onBrowseBrands(); }}
                    >
                      <span>See all brands we carry</span>
                      <span className="cf-count">→</span>
                    </button>
                  )}
                  {key !== "sort" && selected && (
                    <button type="button" className="cf-option" onClick={() => setFilter(key, "")}>
                      Clear
                    </button>
                  )}
                  {(opts.length
                    ? opts
                    : key === "sort"
                      ? [
                          { value: "featured", label: "Featured" },
                          { value: "newest", label: "Newest" },
                          { value: "price_asc", label: "Price: Low to high" },
                          { value: "price_desc", label: "Price: High to low" },
                          { value: "name", label: "Name" },
                        ]
                      : [{ value: "", label: "No matches in catalog", count: 0 }]
                  ).map((o) => (
                    <button
                      key={String(o.value)}
                      type="button"
                      role="option"
                      className={`cf-option${selected === o.value ? " cf-option--on" : ""}`}
                      disabled={o.value === "" && o.count === 0}
                      onClick={() => o.value !== "" && setFilter(key, o.value)}
                    >
                      <span className={key === "brand" ? "cf-option-brand" : undefined}>
                        {key === "brand" && o.value ? <BrandMark name={o.label || o.value} /> : null}
                        {o.label}
                      </span>
                      {o.count != null && <span className="cf-count">{o.count}</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="cf-meta">
        <span className="cf-count-label">
          {loading ? "Updating…" : total != null ? `${total.toLocaleString("en-IN")} items` : "Filter catalog"}
        </span>
        {activeCount > 0 && (
          <button type="button" className="cf-clear" onClick={clearAll}>Clear filters</button>
        )}
      </div>
    </div>
  );
}
