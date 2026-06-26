"""Loads and searches the hardcoded Phase 1 product catalog.

Phase 1 keeps this dead simple: a JSON file + naive keyword/attribute filtering.
Real multi-source affiliate sourcing is Phase 3 (see docs/03-roadmap.md).
"""
from __future__ import annotations

import json
from pathlib import Path

_DATA = Path(__file__).parent / "data" / "products.json"


def load_catalog() -> list[dict]:
    """Load all products from the JSON file."""
    with _DATA.open(encoding="utf-8") as f:
        return json.load(f)


def search(
    catalog: list[dict],
    *,
    category: str | None = None,
    style: str | None = None,
    gender: str | None = None,
    max_price: float | None = None,
    limit: int = 8,
) -> list[dict]:
    """Filter the catalog by simple attributes.

    All filters are optional and AND-combined. Returns up to `limit` items so we
    never overwhelm the LLM context (curation > breadth).
    """
    results = catalog
    if category:
        results = [p for p in results if p["category"] == category.lower()]
    if style:
        s = style.lower()
        results = [p for p in results if s in p["style"]]
    if gender:
        g = gender.lower()
        results = [p for p in results if p["gender"] in (g, "unisex")]
    if max_price is not None:
        results = [p for p in results if p["price"] <= max_price]
    return results[:limit]


def to_prompt_lines(products: list[dict]) -> str:
    """Compact, token-cheap rendering of products for the LLM prompt."""
    return "\n".join(
        f'- {p["id"]} | {p["name"]} | {p["category"]} | {p["color"]} | '
        f'${p["price"]} | {", ".join(p["style"])} | {p["gender"]}'
        for p in products
    )
