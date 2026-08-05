"""Deterministic, fast (<10 ms) search agent for typed shopping asks.

Turns free text like "show me 5 red dresses of Tommy under 3000" into a
structured catalog query and returns ranked results — without ever waiting
on the LLM. This is what guarantees the sub-3-second chat answer:

  Speed design
  ------------
  1. The full catalog already lives in memory (product_store TTLCache +
     live_server._CATALOG) — no network on this path, ever.
  2. A small LRU query cache short-circuits repeat questions (same text,
     same session exclusions) to a dict lookup.
  3. Ranking is a single O(n) pass over ~1-5K products (sub-millisecond).
  The LLM (Gemini Live) only ADDS colour commentary afterwards; the cards
  and the honest availability note are already on screen.

  Query understanding
  -------------------
  count      "show me 5 …", "a few", "a couple"           → how many cards
  brand      "of tommy", "from Zara"                      → catalog brands
  category   "dresses", "sneakers", "kurti", …            → catalog category
  color      "red" (incl. burgundy/maroon aliases), …     → color family
  price      "under 3000", "below 2k", "between 1k and 5k" → price bounds
  sort       "best selling / top rated"  → popularity (default)
             "cheapest"                  → price ascending
             "premium / most expensive"  → price descending
             "newest / latest"           → recency
  recommend  "recommend something for me", "surprise me"  → recommender path

  Availability honesty
  --------------------
  Facets relax progressively (brand+cat+color → brand+cat → …) with a note
  explaining what was missing. When nothing matches at all — or paging has
  exhausted the pool — `message` carries the shopper-facing apology:
  "Sorry — we don't have any more … right now."
"""
from __future__ import annotations

import re
import time
from collections import OrderedDict
from collections.abc import Iterable
from math import log1p
from typing import Any

from curation_mix import (
    _CATEGORY_SYNONYMS,
    _COLOR_ALIASES,
    _color_matches,
    detect_brand,
    detect_category,
    detect_color_key,
)

DEFAULT_N = 6
MAX_N = 12

# ---------------------------------------------------------------------------
# Popularity — proxy for "highly selling"
# ---------------------------------------------------------------------------

_RATING_PRIOR = 3.6   # neutral rating for unrated items
_PRIOR_WEIGHT = 12.0  # pseudo-reviews pulling small samples toward the prior


def popularity_score(p: dict) -> float:
    """Bayesian-smoothed rating × review volume — best proxy for units sold.

    A 4.3★ item with 8,000 ratings outranks a 5.0★ item with 2 ratings;
    unrated items sit at the prior so they aren't buried entirely.
    """
    try:
        rating = float(p.get("rating") or 0.0)
    except (TypeError, ValueError):
        rating = 0.0
    try:
        votes = float(p.get("ratings_total") or 0.0)
    except (TypeError, ValueError):
        votes = 0.0
    if rating <= 0.0:
        rating, votes = _RATING_PRIOR, 0.0
    smoothed = (rating * votes + _RATING_PRIOR * _PRIOR_WEIGHT) / (votes + _PRIOR_WEIGHT)
    return smoothed * (1.0 + log1p(votes))


# ---------------------------------------------------------------------------
# Query parsing
# ---------------------------------------------------------------------------

_WORD_COUNTS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "a couple": 2, "couple of": 2, "a few": 3, "few": 3, "a dozen": 12,
}

_PRICE_BETWEEN_RE = re.compile(
    r"between\s*(?:rs\.?|inr|₹|\$)?\s*([\d,.]+)\s*(k|thousand)?\s*"
    r"(?:and|to|-)\s*(?:rs\.?|inr|₹|\$)?\s*([\d,.]+)\s*(k|thousand)?",
    re.IGNORECASE,
)
_PRICE_MAX_RE = re.compile(
    r"(?:under|below|less than|within|upto|up to|max(?:imum)?|budget of|no more than)"
    r"\s*(?:rs\.?|inr|₹|\$)?\s*([\d,.]+)\s*(k|thousand)?",
    re.IGNORECASE,
)
_PRICE_MIN_RE = re.compile(
    r"(?:over|above|more than|at least|starting|from)\s*(?:rs\.?|inr|₹)\s*([\d,.]+)\s*(k|thousand)?"
    r"|(?:over|above|more than|at least)\s*([\d,.]{3,})\s*(k|thousand)?",
    re.IGNORECASE,
)

_SORT_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("popular", ("best sell", "bestsell", "top sell", "most popular", "popular",
                 "best rated", "top rated", "highest rated", "trending", "hot ")),
    ("price_asc", ("cheapest", "cheap ", "lowest price", "low price", "affordable",
                   "least expensive", "low to high")),
    ("price_desc", ("most expensive", "premium", "luxury", "high end", "high-end",
                    "priciest", "high to low")),
    ("newest", ("newest", "latest", "new in", "new arrivals", "recent")),
)

# "from <name>" where <name> isn't a catalog brand → honest "don't carry it" note.
_BRAND_ASK_RE = re.compile(
    r"\b(?:from|by|of)\s+([a-z][\w&'.-]*(?:\s+[a-z][\w&'.-]*){0,2})", re.IGNORECASE
)
_BRAND_ASK_BREAK = {
    "under", "below", "over", "above", "between", "in", "with", "for", "and",
    "or", "that", "please", "around", "about", "upto", "max",
}
_BRAND_ASK_STOP = {
    "my", "me", "the", "your", "our", "their", "this", "a", "an", "you",
    "wardrobe", "amazon", "india", "silk", "cotton", "linen", "denim", "leather",
}


def detect_unknown_brand(text: str, known_brand: str | None) -> str | None:
    """Name the brand the user asked for when it's not in the catalog."""
    if known_brand:
        return None
    m = _BRAND_ASK_RE.search((text or "").lower())
    if not m:
        return None
    words: list[str] = []
    for w in m.group(1).split():
        if w in _BRAND_ASK_BREAK or any(ch.isdigit() for ch in w):
            break
        words.append(w)
        if len(words) >= 2:
            break
    if not words:
        return None
    first = words[0]
    if first in _BRAND_ASK_STOP or detect_category(first) or detect_color_key(first):
        return None
    return " ".join(words)


_RECOMMEND_PATTERNS = (
    "recommend", "suggest something", "suggest me", "for me", "surprise me",
    "what should i buy", "what should i get", "what would you pick",
    "picks for me", "based on my", "my taste", "my style", "you know me",
    "something i'd like", "something i would like", "personalised", "personalized",
)


def _to_amount(num: str, kilo: str | None) -> float:
    val = float(num.replace(",", ""))
    if kilo:
        val *= 1000.0
    return val


def parse_query(text: str) -> dict[str, Any]:
    """Extract count / price bounds / sort / recommend intent from free text."""
    t = (text or "").lower()

    price_min: float | None = None
    price_max: float | None = None
    stripped = t
    m = _PRICE_BETWEEN_RE.search(stripped)
    if m:
        lo = _to_amount(m.group(1), m.group(2))
        hi = _to_amount(m.group(3), m.group(4))
        price_min, price_max = min(lo, hi), max(lo, hi)
        stripped = stripped.replace(m.group(0), " ")
    m = _PRICE_MAX_RE.search(stripped)
    if m:
        price_max = _to_amount(m.group(1), m.group(2))
        stripped = stripped.replace(m.group(0), " ")
    m = _PRICE_MIN_RE.search(stripped)
    if m:
        num = m.group(1) or m.group(3)
        kilo = m.group(2) or m.group(4)
        if num:
            price_min = _to_amount(num, kilo)
            stripped = stripped.replace(m.group(0), " ")

    count: int | None = None
    m = re.search(r"\b(\d{1,2})\b", stripped)
    if m and 1 <= int(m.group(1)) <= 20:
        count = min(int(m.group(1)), MAX_N)
    if count is None:
        for phrase, val in _WORD_COUNTS.items():
            if re.search(rf"\b{re.escape(phrase)}\b", stripped):
                count = val
                break

    sort: str | None = None
    for key, phrases in _SORT_PATTERNS:
        if any(ph in t for ph in phrases):
            sort = key
            break

    recommend = any(ph in t for ph in _RECOMMEND_PATTERNS)

    return {
        "count": count,
        "price_min": price_min,
        "price_max": price_max,
        "sort": sort,            # None → caller defaults to popularity
        "recommend": recommend,
    }


# ---------------------------------------------------------------------------
# Retrieval + ranking
# ---------------------------------------------------------------------------

def _price_of(p: dict) -> float:
    try:
        return float(p.get("price") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _in_price(p: dict, lo: float | None, hi: float | None) -> bool:
    price = _price_of(p)
    if lo is not None and price < lo:
        return False
    if hi is not None and price > hi:
        return False
    return True


def _rank(products: list[dict], sort: str) -> list[dict]:
    if sort == "price_asc":
        return sorted(products, key=_price_of)
    if sort == "price_desc":
        return sorted(products, key=_price_of, reverse=True)
    if sort == "newest":
        return sorted(products, key=lambda p: p.get("created_at") or "", reverse=True)
    return sorted(products, key=popularity_score, reverse=True)


def _dedupe(products: list[dict]) -> list[dict]:
    """Drop same-name+color duplicates (feed imports often repeat items)."""
    seen: set[tuple] = set()
    out = []
    for p in products:
        key = ((p.get("name") or "").strip().lower(), (p.get("color") or "").lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _facet_desc(brand, category, color, price_max=None, price_min=None) -> str:
    bits = []
    if color:
        bits.append(color)
    bits.append(category or "products")
    desc = " ".join(bits)
    if brand:
        desc += f" from {brand}"
    if price_max is not None and price_min is not None:
        desc += f" between ₹{price_min:,.0f} and ₹{price_max:,.0f}"
    elif price_max is not None:
        desc += f" under ₹{price_max:,.0f}"
    elif price_min is not None:
        desc += f" over ₹{price_min:,.0f}"
    return desc


def _matched_category_terms(text: str) -> list[str]:
    """The literal words that triggered category detection ('kurtas' → kurta)."""
    t = (text or "").lower()
    terms = [w for words in _CATEGORY_SYNONYMS.values() for w in words if w in t]
    return sorted(terms, key=len, reverse=True)


def _label(brand, color, category, sort, sort_explicit, price_max, mode, term=None) -> str:
    """UI header describing what was ACTUALLY matched — never a relaxed facet."""
    bits = []
    if brand and "brand" in mode:
        bits.append(brand)
    if color and "color" in mode:
        bits.append(color.title())
    if mode == "name_match" and term:
        bits.append(term.rstrip("s").title() + "s")
    elif category and ("cat" in mode or mode == "category"):
        bits.append(category.title())
    if sort_explicit:
        bits.append({
            "popular": "Best Selling", "price_asc": "Lowest Price",
            "price_desc": "Premium", "newest": "New In",
        }.get(sort, ""))
    if price_max is not None:
        bits.append(f"Under ₹{price_max:,.0f}")
    return " · ".join(b for b in bits if b) or "Picks for you"


# ---------------------------------------------------------------------------
# LRU query cache — repeat asks answer in ~0 ms
# ---------------------------------------------------------------------------

_CACHE_TTL = 90.0
_CACHE_MAX = 256
_query_cache: OrderedDict[tuple, tuple[float, dict]] = OrderedDict()


def _cache_key(text: str, exclude_ids: set[str], n: int, catalog: list) -> tuple:
    return (
        re.sub(r"\s+", " ", (text or "").strip().lower()),
        frozenset(exclude_ids),
        n,
        len(catalog),
        id(catalog),  # new object after background refresh → old entries never hit
    )


def _cache_get(key: tuple) -> dict | None:
    hit = _query_cache.get(key)
    if not hit:
        return None
    ts, result = hit
    if time.monotonic() - ts > _CACHE_TTL:
        _query_cache.pop(key, None)
        return None
    _query_cache.move_to_end(key)
    return {**result, "products": [dict(p) for p in result["products"]], "cached": True}


def _cache_put(key: tuple, result: dict) -> None:
    _query_cache[key] = (time.monotonic(), result)
    _query_cache.move_to_end(key)
    while len(_query_cache) > _CACHE_MAX:
        _query_cache.popitem(last=False)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def answer(
    catalog: list[dict],
    text: str,
    *,
    exclude_ids: set[str] | None = None,
    default_n: int = DEFAULT_N,
) -> dict[str, Any]:
    """Resolve a typed shopping ask against the in-memory catalog.

    Returns a dict with:
      products    ranked cards (tagged mix_role=on_brief)
      label       short UI header ("Tommy Hilfiger · Red · Dresses")
      notes       honest relaxation notes for Mira to say
      message     shopper-facing apology when nothing matches / pool exhausted
      mode        which facet combination matched ("none" = not a shop ask)
      recommend   True when the user asked for personal recommendations
      elapsed_ms  wall time of this resolution (observability for the 3s SLA)
    """
    t0 = time.perf_counter()
    exclude = exclude_ids or set()

    parsed = parse_query(text)
    n = parsed["count"] or default_n
    sort_explicit = parsed["sort"] is not None
    sort = parsed["sort"] or "popular"
    price_min, price_max = parsed["price_min"], parsed["price_max"]

    key = _cache_key(text, exclude, n, catalog)
    cached = _cache_get(key)
    if cached is not None:
        cached["elapsed_ms"] = (time.perf_counter() - t0) * 1000.0
        return cached

    base = [p for p in catalog if p.get("id") and p["id"] not in exclude]
    brand = detect_brand(text, base or catalog)
    category = detect_category(text)
    color = detect_color_key(text)

    has_price = price_min is not None or price_max is not None
    actionable = bool(brand or category or color or sort_explicit
                      or parsed["count"] or has_price or parsed["recommend"])

    result: dict[str, Any] = {
        "brand": brand, "category": category, "color": color,
        "count": n, "sort": sort, "price_min": price_min, "price_max": price_max,
        "recommend": parsed["recommend"],
        "mode": "none", "notes": [], "message": None, "label": None,
        "products": [],
    }
    if not actionable:
        result["elapsed_ms"] = (time.perf_counter() - t0) * 1000.0
        return result

    def pool(products: list[dict], **want) -> list[dict]:
        out = []
        for p in products:
            if want.get("brand") and (p.get("brand") or "").lower() != want["brand"].lower():
                continue
            if want.get("category") and (p.get("category") or "").lower() != want["category"]:
                continue
            if want.get("color") and not _color_matches(p, want["color"]):
                continue
            out.append(p)
        return out

    attempts: list[tuple[str, dict]] = []
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
    if not attempts:
        # Sort/count/price-only ask ("show me best sellers under 2000")
        attempts.append(("all", {}))

    priced = [p for p in base if _in_price(p, price_min, price_max)] if has_price else base

    def _name_term_search(products: list[dict]) -> tuple[list[dict], str | None]:
        """Match the literal product word in names ('kurta' items may be
        categorised as dresses/tops — don't lose them to the facet taxonomy)."""
        for term in _matched_category_terms(text):
            stem = term.rstrip("s")
            hits = [p for p in products if stem in (p.get("name") or "").lower()]
            if hits:
                if color:
                    color_hits = [p for p in hits if _color_matches(p, color)]
                    if color_hits:
                        hits = color_hits
                return hits, term
        return [], None

    matched: list[dict] = []
    mode = "none"
    matched_term: str | None = None
    price_relaxed = False
    for mode_name, filt in attempts:
        hits = pool(priced, **filt)
        if hits:
            matched, mode = hits, mode_name
            break
    if not matched and category:
        hits, term = _name_term_search(priced)
        if hits:
            matched, mode, matched_term = hits, "name_match", term
    if not matched and has_price:
        # Nothing within budget — retry without the price bound, flag honesty note.
        for mode_name, filt in attempts:
            hits = pool(base, **filt)
            if hits:
                matched, mode, price_relaxed = hits, mode_name, True
                break
        if not matched and category:
            hits, term = _name_term_search(base)
            if hits:
                matched, mode, matched_term = hits, "name_match", term
                price_relaxed = True

    unknown_brand = detect_unknown_brand(text, brand)
    notes: list[str] = []
    if matched:
        if unknown_brand:
            notes.append(
                f"I don't carry {unknown_brand.title()} yet — "
                f"showing close alternatives from brands we do stock."
            )
        if brand and color and "color" not in mode:
            notes.append(
                f"No {color} {category or 'pieces'} from {brand} in the catalog right now — "
                f"showing {brand} {category or 'picks'} instead."
            )
        elif color and category and mode == "category":
            notes.append(f"No {color} {category} right now — showing our {category}.")
        elif color and mode == "name_match" and not any(
            _color_matches(p, color) for p in matched[:20]
        ):
            notes.append(f"No {color} ones right now — showing what we have.")
        elif brand and "brand" not in mode:
            notes.append(f"I don't carry {brand} yet — showing close alternatives.")
        if price_relaxed:
            bound = (f"under ₹{price_max:,.0f}" if price_max is not None
                     else f"over ₹{price_min:,.0f}")
            notes.append(f"Nothing {bound} for that ask — showing the closest matches.")

    ranked = _dedupe(_rank(matched, sort))[:n]
    products = [{**p, "mix_role": "on_brief"} for p in ranked]

    if not products:
        desc = _facet_desc(brand or (unknown_brand.title() if unknown_brand else None),
                           category, color, price_max, price_min)
        result["message"] = (
            f"Sorry — we don't have any more {desc} right now. "
            f"Want me to show something close instead?"
        )
    else:
        result["label"] = _label(
            brand, color, category, sort, sort_explicit, price_max, mode,
            term=matched_term,
        )

    result.update({"mode": mode, "notes": notes, "products": products})
    _cache_put(key, {**result, "products": [dict(p) for p in products]})
    result["elapsed_ms"] = (time.perf_counter() - t0) * 1000.0
    return result
