"""Deterministic 2-on-brief + 1 curiosity curation and shopping-buddy complements.

Keeps Mira on the shopper's ask while surfacing one elevated / accent pick the
model can frame as a stretch — never invented outside the catalog.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from functools import lru_cache
from typing import Any


# Everyday words → catalog category (aligned with stylist / live_server intent).
_CATEGORY_SYNONYMS: dict[str, tuple[str, ...]] = {
    "shoes": ("shoes", "shoe", "sneaker", "sneakers", "trainers", "heels", "boots",
              "sandals", "loafers", "flats"),
    "tops": ("tops", "top", "shirt", "tee", "t-shirt", "blouse", "sweater", "jumper",
             "turtleneck", "hoodie"),
    "bottoms": ("bottoms", "bottom", "jeans", "trousers", "pants", "shorts", "skirt",
                "leggings", "chinos"),
    "dresses": ("dresses", "dress", "gown", "frock"),
    "outerwear": ("outerwear", "jacket", "coat", "blazer", "parka", "cardigan"),
    "bags": ("bags", "bag", "tote", "clutch", "purse", "handbag"),
    "accessories": ("accessories", "accessory", "scarf", "belt", "hat", "cap",
                    "jewelry", "jewellery", "necklace", "sunglasses", "glasses",
                    "watch", "earrings"),
    "ethnic": ("ethnic", "kurti", "kurta", "saree", "lehenga", "anarkali", "salwar"),
    "activewear": ("activewear", "athletic", "gym", "workout", "sports"),
}

_COLOR_ALIASES: dict[str, tuple[str, ...]] = {
    # Listed first so a mixed-print ask never falls through to a single hue.
    "multicolor": ("multicolor", "multicolour", "multicolored", "multicoloured",
                   "multi-color", "multi-colour", "multi color", "multi colour",
                   "multi", "multitone", "colorblock", "colourblock",
                   "color block", "colour block", "rainbow", "printed", "print",
                   "floral", "patterned", "tie dye", "tie-dye", "striped"),
    "purple": ("purple", "violet", "lavender", "lilac", "plum", "magenta", "mauve"),
    "red": ("red", "burgundy", "crimson", "maroon", "scarlet", "wine"),
    "blue": ("blue", "navy", "indigo", "cobalt", "teal", "azure"),
    "green": ("green", "emerald", "olive", "sage", "forest", "mint"),
    "black": ("black", "charcoal", "onyx"),
    "white": ("white", "ivory", "cream", "off-white", "off white"),
    "pink": ("pink", "blush", "rose", "fuchsia", "dusty pink"),
    "yellow": ("yellow", "mustard", "gold", "amber"),
    "orange": ("orange", "rust", "coral", "terracotta"),
    "brown": ("brown", "tan", "camel", "beige", "khaki", "nude"),
    "grey": ("grey", "gray", "silver", "slate"),
}

# Accent colors that create a "wow" contrast while staying fashion-sensible.
_ACCENT_FOR: dict[str, tuple[str, ...]] = {
    "purple": ("red", "gold", "black", "emerald", "pink"),
    "red": ("black", "gold", "white", "navy"),
    "blue": ("white", "gold", "red", "cream"),
    "green": ("gold", "cream", "black", "burgundy"),
    "black": ("red", "gold", "white", "emerald"),
    "white": ("black", "red", "navy", "gold"),
    "pink": ("red", "black", "gold", "burgundy"),
    "yellow": ("black", "white", "navy"),
    "orange": ("black", "cream", "navy"),
    "brown": ("cream", "black", "gold"),
    "grey": ("red", "black", "white", "burgundy"),
}

# After engagement on a hero category, suggest these companions.
_COMPLEMENTS: dict[str, tuple[str, ...]] = {
    "bottoms": ("tops", "accessories", "shoes", "bags", "outerwear"),
    "tops": ("bottoms", "accessories", "shoes", "bags", "outerwear"),
    "dresses": ("shoes", "bags", "accessories", "outerwear"),
    "ethnic": ("shoes", "bags", "accessories"),
    "shoes": ("tops", "bottoms", "accessories", "bags"),
    "bags": ("tops", "dresses", "accessories", "shoes"),
    "accessories": ("tops", "dresses", "bottoms", "shoes"),
    "outerwear": ("tops", "bottoms", "dresses", "accessories"),
    "activewear": ("shoes", "accessories", "tops"),
}


def detect_category(text: str) -> str | None:
    t = (text or "").lower()
    for cat, words in _CATEGORY_SYNONYMS.items():
        if any(w in t for w in words):
            return cat
    return None


@lru_cache(maxsize=1024)
def _alias_re(alias: str) -> re.Pattern:
    """Whole-word matcher, tolerating a plural s.

    Substring matching silently mis-reads asks: "multicoloured" contains "red",
    so a request for multicoloured dresses came back as red ones.
    """
    return re.compile(rf"\b{re.escape(alias)}s?\b")


def _mentions(text: str, aliases: Iterable[str]) -> bool:
    return any(_alias_re(a).search(text) for a in aliases)


def detect_color_key(text: str) -> str | None:
    t = (text or "").lower()
    for key, aliases in _COLOR_ALIASES.items():
        if _mentions(t, aliases):
            return key
    return None


# Feed importers write "multi" when they could not read a colour at all, so it
# means "unknown", not "multicoloured" — 74% of the catalog carries it. Treating it
# as a colour claims 778 items are multicoloured when only ~40 are, and lets a
# plain sage-green dress answer a multicoloured ask.
_UNKNOWN_COLOR_VALUES = frozenset({"", "multi", "multicolor", "multicolour", "assorted", "various"})

# A real pattern has to be visible in the product name to count as multicoloured.
_MULTICOLOR_CUES: tuple[str, ...] = (
    "multicolor", "multicolour", "multicolored", "multicoloured", "multi-color",
    "multi-colour", "colorblock", "colourblock", "color block", "colour block",
    "rainbow", "printed", "print", "floral", "patterned", "pattern", "tie dye",
    "tie-dye", "striped", "stripe", "paisley", "plaid", "checked", "polka",
    "graphic", "abstract", "animal print", "leopard", "geometric",
)


def is_color_known(product: dict) -> bool:
    """False when the feed gave us no usable colour for this product."""
    raw = (product.get("color") or "").strip().lower()
    if raw not in _UNKNOWN_COLOR_VALUES:
        return True
    name = (product.get("name") or "").lower()
    if _mentions(name, _MULTICOLOR_CUES):
        return True
    return any(
        _mentions(name, aliases)
        for key, aliases in _COLOR_ALIASES.items()
        if key != "multicolor"
    )


def _color_matches(product: dict, color_key: str | None) -> bool:
    if not color_key:
        return False
    raw = (product.get("color") or "").strip().lower()
    name = (product.get("name") or "").lower()
    if color_key == "multicolor":
        return _mentions(name, _MULTICOLOR_CUES)
    known = "" if raw in _UNKNOWN_COLOR_VALUES else raw
    return _mentions(f"{known} {name}", _COLOR_ALIASES.get(color_key, ()))


def _as_price(p: dict) -> float:
    try:
        return float(p.get("price") or 0)
    except (TypeError, ValueError):
        return 0.0


def _tag(p: dict, role: str) -> dict:
    out = dict(p)
    out["mix_role"] = role
    return out


def build_curation_mix(
    catalog: Iterable[dict],
    query: str,
    *,
    n: int = 3,
    exclude_ids: set[str] | None = None,
    category: str | None = None,
    color_key: str | None = None,
) -> list[dict]:
    """Return up to n products: mostly on-brief, with at most one curiosity pick.

    Curiosity = same category (when known) + accent color or higher price tier.
    If no curiosity candidate exists, returns only on-brief picks.
    """
    exclude = exclude_ids or set()
    cat = category or detect_category(query)
    color = color_key or detect_color_key(query)

    pool = [p for p in catalog if p.get("id") and p["id"] not in exclude]
    if cat:
        cat_pool = [p for p in pool if (p.get("category") or "").lower() == cat]
        if cat_pool:
            pool = cat_pool

    on_brief = [p for p in pool if _color_matches(p, color)] if color else list(pool)
    if not on_brief:
        on_brief = list(pool)

    # Prefer mid-premium on-brief (not the cheapest dump).
    on_brief_sorted = sorted(on_brief, key=_as_price, reverse=True)
    # Spread: take from top half for quality bias.
    mid = on_brief_sorted[: max(3, len(on_brief_sorted) // 2)] or on_brief_sorted
    brief_picks: list[dict] = []
    for p in mid:
        brief_picks.append(_tag(p, "on_brief"))
        if len(brief_picks) >= max(1, n - 1):
            break
    if len(brief_picks) < max(1, n - 1):
        seen = {p["id"] for p in brief_picks}
        for p in on_brief_sorted:
            if p["id"] in seen:
                continue
            brief_picks.append(_tag(p, "on_brief"))
            if len(brief_picks) >= max(1, n - 1):
                break

    used = {p["id"] for p in brief_picks}
    curiosity = _pick_curiosity(pool, used, color, brief_picks)

    result = list(brief_picks)
    if curiosity and len(result) < n:
        result.append(curiosity)
    elif not curiosity and len(result) < n:
        for p in on_brief_sorted:
            if p["id"] in used:
                continue
            result.append(_tag(p, "on_brief"))
            if len(result) >= n:
                break
    return result[:n]


def _pick_curiosity(
    pool: list[dict],
    used: set[str],
    color_key: str | None,
    brief_picks: list[dict],
) -> dict | None:
    accents = _ACCENT_FOR.get(color_key or "", ())
    avg_brief = (
        sum(_as_price(p) for p in brief_picks) / len(brief_picks)
        if brief_picks else 0.0
    )

    accent_hits: list[dict] = []
    premium_hits: list[dict] = []
    for p in pool:
        if p["id"] in used:
            continue
        blob = f"{p.get('color') or ''} {p.get('name') or ''}".lower()
        if accents and any(
            a in blob
            for key in accents
            for a in _COLOR_ALIASES.get(key, (key,))
        ):
            accent_hits.append(p)
            continue
        if avg_brief and _as_price(p) >= avg_brief * 1.25:
            premium_hits.append(p)
        elif not avg_brief and not accents:
            premium_hits.append(p)

    pick = None
    if accent_hits:
        pick = max(accent_hits, key=_as_price)
    elif premium_hits:
        pick = max(premium_hits, key=_as_price)
    if pick is None:
        return None
    return _tag(pick, "curiosity")


def complements_for(
    hero: dict,
    catalog: Iterable[dict],
    *,
    n: int = 3,
    exclude_ids: set[str] | None = None,
) -> list[dict]:
    """Pick complementary pieces to complete the look around a loved/try-on hero."""
    exclude = set(exclude_ids or set())
    hid = hero.get("id")
    if hid:
        exclude.add(hid)
    hero_cat = (hero.get("category") or "").lower()
    targets = _COMPLEMENTS.get(hero_cat, ("tops", "accessories", "shoes", "bags"))

    by_cat: dict[str, list[dict]] = {}
    for p in catalog:
        if not p.get("id") or p["id"] in exclude:
            continue
        by_cat.setdefault((p.get("category") or "other").lower(), []).append(p)

    picks: list[dict] = []
    for cat in targets:
        candidates = by_cat.get(cat) or []
        if not candidates:
            continue
        # Prefer slightly elevated price within the complement category.
        best = max(candidates, key=_as_price)
        picks.append(_tag(best, "complement"))
        exclude.add(best["id"])
        if len(picks) >= n:
            break
    return picks


def render_mix_prompt(products: list[dict]) -> str:
    """Compact grounding lines; curiosity picks are explicitly tagged for the LLM.

    Price format matches catalog.to_prompt_lines (`$N`) so existing grounding
    parsers and offline tests stay consistent.
    """
    lines = []
    for p in products:
        role = p.get("mix_role") or "on_brief"
        tag = " | CURIOSITY/elevated" if role == "curiosity" else (
            " | COMPLEMENT" if role == "complement" else ""
        )
        styles = p.get("style") or []
        style_s = ", ".join(styles) if isinstance(styles, list) else str(styles)
        gender = p.get("gender") or ""
        gender_bit = f" | {gender}" if gender else ""
        lines.append(
            f'- {p.get("id")} | {p.get("name")} | {p.get("category")} | '
            f'{p.get("color")} | ${p.get("price")} | {style_s}{gender_bit}{tag}'
        )
    return "\n".join(lines)


def majority_color_ok(products: list[dict], color_key: str, *, min_share: float = 0.5) -> bool:
    """True if at least min_share of products match the asked color (eval helper)."""
    if not products or not color_key:
        return True
    hits = sum(1 for p in products if _color_matches(p, color_key))
    return (hits / len(products)) >= min_share


def card_fields(p: dict, affiliate_url: str | None = None) -> dict[str, Any]:
    """WS/UI product payload including mix_role when present."""
    out = {
        "id": p["id"],
        "name": p["name"],
        "category": p.get("category"),
        "color": p.get("color"),
        "price": p.get("price"),
        "currency": p.get("currency", "INR"),
        "image_url": p.get("image_url"),
        "affiliate_url": affiliate_url if affiliate_url is not None else p.get("affiliate_url"),
        "brand": p.get("brand"),
    }
    if p.get("mix_role"):
        out["mix_role"] = p["mix_role"]
    return out


def _brand_index(catalog: Iterable[dict]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for p in catalog:
        b = (p.get("brand") or "").strip()
        if not b:
            continue
        key = b.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(b)
    # Longer names first so "Tommy Hilfiger" wins over "Tommy"
    out.sort(key=lambda s: len(s), reverse=True)
    return out


def detect_brand(text: str, catalog: Iterable[dict] | None = None) -> str | None:
    """Match a brand mentioned in free text (e.g. 'tommy' → Tommy Hilfiger).

    Whole-word matching only — substring matching made one-letter brands like
    "W" (W for Woman) hijack every sentence containing that letter.
    """
    t = (text or "").lower()
    if not t:
        return None
    brands = _brand_index(catalog or [])
    for b in brands:
        bl = b.lower()
        if re.search(rf"\b{re.escape(bl)}\b", t):
            return b
        # first token shorthand: "tommy" → Tommy Hilfiger
        first = bl.split()[0]
        if len(first) >= 4 and re.search(rf"\b{re.escape(first)}\b", t):
            return b
    return None


def _matches_color(p: dict, color_key: str | None) -> bool:
    return _color_matches(p, color_key)


def resolve_shop_query(
    catalog: Iterable[dict],
    query: str,
    *,
    n: int = 6,
    exclude_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Deterministic catalog answer for 'show me red dresses from tommy'.

    Progressive relaxation:
      brand+category+color → brand+category → category+color → category → brand
    Returns products + notes so Mira can be honest when a facet is missing.
    """
    exclude = exclude_ids or set()
    products = [p for p in catalog if p.get("id") and p["id"] not in exclude]
    brand = detect_brand(query, products)
    category = detect_category(query)
    color = detect_color_key(query)

    def pool(**want) -> list[dict]:
        out = []
        for p in products:
            if want.get("brand") and (p.get("brand") or "").lower() != want["brand"].lower():
                continue
            if want.get("category") and (p.get("category") or "").lower() != want["category"]:
                continue
            if want.get("color") and not _matches_color(p, want["color"]):
                continue
            out.append(p)
        return out

    notes: list[str] = []
    matched: list[dict] = []
    mode = "none"

    attempts = []
    if brand and category and color:
        attempts.append(("brand_cat_color", {"brand": brand, "category": category, "color": color}))
    if brand and category:
        attempts.append(("brand_cat", {"brand": brand, "category": category}))
    if category and color:
        attempts.append(("cat_color", {"category": category, "color": color}))
    if brand and color:
        attempts.append(("brand_color", {"brand": brand, "color": color}))
    if category:
        attempts.append(("category", {"category": category}))
    if brand:
        attempts.append(("brand", {"brand": brand}))
    if color:
        attempts.append(("color", {"color": color}))

    for mode_name, filt in attempts:
        hits = pool(**filt)
        if hits:
            matched = hits
            mode = mode_name
            break

    if brand and color and mode in ("brand_cat", "brand") and category:
        notes.append(
            f"No {color} {category} from {brand} in the catalog right now — "
            f"showing {brand} {category} instead."
        )
    elif brand and color and mode == "brand_cat":
        notes.append(
            f"No exact {color} pieces from {brand} tagged that way — "
            f"showing {brand} {category or 'picks'}."
        )
    elif brand and mode in ("cat_color", "category") and not matched:
        notes.append(f"I don't carry {brand} yet.")
    elif brand and mode in ("cat_color", "category"):
        # Had brand in query but fell through without brand — shouldn't happen if brand pool empty
        pass

    # Prefer curation mix when we have a category-ish ask
    if matched and category and mode in ("brand_cat", "brand_cat_color", "cat_color", "category"):
        picked = build_curation_mix(
            matched, query, n=min(n, 3), category=category, color_key=color if "color" in mode else None,
        )
        # fill remaining from matched
        seen = {p["id"] for p in picked}
        for p in matched:
            if p["id"] in seen:
                continue
            picked.append(_tag(p, "on_brief"))
            if len(picked) >= n:
                break
        matched = picked
    else:
        matched = [_tag(p, "on_brief") for p in matched[:n]]

    return {
        "brand": brand,
        "category": category,
        "color": color,
        "mode": mode,
        "notes": notes,
        "products": matched[:n],
    }
