"""Deterministic, catalog-grounded complete-look recommendations.

The language model can explain a look, but it never chooses product IDs. This module
selects compatible products from the affiliate catalog so every displayed item is
real, priced, and linked before Mira makes a recommendation.

A "complete look" = outfit anchor + shoes + bag + accessories (5–6 pieces total).
"""
from __future__ import annotations

import random
from collections.abc import Iterable


# ── Occasion buckets ──────────────────────────────────────────────────────────

def _occasion_bucket(occasion: str) -> str:
    o = occasion.lower()
    if any(w in o for w in ["sangeet", "mehndi", "haldi"]):
        return "sangeet"
    if any(w in o for w in ["reception", "bridal", "bride", "wedding"]):
        return "wedding"
    if any(w in o for w in ["diwali", "navratri", "festive", "puja", "festival"]):
        return "festive"
    if any(w in o for w in ["cocktail", "gala", "formal", "black tie"]):
        return "cocktail"
    if any(w in o for w in ["party", "birthday", "celebration", "club", "night out"]):
        return "party"
    if any(w in o for w in ["office", "work", "business", "meeting", "interview"]):
        return "office"
    if any(w in o for w in ["date", "dinner", "romantic"]):
        return "date"
    if any(w in o for w in ["beach", "vacation", "resort", "travel", "holiday"]):
        return "casual"
    return "casual"


# ── Exclusions per occasion bucket ───────────────────────────────────────────

_EXCLUDE: dict[str, list[str]] = {
    "wedding":  ["athletic", "workout", "gym", "sports bra", "leggings",
                 "quick dry", "basketball", "compression", "sleepwear", "pajama",
                 "lingerie", "swim", "trunks"],
    "sangeet":  ["athletic", "workout", "gym", "sleepwear", "lingerie", "swim"],
    "festive":  ["athletic", "workout", "gym", "sleepwear", "lingerie", "swim"],
    "cocktail": ["athletic", "workout", "gym", "sleepwear", "swim", "pajama"],
    "party":    ["sleepwear", "pajama", "athletic", "workout", "gym"],
    "office":   ["swimwear", "lingerie", "sleepwear", "swim", "sequin", "party"],
    "date":     ["sleepwear", "pajama", "athletic", "gym", "workout"],
    "casual":   ["sleepwear", "pajama", "lingerie"],
}


# ── Style preference boosts ───────────────────────────────────────────────────

_STYLE_TERMS: dict[str, list[str]] = {
    "wedding":  ["floral", "lace", "chiffon", "midi", "maxi", "wrap", "elegant",
                 "silk", "embroidered", "lehenga", "saree", "anarkali"],
    "sangeet":  ["lehenga", "anarkali", "sharara", "palazzo", "silk", "embroidered",
                 "ethnic", "festive", "yellow", "floral"],
    "festive":  ["silk", "embroidered", "ethnic", "festive", "kurti", "saree",
                 "lehenga", "anarkali", "kurta", "brocade"],
    "cocktail": ["cocktail", "elegant", "chiffon", "midi", "sequin", "formal"],
    "party":    ["party", "sequin", "floral", "feminine", "cocktail", "satin"],
    "office":   ["blazer", "tailored", "formal", "structured", "chino", "trousers"],
    "date":     ["wrap", "floral", "feminine", "elegant", "midi", "silk"],
    "casual":   ["casual", "everyday", "comfortable", "relaxed", "cotton", "linen"],
}


# ── Shoe style per occasion ───────────────────────────────────────────────────

_SHOE_TERMS: dict[str, list[str]] = {
    "wedding":  ["heels", "pumps", "stiletto", "block heels", "juttis", "sandals"],
    "sangeet":  ["juttis", "heels", "ethnic", "kolhapuri", "block heels", "sandals"],
    "festive":  ["juttis", "heels", "ethnic", "kolhapuri", "sandals"],
    "cocktail": ["heels", "stiletto", "pumps", "ankle boots"],
    "party":    ["heels", "block heels", "ankle boots", "pumps"],
    "office":   ["pumps", "loafers", "flats", "formal", "ballet"],
    "date":     ["heels", "block heels", "ankle boots", "sandals"],
    "casual":   ["sneakers", "flats", "loafers", "sandals", "canvas"],
}


# ── Bag style per occasion ────────────────────────────────────────────────────

_BAG_TERMS: dict[str, list[str]] = {
    "wedding":  ["clutch", "evening", "satin", "potli", "embroidered"],
    "sangeet":  ["clutch", "potli", "embroidered", "ethnic", "evening"],
    "festive":  ["clutch", "potli", "embroidered", "ethnic"],
    "cocktail": ["clutch", "evening", "satin", "small"],
    "party":    ["clutch", "crossbody", "evening", "small"],
    "office":   ["tote", "work bag", "laptop", "structured", "leather"],
    "date":     ["clutch", "crossbody", "shoulder", "small"],
    "casual":   ["crossbody", "tote", "shoulder", "sling", "canvas"],
}


# ── Accessory type per occasion ───────────────────────────────────────────────

_ACCESSORY_TERMS: dict[str, list[str]] = {
    "wedding":  ["earrings", "necklace", "jewellery", "bracelet", "bangle"],
    "sangeet":  ["earrings", "necklace", "jewellery", "ethnic", "traditional"],
    "festive":  ["earrings", "necklace", "jewellery", "ethnic", "traditional"],
    "cocktail": ["watch", "bracelet", "earrings", "necklace"],
    "party":    ["earrings", "watch", "bracelet"],
    "office":   ["watch", "belt"],
    "date":     ["watch", "earrings", "bracelet"],
    "casual":   ["watch", "sunglasses"],
}


# ── Rationale copy ────────────────────────────────────────────────────────────

_RATIONALE: dict[tuple[str, str], str] = {
    # Western looks
    ("Signature Look",    "wedding"):   "Head-to-toe elegance — a dress-led look that handles ceremony, photos, and dancing.",
    ("Smart Separates",   "wedding"):   "Mix-and-match pieces that read intentional together, easy to restyle after the day.",
    ("Ethnic Glam",       "wedding"):   "Rich ethnic layers that feel celebratory without being overdressed.",
    ("Signature Look",    "cocktail"):  "A single standout piece carries the whole look — polish without effort.",
    ("Smart Separates",   "cocktail"):  "Coordinated separates that feel considered and versatile.",
    ("Ethnic Glam",       "cocktail"):  "A festive ethnic look that turns heads at any formal evening.",
    ("Signature Look",    "party"):     "One conversation-starting piece, styled simply so everything else feels intentional.",
    ("Smart Separates",   "party"):     "Elevated separates — fun, well-matched, easy to restyle for the next occasion.",
    ("Ethnic Glam",       "party"):     "Festive ethnic wear that makes the party memorable.",
    ("Signature Look",    "sangeet"):   "Bright, layered ethnic glam that's made for dancing and photographs.",
    ("Smart Separates",   "sangeet"):   "Coordinated ethnic separates — comfortable on the dance floor, stunning in photos.",
    ("Ethnic Glam",       "sangeet"):   "Full traditional look — the kind of outfit that anchors the evening.",
    ("Signature Look",    "festive"):   "Silk and embroidery that feels special without being overdressed.",
    ("Smart Separates",   "festive"):   "Layered festive separates that move from puja to party without a change.",
    ("Ethnic Glam",       "festive"):   "A richly embellished look for Diwali, Navratri, or any big festive night.",
    ("Signature Look",    "office"):    "A polished dress-led look that reads serious without trying too hard.",
    ("Smart Separates",   "office"):    "Clean separates that pair well with what you already own.",
    ("Ethnic Glam",       "office"):    "Refined ethnic wear that works perfectly for formal office days or client meetings.",
    ("Signature Look",    "date"):      "A single memorable piece that's beautiful without being overdressed.",
    ("Smart Separates",   "date"):      "Elevated but relaxed separates — works for dinner and wherever the night goes.",
    ("Ethnic Glam",       "date"):      "An effortlessly stylish ethnic look that feels special without trying too hard.",
    ("Signature Look",    "casual"):    "An easy, feel-good outfit built around one key piece.",
    ("Smart Separates",   "casual"):    "Comfortable, well-matched separates for a relaxed but styled day.",
    ("Ethnic Glam",       "casual"):    "Casual ethnic wear that's comfortable, stylish, and easy to wear all day.",
}
_RATIONALE_FALLBACK = "A complete {occasion} look — Mira can refine the mood, fit, or budget from here."


# ── Look templates ────────────────────────────────────────────────────────────
# Each template is: (name, outfit_categories, is_ethnic)
# outfit_categories = what garment categories to pick from for the main outfit

_TEMPLATES: list[tuple[str, list[str], bool]] = [
    ("Signature Look",  ["dresses"],                      False),  # dress-led western
    ("Smart Separates", ["tops", "bottoms", "outerwear"], False),  # separates western
    ("Ethnic Glam",     ["ethnic"],                       True),   # ethnic anchor
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _as_number(v: object) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _text(p: dict) -> str:
    return " ".join([
        p.get("name", ""),
        p.get("category", ""),
        p.get("color", ""),
        *list(p.get("style") or []),
    ]).lower()


def _is_excluded(p: dict, bucket: str) -> bool:
    ex = _EXCLUDE.get(bucket, [])
    if not ex:
        return False
    t = _text(p)
    return any(kw in t for kw in ex)


def _score(p: dict, bucket: str, vibe: str, term_map: dict[str, list[str]]) -> float:
    t = _text(p)
    score = 0.0
    for term in term_map.get(bucket, []):
        if term in t:
            score += 2.0
    if vibe:
        for word in vibe.lower().split():
            if len(word) > 3 and word in t:
                score += 1.5
    price = _as_number(p.get("price"))
    if price >= 1500:
        score += 0.5
    if price >= 3000:
        score += 0.5
    return score


def _pick(
    candidates: list[dict],
    bucket: str,
    vibe: str,
    budget_max: float | None,
    term_map: dict[str, list[str]],
    used_ids: set[str],
) -> dict | None:
    pool = [p for p in candidates if p["id"] not in used_ids]
    if budget_max:
        affordable = [p for p in pool if _as_number(p.get("price")) <= budget_max]
        if affordable:
            pool = affordable
    if not pool:
        return None
    scored = sorted(pool, key=lambda p: _score(p, bucket, vibe, term_map), reverse=True)
    top = scored[:max(3, len(scored) // 5)]
    return random.choice(top)


def _card(p: dict) -> dict:
    return {
        "id":            p["id"],
        "name":          p["name"],
        "category":      p.get("category", "other"),
        "color":         p.get("color"),
        "price":         p.get("price"),
        "currency":      p.get("currency", "INR"),
        "image_url":     p.get("image_url"),
        "affiliate_url": p.get("affiliate_url"),
    }


# ── Public API ────────────────────────────────────────────────────────────────

def build_looks(
    catalog: Iterable[dict],
    *,
    occasion: str,
    vibe: str = "",
    budget_max: float | None = None,
) -> list[dict]:
    """Build up to three distinct COMPLETE looks from the catalog.

    Each look has:
      • outfit  — 1–3 garment pieces (dress / ethnic wear / separates)
      • shoes   — matched footwear
      • bag     — matched bag or clutch
      • accessories — watch or jewellery (optional, best-effort)
    """
    bucket = _occasion_bucket(occasion)

    # Filter catalog: need real products with affiliate links
    products = [
        p for p in catalog
        if p.get("id") and p.get("affiliate_url") and p.get("image_url")
        and not _is_excluded(p, bucket)
    ]

    by_cat: dict[str, list[dict]] = {}
    for p in products:
        by_cat.setdefault(p.get("category", "other"), []).append(p)

    used_ids: set[str] = set()
    looks: list[dict] = []

    for look_name, outfit_cats, _is_ethnic in _TEMPLATES:
        # ── 1. Pick outfit pieces ─────────────────────────────────────────────
        outfit_items: list[dict] = []
        for cat in outfit_cats:
            candidates = by_cat.get(cat, [])
            pick = _pick(candidates, bucket, vibe, budget_max, _STYLE_TERMS, used_ids)
            if pick is None:
                outfit_items = []
                break
            outfit_items.append(pick)
            used_ids.add(pick["id"])

        if not outfit_items:
            continue

        # ── 2. Pick shoes ─────────────────────────────────────────────────────
        shoe = _pick(by_cat.get("shoes", []), bucket, vibe, budget_max, _SHOE_TERMS, used_ids)
        if shoe:
            used_ids.add(shoe["id"])

        # ── 3. Pick bag ───────────────────────────────────────────────────────
        bag = _pick(by_cat.get("bags", []), bucket, vibe, budget_max, _BAG_TERMS, used_ids)
        if bag:
            used_ids.add(bag["id"])

        # ── 4. Pick accessory (best-effort) ───────────────────────────────────
        accessory = _pick(
            by_cat.get("accessories", []),
            bucket, vibe, budget_max, _ACCESSORY_TERMS, used_ids,
        )
        if accessory:
            used_ids.add(accessory["id"])

        # ── 5. Assemble look ──────────────────────────────────────────────────
        all_items = outfit_items[:]
        if shoe:       all_items.append(shoe)
        if bag:        all_items.append(bag)
        if accessory:  all_items.append(accessory)

        total = round(sum(_as_number(p.get("price")) for p in all_items), 2)
        rationale = _RATIONALE.get(
            (look_name, bucket),
            _RATIONALE_FALLBACK.format(occasion=occasion.lower()),
        )

        looks.append({
            "id":          f"draft-{len(looks) + 1}",
            "name":        look_name,
            "rationale":   rationale,
            "total_price": total,
            "occasion":    occasion,
            "items":       [_card(p) for p in all_items],
            # Structured slots so the UI can lay out the look properly
            "slots": {
                "outfit":      [_card(p) for p in outfit_items],
                "shoes":       _card(shoe)       if shoe       else None,
                "bag":         _card(bag)        if bag        else None,
                "accessories": _card(accessory)  if accessory  else None,
            },
        })

    return looks
