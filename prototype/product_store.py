"""Supabase-backed product catalog with in-memory cache.

Architecture (see docs/affiliate-data-architecture.md):

  Request → in-memory catalog (sub-ms filter) → return
               ↑ miss/expired
            Supabase products table → load full active catalog → cache

  The full catalog is loaded once at startup and refreshed every 5 minutes
  in a background thread.  At 10K users/day the catalog is essentially always
  served from memory — zero Supabase read quota consumed per search.

  Writes (add/update products) go directly to Supabase; the background
  refresh picks them up within TTL seconds.

Env:
  SUPABASE_URL          Supabase project URL
  SUPABASE_SECRET_KEY   Service-role key (server-side only, never in browser)
"""
from __future__ import annotations

import os
from typing import Any

from cache import TTLCache, _MISSING

# Catalog TTL: 5 minutes.  Products change at most a few times a day.
_CATALOG_TTL = 300  # seconds


# ------------------------------------------------------------------
# Supabase client (lazy singleton — avoids import at module level)
# ------------------------------------------------------------------

_client = None
_client_lock = __import__("threading").Lock()


def _db():
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is not None:
            return _client
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SECRET_KEY", "")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SECRET_KEY must be set to use SupabaseProductSource"
            )
        _client = create_client(url, key)
    return _client


# ------------------------------------------------------------------
# Catalog loader — called by cache on cold-start and background refresh
# ------------------------------------------------------------------

def _load_catalog_from_db() -> list[dict]:
    """Fetch all active products from Supabase (bypasses the default 1000-row page cap)."""
    from product_facets import enrich_catalog

    all_products: list[dict] = []
    page_size = 1000
    start = 0
    # Prefer brand/facets when migrate_product_facets.sql has been applied.
    select_full = (
        "id,source,asin,name,category,color,price,style,gender,image_url,"
        "affiliate_url,partner_tag,created_at,brand,facets"
    )
    select_basic = (
        "id,source,asin,name,category,color,price,style,gender,image_url,"
        "affiliate_url,partner_tag,created_at"
    )
    select_cols = select_full
    while True:
        try:
            result = (
                _db()
                .table("products")
                .select(select_cols)
                .eq("is_active", True)
                .order("name")
                .range(start, start + page_size - 1)
                .execute()
            )
        except Exception:
            if select_cols == select_full:
                select_cols = select_basic
                start = 0
                all_products = []
                continue
            raise
        page = result.data or []
        all_products.extend(page)
        if len(page) < page_size:
            break
        start += page_size
    all_products = enrich_catalog(all_products)
    print(f"[product_store] catalog loaded: {len(all_products)} active products (faceted)")
    return all_products


# ------------------------------------------------------------------
# In-memory catalog cache with background refresh
# ------------------------------------------------------------------

_catalog_cache = TTLCache(
    ttl=_CATALOG_TTL,
    refresh_fn=_load_catalog_from_db,
    refresh_ratio=0.8,   # refresh at 4 min, before 5-min TTL expires
)


def _get_catalog() -> list[dict]:
    """Return catalog from cache; fetch from Supabase on miss."""
    hit = _catalog_cache.get()
    if hit is not _MISSING:
        return hit  # type: ignore[return-value]
    # Cold start — load synchronously the first time
    try:
        products = _load_catalog_from_db()
    except Exception as exc:
        print(f"[product_store] Supabase unavailable, falling back to local JSON: {exc}")
        products = _fallback_local()
    _catalog_cache.set(products)
    return products


def _fallback_local() -> list[dict]:
    """Load affiliate_products.json as a last-resort fallback."""
    import json
    from pathlib import Path
    from product_facets import enrich_catalog
    p = Path(__file__).parent / "data" / "affiliate_products.json"
    if p.exists():
        return enrich_catalog(json.loads(p.read_text()))
    return []


# ------------------------------------------------------------------
# In-memory search (pure Python — sub-millisecond for < 50K products)
# ------------------------------------------------------------------

def search_products(
    *,
    category: str | None = None,
    style: list[str] | str | None = None,
    gender: str | None = None,
    max_price: float | None = None,
    limit: int = 8,
    filters: dict | None = None,
    offset: int = 0,
) -> list[dict]:
    """Search the in-memory catalog.  All filters are AND-combined.

    Args:
        category:   Exact category match (dresses, bottoms, tops, …)
        style:      One or more style tags; product must match at least one.
        gender:     women | men | unisex.  'unisex' items match all gender queries.
        max_price:  Upper price bound (inclusive).
        limit:      Max results to return.
        filters:    Optional Zara-style facet dict (brand, colour, fit, …).
        offset:     Skip first N matches (browse pagination).

    Returns list of product dicts with the same schema as the products table.
    """
    from product_facets import filter_catalog, product_matches

    catalog = _get_catalog()
    facet_filters = dict(filters or {})
    if category:
        facet_filters["category"] = category
    if max_price is not None:
        facet_filters["max_price"] = max_price

    # Normalise style to a set
    style_set: set[str] = set()
    if isinstance(style, str):
        style_set = {style.lower()}
    elif style:
        style_set = {s.lower() for s in style}

    # When only classic args are used (voice/spotlight), keep prior semantics.
    if not facet_filters and not style_set and not gender:
        return catalog[offset: offset + limit] if limit else catalog

    if style_set or gender:
        narrowed = []
        for p in catalog:
            if not product_matches(p, facet_filters):
                continue
            if gender:
                pg = (p.get("gender") or "unisex").lower()
                if pg != "unisex" and pg != gender.lower():
                    continue
            if style_set:
                product_styles = {s.lower() for s in (p.get("style") or [])}
                if not style_set.intersection(product_styles):
                    continue
            narrowed.append(p)
        return narrowed[offset: offset + limit]

    matched, _total = filter_catalog(catalog, facet_filters, limit=limit, offset=offset)
    return matched


def browse_products(
    filters: dict | None = None,
    *,
    limit: int = 24,
    offset: int = 0,
) -> tuple[list[dict], int, dict]:
    """Faceted browse: products + total + available filter options."""
    from product_facets import facet_options, filter_catalog

    catalog = _get_catalog()
    filters = filters or {}
    matched, total = filter_catalog(catalog, filters, limit=limit, offset=offset)
    options = facet_options(catalog, filters)
    return matched, total, options


def vector_search(
    query_text: str,
    *,
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    limit: int = 5,
    api_key: str | None = None,
) -> list[dict]:
    """Semantic product search via pgvector similarity.

    Embeds query_text with Google text-embedding-004, then calls the
    match_products Supabase RPC.  Falls back to an empty list if pgvector
    isn't set up yet (embeddings column missing / RPC not created).

    Requires GEMINI_API_KEY (or pass api_key=).
    """
    import os
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return []
    try:
        from google import genai as _genai
        client = _genai.Client(api_key=key)
        resp = client.models.embed_content(
            model="gemini-embedding-001",
            contents=[query_text],
            config={"output_dimensionality": 768},
        )
        embedding = resp.embeddings[0].values
    except Exception as e:
        print(f"[vector_search] embed failed: {e}")
        return []

    try:
        rpc_params: dict = {"query_embedding": embedding, "match_count": limit}
        if category:
            rpc_params["filter_category"] = category
        if min_price is not None:
            rpc_params["min_price"] = min_price
        if max_price is not None:
            rpc_params["max_price"] = max_price
        result = _db().rpc("match_products", rpc_params).execute()
        return result.data or []
    except Exception as e:
        print(f"[vector_search] rpc failed: {e}")
        return []


def render_products(products: list[dict]) -> str:
    """Render products as compact pipe-delimited lines for the LLM prompt."""
    lines = []
    for p in products:
        styles = ",".join(p.get("style") or [])
        price = f"${p['price']:.2f}" if p.get("price") else "N/A"
        lines.append(
            f"{p['id']} | {p['name']} | {p.get('category','')} | "
            f"{p.get('color','')} | {price} | {styles} | {p.get('gender','')}"
        )
    return "\n".join(lines)


# ------------------------------------------------------------------
# Write helpers (used by migrate_products.py and admin flows)
# ------------------------------------------------------------------

def upsert_product(product: dict) -> dict:
    """Insert or update one product in Supabase.  Invalidates the cache."""
    from datetime import datetime, timezone
    record = {**product, "updated_at": datetime.now(timezone.utc).isoformat()}
    result = _db().table("products").upsert(record, on_conflict="id").execute()
    _catalog_cache.invalidate()
    return result.data[0] if result.data else {}


def upsert_products(products: list[dict]) -> int:
    """Bulk upsert a list of products.  Returns count inserted/updated."""
    if not products:
        return 0
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    records = [{**p, "updated_at": now} for p in products]

    # Supabase upsert is a single round-trip regardless of batch size
    _db().table("products").upsert(records, on_conflict="id").execute()
    _catalog_cache.invalidate()
    return len(records)


def deactivate_product(product_id: str) -> None:
    """Soft-delete: set is_active=false.  Hard delete is avoided to preserve FK integrity."""
    _db().table("products").update({"is_active": False}).eq("id", product_id).execute()
    _catalog_cache.invalidate()


def get_product(product_id: str) -> dict | None:
    """Fetch a single product by id (checks cache first)."""
    for p in _get_catalog():
        if p["id"] == product_id:
            return p
    # May be inactive — hit DB directly
    result = _db().table("products").select("*").eq("id", product_id).execute()
    return result.data[0] if result.data else None


# ------------------------------------------------------------------
# ProductSource protocol adapter
# (drop-in replacement for CuratedAmazonSource / LocalJsonSource)
# ------------------------------------------------------------------

class SupabaseProductSource:
    """Implements the ProductSource protocol backed by Supabase + in-memory cache."""

    def search(
        self,
        *,
        category: str | None = None,
        style: list[str] | str | None = None,
        gender: str | None = None,
        max_price: float | None = None,
        limit: int = 8,
    ) -> list[dict]:
        return search_products(
            category=category,
            style=style,
            gender=gender,
            max_price=max_price,
            limit=limit,
        )

    def render(self, products: list[dict]) -> str:
        return render_products(products)
