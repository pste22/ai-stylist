"""ProductSource adapter (P1-12) — one interface, many catalogs.

The stylist brain must never care *where* products come from. Today that's a local
JSON file; Phase 3 swaps in real affiliate feeds (Amazon PA-API, LTK/ShopStyle,
Impact/CJ) by writing a new adapter that implements the same `ProductSource`
interface — no change to Mira's reasoning. See docs/10-sourcing-strategy.md.

Products are plain dicts in the shared schema (see data/products.json):
    id, name, category, color, price, style[list], gender,
    affiliate_url(optional), image_url(optional)
"""
from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from catalog import load_catalog, search, to_prompt_lines


@runtime_checkable
class ProductSource(Protocol):
    """A swappable catalog backend. Implement this to add a new affiliate feed."""

    def search(
        self,
        *,
        category: str | None = None,
        style: str | None = None,
        gender: str | None = None,
        max_price: float | None = None,
        limit: int = 8,
    ) -> list[dict]:
        """Return up to `limit` products matching the (AND-combined) filters."""
        ...

    def render(self, products: list[dict]) -> str:
        """Render products as compact, token-cheap lines for the LLM prompt."""
        ...


class LocalJsonSource:
    """Phase 1 source: the bundled `data/products.json`. Zero cost, no network.

    Kept as the default and as an offline/demo fallback even after real sources land.
    """

    def __init__(self) -> None:
        self._catalog = load_catalog()

    def search(
        self,
        *,
        category: str | None = None,
        style: str | None = None,
        gender: str | None = None,
        max_price: float | None = None,
        limit: int = 8,
    ) -> list[dict]:
        return search(
            self._catalog,
            category=category,
            style=style,
            gender=gender,
            max_price=max_price,
            limit=limit,
        )

    def render(self, products: list[dict]) -> str:
        return to_prompt_lines(products)


# Map our taste categories to Amazon search indexes (kept tiny; extend as needed).
_AMAZON_SEARCH_INDEX = {
    "tops": "Fashion",
    "bottoms": "Fashion",
    "dresses": "Fashion",
    "outerwear": "Fashion",
    "shoes": "Shoes",
    "accessories": "Fashion",
}

# Rough category inference from an Amazon BrowseNode / title, back into our schema.
_CATEGORY_HINTS = {
    "shoes": ("shoe", "sneaker", "boot", "heel", "loafer"),
    "dresses": ("dress", "gown"),
    "outerwear": ("jacket", "coat", "blazer", "parka"),
    "bottoms": ("jean", "trouser", "pant", "short", "skirt"),
    "accessories": ("bag", "belt", "scarf", "hat", "beanie", "tote"),
    "tops": ("shirt", "tee", "top", "blouse", "sweater", "knit"),
}


def _infer_category(title: str) -> str | None:
    low = title.lower()
    for cat, words in _CATEGORY_HINTS.items():
        if any(w in low for w in words):
            return cat
    return None


def normalize_paapi_item(item: dict) -> dict:
    """Map ONE Amazon PA-API item (as a plain dict) into our product schema.

    Pure + offline so it's unit-testable without credentials or network. PA-API gives
    us name, price, image and a `DetailPageURL` that ALREADY carries our partner tag —
    that URL *is* the monetizable `affiliate_url`. Missing fields degrade gracefully.
    """
    info = item.get("ItemInfo", {})
    title = (info.get("Title", {}) or {}).get("DisplayValue", "") or "Untitled"

    listing = (item.get("Offers", {}).get("Listings") or [{}])[0]
    amount = (listing.get("Price", {}) or {}).get("Amount")
    price = float(amount) if amount is not None else None

    images = item.get("Images", {}) or {}
    image_url = ((images.get("Primary", {}) or {}).get("Medium", {}) or {}).get("URL")

    return {
        "id": item.get("ASIN", ""),
        "name": title,
        "category": _infer_category(title),
        "color": None,
        "price": price,
        "style": [],
        "gender": "unisex",
        "affiliate_url": item.get("DetailPageURL"),  # already tagged by PA-API
        "image_url": image_url,
    }


class AmazonSource:
    """Phase 3 first real source: Amazon Product Advertising API (PA-API 5).

    Strategically chosen as the easiest real feed to prove the adapter end-to-end
    (docs/10-sourcing-strategy.md). Credentials come from the environment:

        AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_PARTNER_TAG
        AMAZON_HOST (default webservices.amazon.com), AMAZON_REGION (default us-east-1)

    Requires the `amazon-paapi` package. Without keys/package we fail loudly so the
    caller can fall back to LocalJsonSource — Mira's reasoning never changes.
    """

    def __init__(self) -> None:
        self.access_key = os.environ.get("AMAZON_ACCESS_KEY")
        self.secret_key = os.environ.get("AMAZON_SECRET_KEY")
        self.partner_tag = os.environ.get("AMAZON_PARTNER_TAG")
        self.host = os.environ.get("AMAZON_HOST", "webservices.amazon.com")
        self.region = os.environ.get("AMAZON_REGION", "us-east-1")
        if not (self.access_key and self.secret_key and self.partner_tag):
            raise RuntimeError(
                "AmazonSource needs AMAZON_ACCESS_KEY / AMAZON_SECRET_KEY / "
                "AMAZON_PARTNER_TAG in the environment."
            )
        self._api = self._build_api()

    def _build_api(self):
        try:
            from amazon_paapi import AmazonApi
        except ImportError as exc:  # keep the dependency optional
            raise RuntimeError(
                "AmazonSource requires the 'amazon-paapi' package "
                "(pip install amazon-paapi)."
            ) from exc
        return AmazonApi(
            self.access_key, self.secret_key, self.partner_tag, self.region
        )

    def search(
        self,
        *,
        category: str | None = None,
        style: str | None = None,
        gender: str | None = None,
        max_price: float | None = None,
        limit: int = 8,
    ) -> list[dict]:
        keywords = " ".join(filter(None, [style, gender, category])) or "clothing"
        search_index = _AMAZON_SEARCH_INDEX.get(category or "", "Fashion")
        result = self._api.search_items(
            keywords=keywords,
            search_index=search_index,
            item_count=min(limit, 10),
        )
        items = getattr(result, "items", None) or []
        products = [normalize_paapi_item(_to_dict(i)) for i in items]
        if max_price is not None:
            products = [p for p in products if p["price"] is None or p["price"] <= max_price]
        return products[:limit]

    def render(self, products: list[dict]) -> str:
        return to_prompt_lines(products)


def _to_dict(item) -> dict:
    """PA-API SDK returns objects; normalize to the plain dict our mapper expects."""
    if isinstance(item, dict):
        return item
    # The SDK models expose .to_dict(); fall back to __dict__ if not.
    if hasattr(item, "to_dict"):
        return item.to_dict()
    return getattr(item, "__dict__", {})


def amazon_affiliate_url(asin: str, partner_tag: str | None = None) -> str:
    """Build a standard Amazon text affiliate link from an ASIN + partner tag.

    The API-free path (Phase 1): no keys needed, works the day you're accepted into
    Associates. Yields a monetizable buy link but NOT images/live price — those you seed
    manually now, and they arrive automatically once PA-API unlocks (Phase 2).
    """
    tag = partner_tag or os.environ.get("AMAZON_PARTNER_TAG", "")
    return f"https://www.amazon.com/dp/{asin}/?tag={tag}"


class CuratedAmazonSource:
    """Phase 1 (pre-API) real affiliate source — the manual-launch blueprint.

    You can't get PA-API keys until 3 sales, so seed 10–20 hand-picked Amazon products
    using SiteStripe links + manually saved images into `data/affiliate_products.json`
    (same schema as the local catalog, plus `asin`). This source serves those real,
    monetizable products today. When PA-API unlocks, flip PRODUCT_SOURCE=amazon — no
    other change, because both speak the same schema.

    Each item: id/asin, name, category, color, price, style[list], gender,
    image_url (your saved image), affiliate_url (SiteStripe link — or auto-built from
    the ASIN + AMAZON_PARTNER_TAG if omitted).
    """

    def __init__(self, path: str | None = None) -> None:
        import json
        from pathlib import Path

        file = Path(path) if path else (
            Path(__file__).parent / "data" / "affiliate_products.json"
        )
        if not file.exists():
            raise RuntimeError(
                f"Curated product file not found: {file}. Seed it with SiteStripe items."
            )
        items = json.loads(file.read_text(encoding="utf-8"))
        # Drop template/comment rows so placeholders never reach the shopper.
        items = [p for p in items if "_comment" not in p and p.get("affiliate_url") is not None]
        if not items:
            raise RuntimeError(
                f"No real products in {file} yet — add SiteStripe items "
                "(remove the template row)."
            )
        for p in items:  # fill a buy link from the ASIN if none was pasted in
            if not p.get("affiliate_url"):
                asin = p.get("asin") or p.get("id", "")
                p["affiliate_url"] = amazon_affiliate_url(asin)
        self._catalog = items

    def search(
        self,
        *,
        category: str | None = None,
        style: str | None = None,
        gender: str | None = None,
        max_price: float | None = None,
        limit: int = 8,
    ) -> list[dict]:
        return search(
            self._catalog,
            category=category,
            style=style,
            gender=gender,
            max_price=max_price,
            limit=limit,
        )

    def render(self, products: list[dict]) -> str:
        return to_prompt_lines(products)


def get_source(name: str | None = None) -> "ProductSource":
    """Pick a product source by name (or env PRODUCT_SOURCE), default 'local'.

    Falls back to LocalJsonSource if a real source can't initialize (e.g. missing
    Amazon keys), so a misconfigured env never takes Mira offline.
    """
    name = (name or os.environ.get("PRODUCT_SOURCE", "local")).lower()
    if name == "amazon":
        try:
            return AmazonSource()
        except Exception as exc:  # noqa: BLE001 — log + degrade, never crash the brain
            print(f"  ! AmazonSource unavailable ({exc}); using local catalog")
            return LocalJsonSource()
    if name == "curated":
        try:
            return CuratedAmazonSource()
        except Exception as exc:  # noqa: BLE001
            print(f"  ! CuratedAmazonSource unavailable ({exc}); using local catalog")
            return LocalJsonSource()
    return LocalJsonSource()
