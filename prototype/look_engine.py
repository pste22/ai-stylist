"""Deterministic, catalog-grounded complete-look recommendations.

The language model can explain a look, but it never chooses product IDs. This module
selects compatible products from the affiliate catalog so every displayed item is
real, priced, and linked before Mira makes a recommendation.
"""
from __future__ import annotations

from collections.abc import Iterable


_TEMPLATES = (
    ("Mira's Pick", ("dresses", "shoes", "accessories")),
    ("Easy Separates", ("tops", "bottoms", "shoes")),
    ("Statement Layer", ("tops", "bottoms", "outerwear", "accessories")),
)


def _as_number(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _matches_vibe(product: dict, vibe: str) -> bool:
    if not vibe:
        return True
    needle = vibe.lower()
    haystack = " ".join(
        [product.get("name", ""), product.get("color", "")]
        + list(product.get("style") or [])
    ).lower()
    return needle in haystack


def _product_card(product: dict) -> dict:
    """Return only browser-safe card fields, including an existing affiliate URL."""
    return {
        "id": product["id"],
        "name": product["name"],
        "category": product.get("category", "other"),
        "color": product.get("color"),
        "price": product.get("price"),
        "image_url": product.get("image_url"),
        "affiliate_url": product.get("affiliate_url"),
    }


def build_looks(
    catalog: Iterable[dict],
    *,
    occasion: str,
    vibe: str = "",
    budget_max: float | None = None,
) -> list[dict]:
    """Build up to three distinct complete looks from a catalog.

    A modest budget filters individual products rather than rejecting an otherwise
    useful look. The final total is always exposed to the shopper, so Mira can be
    honest when the catalog cannot meet the stated total budget.
    """
    products = [p for p in catalog if p.get("id") and p.get("affiliate_url")]
    used_ids: set[str] = set()
    looks: list[dict] = []

    for name, categories in _TEMPLATES:
        items: list[dict] = []
        for category in categories:
            candidates = [
                p for p in products
                if p.get("category") == category and p["id"] not in used_ids
            ]
            if budget_max:
                affordable = [p for p in candidates if _as_number(p.get("price")) <= budget_max]
                if affordable:
                    candidates = affordable
            vibe_matches = [p for p in candidates if _matches_vibe(p, vibe)]
            pick_from = vibe_matches or candidates
            if not pick_from:
                items = []
                break
            product = min(pick_from, key=lambda p: _as_number(p.get("price")))
            items.append(product)
            used_ids.add(product["id"])

        if not items:
            continue
        total = round(sum(_as_number(p.get("price")) for p in items), 2)
        item_names = ", ".join(p["name"] for p in items[:2])
        looks.append({
            "id": f"draft-{len(looks) + 1}",
            "name": name,
            "rationale": (
                f"A grounded {occasion.lower()} starting point built around {item_names}. "
                "Mira can refine the mood, fit, or budget from here."
            ),
            "total_price": total,
            "items": [_product_card(product) for product in items],
        })

    return looks
