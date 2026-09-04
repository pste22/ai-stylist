"""Deterministic 2-on-brief + 1 curiosity curation and shopping-buddy complements.

Keeps Mira on the shopper's ask while surfacing one elevated / accent pick the
model can frame as a stretch — never invented outside the catalog.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from functools import lru_cache
from typing import Any

from product_facets import COLLARS, FITS, MATERIALS, OCCASIONS, PATTERNS, SHAPES


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

# Words that open a request ("show me some …") rather than name the item wanted.
_LEAD_IN_WORDS: tuple[str, ...] = (
    "show", "find", "get", "see", "want", "need", "looking", "gimme", "give",
    "me", "some", "any", "browse", "search",
)

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


_FUZZY_SKIP = frozenset(_LEAD_IN_WORDS) | {
    "please", "something", "stuff", "items", "pieces", "options", "ones",
    "outfit", "look", "wear", "today", "tonight", "really", "just",
    "with", "from", "that", "this", "have", "what", "when", "which",
    "about", "around", "there", "here", "very", "more", "also",
    "whats", "dont", "cant", "wont",
    # Short English that would otherwise snap onto catalog words (had→hat, let→Lee).
    "had", "has", "his", "her", "hey", "how", "who", "why", "did", "does",
    "are", "was", "can", "let", "see", "you", "she", "him", "they", "them",
    "our", "all", "not", "but", "new", "old", "too", "two", "way", "yes",
    "yet", "put", "say", "use", "now", "out", "its", "may", "been", "like",
    "make", "made", "well", "still", "even", "much", "such", "only", "back",
    "over", "into", "than", "then", "these", "those", "your", "their",
    "would", "could", "should", "might", "will", "going", "hello", "thanks",
    "the", "and", "for", "to", "of", "in", "on", "at", "by", "or", "as",
    "if", "it", "be", "we", "us", "so", "no", "an", "my",
    # Ranking / sort language must never snap onto product words (best→belt).
    "best", "selling", "seller", "sellers", "rated", "popular", "expensive",
    "affordable", "luxury", "latest", "recent", "hottest",
}
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z']*")
_SKIP_VOCAB = frozenset({
    "a", "an", "the", "in", "on", "of", "or", "and", "for", "to", "me", "my",
    "off", "one", "dot", "fit", "line", "multi", "print", "con", "cut",
})
# High-frequency fashion misspellings that edit-distance alone can miss.
_COMMON_TYPOS: dict[str, str] = {
    "topas": "tops", "topps": "tops", "tosp": "tops", "tpos": "tops",
    "shos": "shoes", "shose": "shoes", "shoos": "shoes", "sheos": "shoes",
    "drsses": "dresses", "dreses": "dresses", "dresss": "dresses",
    "jens": "jeans", "jeens": "jeans",
    "pents": "pants", "pantss": "pants",
    "baggs": "bags",
    "jaket": "jacket", "jackt": "jacket", "blzer": "blazer",
    "sandles": "sandals", "sandels": "sandals",
    "snekers": "sneakers", "sneekers": "sneakers", "sneker": "sneakers",
    "heals": "heels", "hels": "heels",
    "kurtie": "kurti", "kurtha": "kurta", "kurti's": "kurti",
    "sarree": "saree", "sari": "saree",
    "lehnga": "lehenga",
    "tshirt": "shirt", "tshrt": "shirt",
    "blose": "blouse", "bloues": "blouse",
    "skrit": "skirt", "skrits": "skirt",
    "trosers": "trousers", "trouser": "trousers",
    "sweter": "sweater", "sweatr": "sweater",
    "hoodi": "hoodie", "hoody": "hoodie",
    "cardigen": "cardigan", "cardgan": "cardigan",
    "leggins": "leggings", "legings": "leggings",
    "palazo": "palazzo", "palazoos": "palazzo",
    "anarkli": "anarkali", "anarkalli": "anarkali",
    "skiny": "skinny",
    "oversizd": "oversized", "overzised": "oversized",
    "denem": "denim", "dnim": "denim",
    "lether": "leather", "leathr": "leather",
    "coton": "cotton",
    "florals": "floral",
    "wedng": "wedding", "weding": "wedding",
    "partty": "party",
    "casul": "casual", "casusal": "casual",
    "forml": "formal",
    "chepest": "cheapest",
    "sugest": "suggest", "suggst": "suggest",
    "purpel": "purple", "purpal": "purple", "purle": "purple", "purpl": "purple",
    "blew": "blue", "blu": "blue",
    "blak": "black", "blk": "black", "balck": "black",
    "whyte": "white", "wite": "white", "whie": "white",
    "yelow": "yellow", "yello": "yellow", "yllow": "yellow",
    "grean": "green", "gren": "green", "grene": "green",
    "organge": "orange", "oragne": "orange", "ornage": "orange",
    "pinck": "pink", "pikn": "pink",
    "navi": "navy",
    "gry": "grey", "graey": "grey", "grayy": "grey",
    "brwn": "brown", "bown": "brown",
    "burgandy": "burgundy", "burdundy": "burgundy",
    "marron": "maroon", "marroon": "maroon",
    "lavendar": "lavender",
    "ivroy": "ivory",
    "florl": "floral", "florel": "floral",
    "stripedd": "striped", "stripes": "striped",
    "cheep": "cheap", "cheepest": "cheapest",
    "trendng": "trending", "trnding": "trending",
    "premum": "premium",
    "newst": "newest",
    "undr": "under", "belo": "below",
    "recomend": "recommend", "reccomend": "recommend",
    "ofice": "office",
}


def _levenshtein(a: str, b: str) -> int:
    """Edit distance for short tokens. Rejects far-apart lengths early."""
    if a == b:
        return 0
    if abs(len(a) - len(b)) > 2:
        return 99
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _vocab_from_groups(*groups: dict) -> set[str]:
    words: set[str] = set()
    for group in groups:
        for aliases in group.values():
            for alias in aliases:
                for part in re.split(r"[^a-z]+", alias.lower()):
                    if len(part) >= 3 and part not in _SKIP_VOCAB:
                        words.add(part)
    return words


@lru_cache(maxsize=1)
def _static_shop_vocab() -> frozenset[str]:
    words = _vocab_from_groups(
        _CATEGORY_SYNONYMS, _COLOR_ALIASES, PATTERNS, FITS, SHAPES, COLLARS, OCCASIONS,
    )
    words.update({
        "under", "below", "between", "budget", "cheapest", "cheap", "premium",
        "newest", "trending", "recommend", "suggest", "surprise", "office",
        "casual",
    })
    words.update(m.lower() for m in MATERIALS if len(m) >= 3)
    words.update(_COMMON_TYPOS.values())
    return frozenset(w for w in words if len(w) >= 3)


def _is_subsequence(short: str, long: str) -> bool:
    it = iter(long)
    return all(ch in it for ch in short)


def _brand_typo_ok(token: str, brand: str) -> bool:
    """Allow zra→zara; block let→Lee / had→hat-style snaps onto short brands."""
    if len(token) >= 4:
        return True
    return len(brand) > len(token) and _is_subsequence(token, brand)


def brand_spell_words(catalog: Iterable[dict] | None) -> tuple[str, ...]:
    """Brand tokens safe to fuzzy-match (never invent a brand we don't carry)."""
    words: list[str] = []
    for b in _brand_index(catalog or []):
        bl = b.lower()
        words.append(bl)
        for part in re.split(r"[^a-z0-9]+", bl):
            if len(part) >= 3:
                words.append(part)
    return tuple(words)


def _in_vocab(token: str, vocab: set[str]) -> bool:
    if token in vocab:
        return True
    if token.endswith("s") and token[:-1] in vocab:
        return True
    if (token + "s") in vocab:
        return True
    return False


def _nearest_vocab(token: str, vocab: Iterable[str]) -> str | None:
    max_dist = 1 if len(token) <= 5 else 2
    best: tuple[int, int, str] | None = None
    for word in vocab:
        if not word or word[0] != token[0]:
            continue
        if len(token) == 3 and not (3 <= len(word) <= 4):
            continue
        if abs(len(word) - len(token)) > 2:
            continue
        dist = _levenshtein(token, word)
        if dist == 0 or dist > max_dist:
            continue
        cand = (dist, -len(word), word)
        if best is None or cand < best:
            best = cand
    return best[2] if best else None


def correct_shop_typos(
    text: str,
    *,
    extra_words: Iterable[str] = (),
) -> tuple[str, list[tuple[str, str]]]:
    """Rewrite chat typos onto catalog language. Returns (text, substitutions)."""
    if not text:
        return text, []
    static = _static_shop_vocab()
    vocab = set(static)
    brand_only = {
        w.lower() for w in extra_words
        if w and len(w) >= 3 and w.lower() not in static
    }
    vocab.update(w.lower() for w in extra_words if w and len(w) >= 3)
    subs: list[tuple[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        tok = match.group(0)
        low = tok.lower().replace("'", "")
        if len(low) < 3 or low in _FUZZY_SKIP or low.isdigit():
            return tok
        mapped = _COMMON_TYPOS.get(low)
        if mapped and mapped != low:
            subs.append((low, mapped))
            return mapped
        if _in_vocab(low, vocab):
            return tok
        # 3-letter tokens are too collision-prone for general fuzzy
        # matching (the→tee, had→hat). Only known maps and dropped-letter
        # brand typos (zra→zara) are allowed.
        search = brand_only if len(low) <= 3 else vocab
        nearest = _nearest_vocab(low, search) if search else None
        if nearest and nearest != low:
            if nearest in brand_only and not _brand_typo_ok(low, nearest):
                return tok
            if len(low) <= 3 and nearest not in brand_only:
                return tok
            subs.append((low, nearest))
            return nearest
        return tok

    return _TOKEN_RE.sub(replace, text), subs


@lru_cache(maxsize=1)
def _synonym_vocab() -> tuple[tuple[str, str], ...]:
    return tuple(
        (word, cat)
        for cat, words in _CATEGORY_SYNONYMS.items()
        for word in words
        if len(word) >= 3
    )


def _fuzzy_category(text: str) -> str | None:
    """Nearest catalog category for a typo'd product word ('topas' → tops)."""
    tokens = [
        w.replace("'", "") for w in _TOKEN_RE.findall(text.lower())
        if w.replace("'", "") not in _FUZZY_SKIP and len(w.replace("'", "")) >= 4
    ]
    best: tuple[int, int, str] | None = None  # (dist, -syn_len, cat)
    for tok in tokens:
        max_dist = 1 if len(tok) <= 5 else 2
        for word, cat in _synonym_vocab():
            if word[0] != tok[0] or abs(len(word) - len(tok)) > 2:
                continue
            dist = _levenshtein(tok, word)
            if dist == 0 or dist > max_dist:
                continue
            cand = (dist, -len(word), cat)
            if best is None or cand < best:
                best = cand
    return best[2] if best else None


_RANK_PHRASE_RE = re.compile(
    r"\b(?:top|best)\s+(?:rated|selling|sell|seller|sellers)\b",
    re.I,
)


def detect_category(text: str) -> str | None:
    """Map free text onto a catalog category using whole-word synonyms.

    Substring matching is unsafe: ``hat`` sits inside ``what's``, so
    "Complete the look — fill what's missing" used to return accessories.
    Typos ('topas', 'shos', 'drsses') are rewritten, then matched.
    Ranking phrases ('top rated shoes') must not steal the 'top' synonym.
    """
    t, _ = correct_shop_typos(text or "")
    t = _RANK_PHRASE_RE.sub(" ", t.lower())
    matches = [
        (m.start(), len(word), cat)
        for cat, words in _CATEGORY_SYNONYMS.items()
        for word in words
        if (m := _alias_re(word).search(t))
    ]
    if not matches:
        return _fuzzy_category(t)
    # A typo can drop a category word inside the command phrase ("shoe mw some
    # tops" for "show me some tops"), so prefer what is asked for after it.
    lead_end = 0
    for lead in _LEAD_IN_WORDS:
        for m in _alias_re(lead).finditer(t):
            lead_end = max(lead_end, m.end())
    after = [item for item in matches if item[0] >= lead_end]
    ranked = sorted(after or matches, key=lambda item: (item[0], -item[1]))
    return ranked[0][2]


def detect_pattern(text: str) -> str | None:
    """Map free text onto a print/pattern facet ("floral", "striped")."""
    t, _ = correct_shop_typos(text or "")
    t = t.lower()
    for key, aliases in PATTERNS.items():
        if _mentions(t, aliases):
            return key
    return None


def detect_occasion(text: str) -> str | None:
    """Map free text onto an occasion facet (office / party / wedding / …)."""
    t, _ = correct_shop_typos(text or "")
    t = t.lower()
    for key, aliases in OCCASIONS.items():
        if _mentions(t, aliases):
            return key
    return None


def pattern_matches(product: dict, pattern_key: str | None) -> bool:
    if not pattern_key:
        return False
    facets = product.get("facets") or {}
    if (facets.get("pattern") or "").strip().lower() == pattern_key:
        return True
    return _mentions((product.get("name") or "").lower(), PATTERNS.get(pattern_key, ()))


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
    t, _ = correct_shop_typos(text or "")
    t = t.lower()
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


def photo_quality(p: dict) -> int:
    """Prefer a real product JPEG over a Pexels stand-in that doesn't match the name."""
    url = (p.get("image_url") or "").lower()
    if "media-amazon.com" in url or "images-amazon.com" in url:
        return 2
    if "pexels.com" in url:
        return 0
    return 1


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

    # Prefer real product photos, then mid-premium on-brief (not the cheapest dump).
    on_brief_sorted = sorted(
        on_brief, key=lambda p: (photo_quality(p), _as_price(p)), reverse=True
    )
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

    def _cur_key(p: dict) -> tuple:
        return (photo_quality(p), _as_price(p))

    pick = None
    if accent_hits:
        real = [p for p in accent_hits if photo_quality(p) > 0]
        pick = max(real or accent_hits, key=_cur_key)
    elif premium_hits:
        real = [p for p in premium_hits if photo_quality(p) > 0]
        pick = max(real or premium_hits, key=_cur_key)
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
        # Prefer a real product photo, then slightly elevated price.
        best = max(candidates, key=lambda p: (photo_quality(p), _as_price(p)))
        picks.append(_tag(best, "complement"))
        exclude.add(best["id"])
        if len(picks) >= n:
            break
    return picks


# VTO "finish this look" — one real catalog piece per slot so a top try-on
# also shows bottoms, shoes and a bag from THIS site (not more tops).
_LOOK_SLOTS: dict[str, tuple[str, ...]] = {
    "tops": ("bottoms", "shoes", "bags"),
    "bottoms": ("tops", "shoes", "bags"),
    "outerwear": ("bottoms", "shoes", "bags"),
    "activewear": ("shoes", "bags", "tops"),
    "dresses": ("shoes", "bags", "accessories"),
    "ethnic": ("shoes", "bags", "accessories"),
    "shoes": ("tops", "bottoms", "bags"),
    "bags": ("tops", "bottoms", "shoes"),
    "accessories": ("tops", "bottoms", "shoes"),
    "swimwear": ("bags", "accessories", "shoes"),
}


def look_slots_for(
    hero: dict,
    catalog: Iterable[dict],
    *,
    exclude_ids: set[str] | None = None,
) -> list[dict]:
    """One catalog item per outfit slot around a try-on hero (bottoms/shoes/bag)."""
    exclude = set(exclude_ids or set())
    hid = hero.get("id")
    if hid:
        exclude.add(hid)
    hero_cat = (hero.get("category") or "").lower()
    slots = _LOOK_SLOTS.get(hero_cat, ("bottoms", "shoes", "bags"))
    slots = tuple(s for s in slots if s != hero_cat)

    by_cat: dict[str, list[dict]] = {}
    for p in catalog:
        if not p.get("id") or p["id"] in exclude:
            continue
        by_cat.setdefault((p.get("category") or "other").lower(), []).append(p)

    hero_color = (hero.get("color") or "").strip().lower()
    if hero_color in _UNKNOWN_COLOR_VALUES:
        hero_color = None
    hero_price = _as_price(hero)

    picks: list[dict] = []
    for cat in slots:
        cands = [p for p in (by_cat.get(cat) or []) if p.get("id") not in exclude]
        if not cands:
            continue

        def _score(p: dict, slot: str = cat) -> tuple:
            s = 0
            s += photo_quality(p) * 8
            s += gender_rank(p, "women") * 3
            if hero_color and _color_matches(p, hero_color):
                s += 5
            blob = f"{p.get('color') or ''} {p.get('name') or ''}".lower()
            if slot == "bottoms" and any(
                tok in blob for tok in ("black", "navy", "white", "beige", "denim", "blue", "ivory")
            ):
                s += 2
            pp = _as_price(p)
            if hero_price and pp:
                ratio = pp / hero_price
                if 0.4 <= ratio <= 2.2:
                    s += 1
            return (s, -abs(pp - hero_price), p.get("id") or "")

        best = max(cands, key=_score)
        picks.append(_tag(best, "look_slot"))
        exclude.add(best["id"])
    return picks


# Women's VTO styling — a *choice* of bottoms, plus bags/shoes other shoppers
# actually rated. Empty/unknown gender stays eligible so sparse feeds still work.
_WOMEN_GENDERS = frozenset({
    "", "women", "woman", "womens", "women's", "female", "unisex", "girls",
})
_MEN_GENDERS = frozenset({
    "men", "man", "mens", "men's", "male", "boys",
})
_BOTTOM_STYLE_KEYS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("skirt", ("skirt", "lehenga")),
    ("shorts", ("short",)),
    ("jeans", ("jean", "denim")),
    ("palazzo", ("palazzo", "wide-leg", "wide leg", "flare", "culotte")),
    ("leggings", ("legging", "jogger")),
    ("trousers", ("trouser", "chino", "pant")),
)
# Amazon review volume we treat as real shopper feedback — not Mira-user claims.
_TRENDING_MIN_VOTES = 25
_TOP_LIKE = frozenset({"tops", "outerwear", "activewear"})


def _gender_norm(item: dict) -> str:
    return (item.get("gender") or "").strip().lower()


def gender_rank(item: dict, shopper: str = "women") -> int:
    """2 = explicit match, 1 = unisex/unknown, 0 = opposite gender."""
    g = _gender_norm(item)
    shopper = (shopper or "women").strip().lower() or "women"
    if shopper == "women":
        if g in _MEN_GENDERS:
            return 0
        if g in ("women", "woman", "womens", "women's", "female", "girls"):
            return 2
        return 1
    if shopper == "men":
        if g in ("women", "woman", "womens", "women's", "female", "girls"):
            return 0
        if g in ("men", "man", "mens", "men's", "male", "boys"):
            return 2
        return 1
    return 1


def gender_ok(item: dict, shopper: str = "women") -> bool:
    return gender_rank(item, shopper) > 0


def _filter_gender(cands: list[dict], shopper: str, *, min_keep: int) -> list[dict]:
    preferred = [p for p in cands if gender_ok(p, shopper)]
    return preferred if len(preferred) >= min_keep else cands


def _review_votes(item: dict) -> float:
    try:
        return float(item.get("ratings_total") or 0)
    except (TypeError, ValueError):
        return 0.0


def _review_rating(item: dict) -> float:
    try:
        return float(item.get("rating") or 0)
    except (TypeError, ValueError):
        return 0.0


def has_shopper_signal(item: dict) -> bool:
    """True when Amazon (or similar) ratings look like real other-shopper feedback."""
    return _review_votes(item) >= _TRENDING_MIN_VOTES and _review_rating(item) > 0


def bottom_style(item: dict) -> str:
    """Coarse silhouette so a VTO rail is jeans + skirt + trousers, not six skinny jeans."""
    styles = item.get("style") or []
    style_s = " ".join(styles) if isinstance(styles, list) else str(styles)
    blob = f"{item.get('name') or ''} {style_s}".lower()
    for key, toks in _BOTTOM_STYLE_KEYS:
        if any(tok in blob for tok in toks):
            return key
    return "other"


def bottoms_variety_for(
    hero: dict,
    catalog: Iterable[dict],
    *,
    n: int = 6,
    shopper: str = "women",
    exclude_ids: set[str] | None = None,
) -> list[dict]:
    """Several bottoms a woman can VTO with this top — variety of silhouette and colour."""
    exclude = set(exclude_ids or set())
    hid = hero.get("id")
    if hid:
        exclude.add(hid)
    hero_color = (hero.get("color") or "").strip().lower()
    if hero_color in _UNKNOWN_COLOR_VALUES:
        hero_color = None
    hero_price = _as_price(hero)

    cands: list[dict] = []
    for p in catalog:
        if not p.get("id") or p["id"] in exclude:
            continue
        if (p.get("category") or "").lower() != "bottoms":
            continue
        if photo_quality(p) <= 0:
            continue
        cands.append(p)
    cands = _filter_gender(cands, shopper, min_keep=max(3, n // 2))
    if not cands:
        return []

    def _score(p: dict) -> tuple:
        s = photo_quality(p) * 10
        s += gender_rank(p, shopper) * 4
        color = (p.get("color") or "").strip().lower()
        # Contrast with the top so the pair reads as a look, not a matchy set.
        if hero_color and color and color != hero_color and not _color_matches(p, hero_color):
            s += 3
        blob = f"{color} {p.get('name') or ''}".lower()
        if any(tok in blob for tok in ("black", "navy", "white", "beige", "denim", "blue", "ivory")):
            s += 2
        if has_shopper_signal(p):
            s += 2
        pp = _as_price(p)
        if hero_price and pp:
            ratio = pp / hero_price
            if 0.4 <= ratio <= 2.2:
                s += 1
        return (s, _review_votes(p), _review_rating(p), -abs(pp - hero_price), p.get("id") or "")

    ranked = sorted(cands, key=_score, reverse=True)
    picked: list[dict] = []
    seen_style: set[str] = set()
    seen_color: set[str] = set()
    picked_ids: set[str] = set()

    def _take(p: dict) -> None:
        picked.append(p)
        picked_ids.add(p["id"])
        seen_style.add(bottom_style(p))
        col = (p.get("color") or "").strip().lower()
        if col:
            seen_color.add(col)

    for p in ranked:
        st = bottom_style(p)
        if st in seen_style:
            continue
        _take(p)
        if len(picked) >= n:
            return [_tag(x, "bottoms_option") for x in picked]

    for p in ranked:
        if p["id"] in picked_ids:
            continue
        col = (p.get("color") or "").strip().lower()
        if col and col in seen_color:
            continue
        _take(p)
        if len(picked) >= n:
            break

    if len(picked) < n:
        for p in ranked:
            if p["id"] in picked_ids:
                continue
            _take(p)
            if len(picked) >= n:
                break
    return [_tag(x, "bottoms_option") for x in picked]


def trending_complements(
    catalog: Iterable[dict],
    *,
    categories: tuple[str, ...] = ("bags", "shoes"),
    n_each: int = 3,
    shopper: str = "women",
    exclude_ids: set[str] | None = None,
) -> list[dict]:
    """Bags/shoes ranked by other shoppers' ratings — badge only when the signal is real."""
    exclude = set(exclude_ids or set())
    out: list[dict] = []
    for cat in categories:
        cands = [
            p for p in catalog
            if p.get("id") and p["id"] not in exclude
            and (p.get("category") or "").lower() == cat
            and photo_quality(p) > 0
        ]
        cands = _filter_gender(cands, shopper, min_keep=n_each)
        cands.sort(
            key=lambda p: (
                _review_votes(p),
                _review_rating(p),
                photo_quality(p),
                gender_rank(p, shopper),
                -_as_price(p),
            ),
            reverse=True,
        )
        for p in cands[:n_each]:
            tagged = _tag(p, "trending")
            if has_shopper_signal(p):
                tagged["badge"] = "trending"
            out.append(tagged)
            exclude.add(p["id"])
    return out


# Homepage rails — clothes / shoes / bags. Tokens are Mira's read of what is
# moving on social (Reels, Pinterest, search), not a scrape of Instagram.
_CLOTHES_CATS = ("dresses", "tops", "bottoms", "outerwear", "ethnic", "activewear")
_HOMEPAGE_RAILS: dict[str, tuple[str, ...]] = {
    "clothes": _CLOTHES_CATS,
    "shoes": ("shoes",),
    "bags": ("bags",),
}
_BAG_HINTS = ("bag", "tote", "clutch", "purse", "handbag", "backpack", "sling", "bucket")
_SOCIAL_HEAT: tuple[str, ...] = (
    "trendy", "cargo", "linen", "co-ord", "coord", "corset", "mesh",
    "platform", "chunky", "mini bag", "shoulder bag", "bucket",
    "jutti", "juttis", "kolhapuri", "festive", "embroidered", "satin",
    "ballet", "sling", "tote", "bodycon", "wrap",
)


def _style_blob(item: dict) -> str:
    styles = item.get("style") or item.get("style_tags") or []
    style_s = " ".join(styles) if isinstance(styles, list) else str(styles)
    return f"{item.get('name') or ''} {style_s} {item.get('color') or ''} {item.get('category') or ''}".lower()


def _social_heat_score(item: dict) -> int:
    blob = _style_blob(item)
    return sum(1 for tok in _SOCIAL_HEAT if tok in blob)


def homepage_trending_rails(
    catalog: Iterable[dict],
    *,
    n_each: int = 8,
    shopper: str = "women",
) -> dict[str, Any]:
    """Ranked clothes / shoes / bags for the launch homepage.

    Products stay catalog-grounded and buyable. Ranking uses social-heat
    tokens, shopper ratings, and real product photos — never scraped Reels.
    """
    pool = [p for p in catalog if p.get("id")]
    rails: dict[str, list[dict]] = {}
    for rail, cats in _HOMEPAGE_RAILS.items():
        cands = [p for p in pool if (p.get("category") or "").lower() in cats]
        if rail == "bags" and len(cands) < n_each:
            extra = [
                p for p in pool
                if (p.get("category") or "").lower() == "accessories"
                and p["id"] not in {x["id"] for x in cands}
                and any(h in _style_blob(p) for h in _BAG_HINTS)
            ]
            cands = cands + extra
        pictured = [p for p in cands if p.get("image_url")]
        cands = pictured or cands
        cands = _filter_gender(cands, shopper, min_keep=max(n_each, 3))
        cands.sort(
            key=lambda p: (
                photo_quality(p),
                _social_heat_score(p),
                1 if has_shopper_signal(p) else 0,
                _review_votes(p),
                _review_rating(p),
            ),
            reverse=True,
        )
        picked: list[dict] = []
        seen: set[str] = set()
        for p in cands:
            pid = p["id"]
            if pid in seen:
                continue
            tagged = _tag(p, "trending")
            if has_shopper_signal(p) or _social_heat_score(p) > 0:
                tagged["badge"] = "trending"
            picked.append(tagged)
            seen.add(pid)
            if len(picked) >= n_each:
                break
        rails[rail] = picked

    flat: list[dict] = []
    seen_flat: set[str] = set()
    for rail in ("clothes", "shoes", "bags"):
        for p in rails.get(rail, [])[:4]:
            if p["id"] in seen_flat:
                continue
            flat.append(p)
            seen_flat.add(p["id"])

    return {
        "headline": "Trending now",
        "subhead": "Clothes, shoes, and bags moving on social this week",
        "rails": rails,
        "items": flat,
    }


def style_suggestions_for(
    hero: dict,
    catalog: Iterable[dict],
    *,
    shopper: str = "women",
    exclude_ids: set[str] | None = None,
    bottoms_n: int = 6,
    trending_n_each: int = 3,
) -> list[dict]:
    """VTO styling rail: a variety of bottoms (when the hero is a top) plus trending bags/shoes."""
    catalog = list(catalog)
    exclude = set(exclude_ids or set())
    hid = hero.get("id")
    if hid:
        exclude.add(hid)
    hero_cat = (hero.get("category") or "").lower()
    items: list[dict] = []
    if hero_cat in _TOP_LIKE:
        bottoms = bottoms_variety_for(
            hero, catalog, n=bottoms_n, shopper=shopper, exclude_ids=exclude,
        )
        items.extend(bottoms)
        exclude.update(p["id"] for p in bottoms if p.get("id"))
    items.extend(trending_complements(
        catalog,
        categories=("bags", "shoes"),
        n_each=trending_n_each,
        shopper=shopper,
        exclude_ids=exclude,
    ))
    if not items:
        return look_slots_for(hero, catalog, exclude_ids=exclude_ids)
    return items


def companion_top_for(
    hero: dict,
    catalog: Iterable[dict],
    *,
    shopper: str = "women",
    exclude_ids: set[str] | None = None,
) -> dict | None:
    """The top to pin on the left of Shop the Look — the hero itself when it is a top."""
    cat = (hero.get("category") or "").lower()
    if cat in ("tops", "outerwear"):
        return _tag(dict(hero), "pinned_top")
    exclude = set(exclude_ids or set())
    hid = hero.get("id")
    if hid:
        exclude.add(hid)
    cands = [
        p for p in catalog
        if p.get("id") and p["id"] not in exclude
        and (p.get("category") or "").lower() in ("tops", "outerwear")
        and photo_quality(p) > 0
    ]
    cands = _filter_gender(cands, shopper, min_keep=1)
    if not cands:
        return None
    hero_color = (hero.get("color") or "").strip().lower()
    if hero_color in _UNKNOWN_COLOR_VALUES:
        hero_color = None
    hero_price = _as_price(hero)

    def _score(p: dict) -> tuple:
        s = photo_quality(p) * 10
        s += gender_rank(p, shopper) * 4
        if hero_color and _color_matches(p, hero_color):
            s += 3
        if has_shopper_signal(p):
            s += 2
        pp = _as_price(p)
        if hero_price and pp:
            ratio = pp / hero_price
            if 0.4 <= ratio <= 2.2:
                s += 1
        return (s, _review_votes(p), _review_rating(p), p.get("id") or "")

    return _tag(max(cands, key=_score), "pinned_top")


def look_match_pct(hero: dict | None, piece: dict, shopper: str = "women") -> int:
    """Deterministic pairing score from colour, style, photo and price — not invented social proof."""
    if not piece:
        return 0
    score = 76
    score += gender_rank(piece, shopper) * 4
    score += photo_quality(piece) * 3
    hero_color = ((hero or {}).get("color") or "").strip().lower()
    if hero_color in _UNKNOWN_COLOR_VALUES:
        hero_color = None
    piece_color = (piece.get("color") or "").strip().lower()
    if hero_color and _color_matches(piece, hero_color):
        score += 5
    elif hero_color and piece_color and piece_color != hero_color and piece_color not in _UNKNOWN_COLOR_VALUES:
        score += 8
    hero_styles = {str(s).strip().lower() for s in ((hero or {}).get("style") or []) if s}
    piece_styles = {str(s).strip().lower() for s in (piece.get("style") or []) if s}
    if hero_styles and piece_styles and hero_styles & piece_styles:
        score += 6
    if has_shopper_signal(piece):
        score += 3
    hero_price = _as_price(hero or {})
    pp = _as_price(piece)
    if hero_price and pp:
        ratio = pp / hero_price
        if 0.4 <= ratio <= 2.2:
            score += 3
    return int(min(96, max(76, score)))


def shop_look_for(
    hero: dict,
    catalog: Iterable[dict],
    *,
    shopper: str = "women",
    exclude_ids: set[str] | None = None,
    bottoms_n: int = 6,
    trending_n_each: int = 2,
) -> dict:
    """Shop-the-look payload: pinned top, a chooser of bottoms, trending bags/shoes."""
    catalog = list(catalog)
    exclude = set(exclude_ids or set())
    hid = hero.get("id")
    hero_cat = (hero.get("category") or "").lower()
    pinned = companion_top_for(hero, catalog, shopper=shopper, exclude_ids=exclude)
    if pinned and pinned.get("id"):
        exclude.add(pinned["id"])
    if hid:
        exclude.add(hid)
    bottoms: list[dict] = []
    if pinned:
        bottoms = bottoms_variety_for(
            pinned, catalog, n=bottoms_n, shopper=shopper, exclude_ids=exclude,
        )
        exclude.update(p["id"] for p in bottoms if p.get("id"))
    if hero_cat == "bottoms" and hid:
        tagged = _tag(dict(hero), "bottoms_option")
        rest = [p for p in bottoms if p.get("id") != hid]
        bottoms = [tagged, *rest][: max(bottoms_n, 1)]
        exclude.add(hid)
    accents = trending_complements(
        catalog,
        categories=("bags", "shoes"),
        n_each=trending_n_each,
        shopper=shopper,
        exclude_ids=exclude,
    )
    if hero_cat in ("bags", "shoes") and hid and not any(p.get("id") == hid for p in accents):
        tagged = _tag(dict(hero), "hero")
        same = [p for p in accents if (p.get("category") or "").lower() == hero_cat]
        other = [p for p in accents if (p.get("category") or "").lower() != hero_cat]
        accents = [tagged, *same, *other]
    anchor = pinned or hero
    for p in bottoms:
        p["match_score"] = look_match_pct(anchor, p, shopper)
    for p in accents:
        p["match_score"] = look_match_pct(anchor, p, shopper)
    return {"pinned": pinned, "bottoms": bottoms, "accents": accents}


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
    if p.get("badge"):
        out["badge"] = p["badge"]
    rating = p.get("rating")
    if rating not in (None, "", 0, 0.0, "0"):
        out["rating"] = rating
        out["ratings_total"] = p.get("ratings_total") or 0
    styles = p.get("style")
    if isinstance(styles, list) and styles:
        out["style"] = styles
    try:
        match = int(p.get("match_score") or 0)
    except (TypeError, ValueError):
        match = 0
    if match:
        out["match_score"] = match
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
    t, _ = correct_shop_typos(text or "", extra_words=brand_spell_words(catalog))
    t = t.lower()
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
    query, _ = correct_shop_typos(query, extra_words=brand_spell_words(products))
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
