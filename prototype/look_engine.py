"""Deterministic, catalog-grounded complete-look recommendations.

The language model can explain a look, but it never chooses product IDs. This module
selects compatible products from the affiliate catalog so every displayed item is
real, priced, and linked before Mira makes a recommendation.
"""
from __future__ import annotations

import random
from collections.abc import Iterable


_TEMPLATES = (
    ("Mira's Pick",       ("dresses",),                 "dress-led"),
    ("Easy Separates",    ("tops", "bottoms"),           "top-bottom"),
    ("Statement Layer",   ("tops", "bottoms", "outerwear"), "layered"),
)

# Keywords that disqualify a product for a given occasion type
_EXCLUDE_KEYWORDS: dict[str, list[str]] = {
    "wedding":   ["nightgown", "sleepwear", "chemise", "lingerie", "swim", "trunks",
                  "biker", "athletic", "workout", "gym", "pajama", "lounge",
                  "quick dry", "basketball", "compression", "sports bra"],
    "cocktail":  ["pajama", "sleepwear", "athletic", "workout", "gym", "swim",
                  "trunks", "quick dry"],
    "party":     ["pajama", "sleepwear", "athletic", "workout", "gym"],
    "office":    ["swimwear", "lingerie", "sleepwear", "swim", "party", "sequin"],
    "date":      ["pajama", "sleepwear", "athletic", "gym", "workout"],
    "casual":    ["sleepwear", "pajama", "chemise", "lingerie"],
}

# Keywords that make a product MORE relevant for an occasion (scored up)
_STYLE_TERMS: dict[str, list[str]] = {
    "wedding":   ["floral", "lace", "chiffon", "midi", "maxi", "wrap", "elegant",
                  "feminine", "formal", "cocktail", "party", "dress"],
    "cocktail":  ["cocktail", "elegant", "chiffon", "midi", "party", "formal", "dress"],
    "party":     ["party", "sequin", "floral", "feminine", "cocktail", "dress"],
    "office":    ["blazer", "tailored", "formal", "professional", "structured"],
    "date":      ["wrap", "floral", "feminine", "elegant", "midi", "dress"],
    "casual":    ["casual", "everyday", "comfortable", "relaxed", "basic"],
}

# Human-readable look descriptions keyed by (look_name, occasion_bucket)
_RATIONALE_TEMPLATES: dict[tuple[str, str], str] = {
    ("Mira's Pick", "wedding"):    "A polished, dress-led look that handles the ceremony and dancing without a second thought.",
    ("Easy Separates", "wedding"): "Mix-and-match separates that feel intentional — easy to dress up with the right accessories.",
    ("Statement Layer", "wedding"): "A layered outfit with a third piece that does the heavy lifting on style.",
    ("Mira's Pick", "party"):      "A single standout piece that makes the whole look effortless.",
    ("Easy Separates", "party"):   "Coordinated separates — versatile, stylish, and easy to restyle later.",
    ("Statement Layer", "party"):  "A layered look where the outermost piece is the conversation starter.",
    ("Mira's Pick", "office"):     "A dress-led look that reads polished all day without trying too hard.",
    ("Easy Separates", "office"):  "Clean separates that mix well with what's already in your wardrobe.",
    ("Statement Layer", "office"): "A blazer or layer that elevates a simple base into a full workday look.",
    ("Mira's Pick", "date"):       "A single-piece look that's memorable without being overdressed.",
    ("Easy Separates", "date"):    "Elevated separates that feel put-together but still relaxed.",
    ("Statement Layer", "date"):   "A layered outfit that works across dinner and wherever the night goes.",
    ("Mira's Pick", "casual"):     "An easy, feel-good outfit built around one key piece.",
    ("Easy Separates", "casual"):  "Comfortable, well-matched separates for a relaxed but styled day.",
    ("Statement Layer", "casual"): "A casual base with a layer that pulls the whole look together.",
}
_RATIONALE_FALLBACK = "A grounded {occasion} look — Mira can refine the mood, fit, or budget from here."


def _occasion_bucket(occasion: str) -> str:
    """Map a free-text occasion to the nearest keyword bucket."""
    o = occasion.lower()
    if any(w in o for w in ["wedding", "bridal", "bride", "ceremony", "reception"]):
        return "wedding"
    if any(w in o for w in ["cocktail", "gala", "formal", "black tie"]):
        return "cocktail"
    if any(w in o for w in ["party", "birthday", "celebration", "club", "night"]):
        return "party"
    if any(w in o for w in ["office", "work", "business", "meeting", "interview"]):
        return "office"
    if any(w in o for w in ["date", "dinner", "romantic"]):
        return "date"
    return "casual"


def _as_number(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _is_excluded(product: dict, bucket: str) -> bool:
    """Return True if a product should never appear for this occasion."""
    excludes = _EXCLUDE_KEYWORDS.get(bucket, [])
    if not excludes:
        return False
    text = " ".join([
        product.get("name", ""),
        product.get("color", ""),
        *list(product.get("style") or []),
    ]).lower()
    return any(kw in text for kw in excludes)


def _relevance_score(product: dict, bucket: str, vibe: str) -> float:
    """Higher = more relevant for this occasion. Used to rank candidates."""
    text = " ".join([
        product.get("name", ""),
        product.get("color", ""),
        *list(product.get("style") or []),
    ]).lower()

    score = 0.0
    # Occasion style terms
    for term in _STYLE_TERMS.get(bucket, []):
        if term in text:
            score += 2.0

    # Vibe match (user's own words)
    if vibe:
        for word in vibe.lower().split():
            if len(word) > 3 and word in text:
                score += 1.5

    # Moderate price signal — very cheap items often aren't occasion-appropriate
    price = _as_number(product.get("price"))
    if price >= 15:
        score += 0.5
    if price >= 30:
        score += 0.5

    return score


def _pick(candidates: list[dict], bucket: str, vibe: str,
          budget_max: float | None) -> dict | None:
    """Pick the best candidate: apply budget, score by relevance, add slight randomness."""
    if budget_max:
        affordable = [p for p in candidates if _as_number(p.get("price")) <= budget_max]
        if affordable:
            candidates = affordable

    if not candidates:
        return None

    # Sort by descending relevance; top-3 get random shuffle to vary looks per session
    scored = sorted(candidates, key=lambda p: _relevance_score(p, bucket, vibe), reverse=True)
    pool = scored[:max(3, len(scored) // 3)]  # top third (at least 3)
    return random.choice(pool)


def _product_card(product: dict) -> dict:
    return {
        "id":          product["id"],
        "name":        product["name"],
        "category":    product.get("category", "other"),
        "color":       product.get("color"),
        "price":       product.get("price"),
        "image_url":   product.get("image_url"),
        "affiliate_url": product.get("affiliate_url"),
    }


def build_looks(
    catalog: Iterable[dict],
    *,
    occasion: str,
    vibe: str = "",
    budget_max: float | None = None,
) -> list[dict]:
    """Build up to three distinct complete looks from the catalog."""
    bucket = _occasion_bucket(occasion)
    products = [
        p for p in catalog
        if p.get("id") and p.get("affiliate_url")
        and not _is_excluded(p, bucket)
    ]
    used_ids: set[str] = set()
    looks: list[dict] = []

    for look_name, categories, _ in _TEMPLATES:
        items: list[dict] = []
        for category in categories:
            candidates = [
                p for p in products
                if p.get("category") == category and p["id"] not in used_ids
            ]
            pick = _pick(candidates, bucket, vibe, budget_max)
            if pick is None:
                items = []
                break
            items.append(pick)
            used_ids.add(pick["id"])

        if not items:
            continue

        total = round(sum(_as_number(p.get("price")) for p in items), 2)
        rationale = _RATIONALE_TEMPLATES.get(
            (look_name, bucket),
            _RATIONALE_FALLBACK.format(occasion=occasion.lower()),
        )
        looks.append({
            "id":          f"draft-{len(looks) + 1}",
            "name":        look_name,
            "rationale":   rationale,
            "total_price": total,
            "items":       [_product_card(p) for p in items],
        })

    return looks
