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


_NEUTRALS = frozenset({
    "black", "white", "cream", "beige", "ivory", "nude", "tan", "brown",
    "grey", "gray", "charcoal", "navy", "gold", "silver", "khaki", "camel",
})
APPAREL_CATEGORIES = frozenset({"dresses", "tops", "bottoms", "outerwear", "ethnic", "activewear"})
_APPAREL = APPAREL_CATEGORIES


def _color_key(p: dict) -> str:
    return str(p.get("color") or "").strip().lower()


def _score(
    p: dict,
    bucket: str,
    vibe: str,
    term_map: dict[str, list[str]],
    *,
    color: str | None = None,
    prefer_neutral: bool = False,
) -> float:
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
    pc = _color_key(p)
    if prefer_neutral and pc and (pc in _NEUTRALS or any(n in pc for n in _NEUTRALS)):
        score += 1.4
    if color:
        hc = color.strip().lower()
        if pc and hc and (pc == hc or hc in pc or pc in hc):
            score += 2.2
    return score


def _pick(
    candidates: list[dict],
    bucket: str,
    vibe: str,
    budget_max: float | None,
    term_map: dict[str, list[str]],
    used_ids: set[str],
    *,
    color: str | None = None,
    prefer_neutral: bool = False,
) -> dict | None:
    pool = [p for p in candidates if p["id"] not in used_ids]
    if budget_max:
        affordable = [p for p in pool if _as_number(p.get("price")) <= budget_max]
        if affordable:
            pool = affordable
    if not pool:
        return None
    scored = sorted(
        pool,
        key=lambda p: _score(
            p, bucket, vibe, term_map, color=color, prefer_neutral=prefer_neutral,
        ),
        reverse=True,
    )
    top = scored[:max(3, len(scored) // 5)]
    return random.choice(top)


def _card(p: dict) -> dict:
    card = {
        "id":            p["id"],
        "name":          p["name"],
        "category":      p.get("category", "other"),
        "color":         p.get("color"),
        "price":         p.get("price"),
        "currency":      p.get("currency", "INR"),
        "image_url":     p.get("image_url"),
        "affiliate_url": p.get("affiliate_url"),
    }
    if p.get("brand"):
        card["brand"] = p["brand"]
    if p.get("source"):
        card["source"] = p["source"]
    return card


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


_LOOK_TITLES = {
    "dresses": "The finished dress look",
    "ethnic": "Festive, head to toe",
    "tops": "The complete separates look",
    "outerwear": "The layered edit",
    "bottoms": "The tailored head-to-toe",
    "activewear": "The off-duty uniform",
    "shoes": "Styled from the shoes up",
    "bags": "The bag that finishes it",
}

_OCCASION_LOOK_NAMES = {
    "wedding": "Wedding-guest edit",
    "sangeet": "Sangeet edit",
    "festive": "Festive head-to-toe",
    "cocktail": "Cocktail edit",
    "party": "Night-out edit",
    "office": "Desk-to-dinner look",
    "date": "Date-night edit",
    "casual": "Everyday full look",
}


def _look_name(hero_cat: str, bucket: str, override: str | None) -> str:
    if override:
        return override
    if bucket != "casual":
        return _OCCASION_LOOK_NAMES.get(bucket, "The full look")
    return _LOOK_TITLES.get(hero_cat, "The full look")


def build_look_around(
    hero: dict,
    catalog: Iterable[dict],
    *,
    occasion: str = "casual",
    vibe: str = "",
    exclude_ids: set[str] | None = None,
    name: str | None = None,
) -> dict | None:
    """One complete, shoppable look with ``hero`` as the anchor.

    Always tries for outfit + shoes + bag (+ accessory). Returns None when the
    catalog cannot finish at least two pieces around the hero.
    """
    if not hero or not hero.get("id") or not hero.get("image_url"):
        return None
    bucket = _occasion_bucket(occasion)
    exclude = set(exclude_ids or set())
    exclude.add(hero["id"])
    hero_color = hero.get("color")

    products = [
        p for p in catalog
        if p.get("id") and p.get("image_url") and p.get("affiliate_url")
        and p["id"] not in exclude
        and not _is_excluded(p, bucket)
    ]
    by_cat: dict[str, list[dict]] = {}
    for p in products:
        by_cat.setdefault(p.get("category", "other"), []).append(p)

    hero_cat = (hero.get("category") or "other").lower()
    outfit_items: list[dict] = []
    shoe = bag = accessory = None

    def pick(cat: str, terms: dict[str, list[str]], *, neutral: bool = False) -> dict | None:
        return _pick(
            by_cat.get(cat, []), bucket, vibe, None, terms, exclude,
            color=hero_color, prefer_neutral=neutral,
        )

    if hero_cat in ("dresses", "ethnic"):
        outfit_items = [hero]
    elif hero_cat in ("tops", "outerwear", "activewear"):
        outfit_items = [hero]
        bottom = pick("bottoms", _STYLE_TERMS)
        if bottom:
            outfit_items.append(bottom)
            exclude.add(bottom["id"])
    elif hero_cat == "bottoms":
        top = pick("tops", _STYLE_TERMS)
        if top:
            outfit_items.append(top)
            exclude.add(top["id"])
        outfit_items.append(hero)
    else:
        dress = pick("dresses", _STYLE_TERMS)
        if dress:
            outfit_items = [dress]
            exclude.add(dress["id"])
        else:
            top = pick("tops", _STYLE_TERMS)
            bottom = pick("bottoms", _STYLE_TERMS)
            outfit_items = [p for p in (top, bottom) if p]
            exclude.update(p["id"] for p in outfit_items)
        if hero_cat == "shoes":
            shoe = hero
        elif hero_cat == "bags":
            bag = hero
        else:
            accessory = hero

    if not outfit_items:
        return None

    if shoe is None:
        shoe = pick("shoes", _SHOE_TERMS, neutral=True)
        if shoe:
            exclude.add(shoe["id"])
    if bag is None:
        bag = pick("bags", _BAG_TERMS, neutral=True)
        if bag:
            exclude.add(bag["id"])
    if accessory is None:
        accessory = pick("accessories", _ACCESSORY_TERMS)

    all_items = list(outfit_items)
    for extra in (shoe, bag, accessory):
        if extra and extra["id"] not in {p["id"] for p in all_items}:
            all_items.append(extra)
    if len(all_items) < 2:
        return None

    total = round(sum(_as_number(p.get("price")) for p in all_items), 2)
    short = (hero.get("name") or "this piece").split(",")[0].strip()[:52]
    n = len(all_items)
    return {
        "id": f"look-{hero['id'][:16]}",
        "name": _look_name(hero_cat, bucket, name),
        "rationale": (
            f"{n} pieces styled around {short} — shoes, bag, and finishers "
            f"chosen to work as one look, so you can take it all."
        ),
        "total_price": total,
        "occasion": occasion,
        "items": [_card(p) for p in all_items],
        "slots": {
            "outfit": [_card(p) for p in outfit_items],
            "shoes": _card(shoe) if shoe else None,
            "bag": _card(bag) if bag else None,
            "accessories": _card(accessory) if accessory else None,
        },
    }
