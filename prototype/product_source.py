"""ProductSource adapter (P1-12) — one interface, many catalogs.

The stylist brain must never care *where* products come from. Today that's a local
JSON file; Phase 3 swaps in real affiliate feeds (Amazon PA-API, LTK/ShopStyle,
Impact/CJ) by writing a new adapter that implements the same `ProductSource`
interface — no change to Mira's reasoning. See docs/10-sourcing-strategy.md.

Products are plain dicts in the shared schema (see data/products.json):
    id, name, category, color, price, style[list], gender, affiliate_url(optional)
"""
from __future__ import annotations

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
