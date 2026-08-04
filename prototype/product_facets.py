"""Catalog facet labeling + in-memory filtering for Zara-style browse.

Facets are derived from name/color/price/created_at so every product is labeled
without waiting on PA-API size/variant feeds. Enrichment is pure and fast —
safe to run on every catalog load (~1k–10k products).
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable

# ── Controlled vocabularies ───────────────────────────────────────────────────

KNOWN_BRANDS = (
    "Marks & Spencer", "VERO MODA", "Hidesign", "Levi's", "Tommy Hilfiger",
    "Clarks", "Lee", "Fossil", "Van Heusen", "Calvin Klein", "Allen Solly",
    "Pepe Jeans", "Aldo", "ONLY", "Lavie Signature", "Lavie Luxe",
    "Carlton London", "MEROKEETY", "Columbia", "BIBA", "PRETTYGARDEN",
    "Tankaneo", "Theater", "SaintX", "Monte Carlo", "Amazon Essentials",
    "ANRABESS", "Reebok", "Nike", "Adidas", "Puma", "H&M", "Zara",
    "U.S. Polo Assn", "US Polo", "Jack & Jones", "SELECTED", "GAP",
    "Forever 21", "Max", "Lifestyle", "Fabindia", "W", "Aurelia",
    # D2C / Mira partner brands
    "Snitch", "Urbanic", "Nobero", "Berrylush", "Rare Rabbit",
)

COLOURS = (
    "black", "white", "red", "blue", "navy", "green", "pink", "beige", "brown",
    "tan", "grey", "gray", "gold", "silver", "purple", "burgundy", "olive",
    "khaki", "cream", "ivory", "yellow", "orange", "maroon", "coral", "teal",
    "camel", "nude", "multi",
)

MATERIALS = (
    "leather", "cotton", "denim", "silk", "linen", "wool", "polyester", "satin",
    "chiffon", "velvet", "suede", "knit", "jersey", "rayon", "viscose", "nylon",
    "cashmere", "georgette", "organza", "tweed", "canvas", "mesh",
)

LENGTHS = {
    "mini": ("mini", "short dress", "short length"),
    "midi": ("midi", "knee length", "knee-length"),
    "maxi": ("maxi", "floor length", "floor-length", "ankle length"),
    "crop": ("crop", "cropped"),
    "regular": ("regular length",),
}

PATTERNS = {
    "floral": ("floral", "flower"),
    "striped": ("stripe", "striped"),
    "checked": ("check", "plaid", "gingham"),
    "printed": ("print", "printed"),
    "solid": ("solid", "plain"),
    "animal": ("leopard", "zebra", "snake", "animal print"),
    "polka": ("polka", "dot print"),
}

FITS = {
    "slim": ("slim fit", "slim-fit", "skinny"),
    "regular": ("regular fit", "classic fit"),
    "relaxed": ("relaxed", "loose fit", "oversized", "baggy"),
    "straight": ("straight fit", "straight leg"),
    "tapered": ("tapered",),
    "bootcut": ("bootcut", "boot cut"),
}

SHAPES = {
    "a-line": ("a-line", "a line"),
    "bodycon": ("bodycon", "body con", "fitted"),
    "wrap": ("wrap dress", "wrap top"),
    "shirt": ("shirt dress", "shacket"),
    "shift": ("shift dress",),
    "sheath": ("sheath",),
    "wide-leg": ("wide leg", "wide-leg", "palazzo"),
}

COLLARS = {
    "v-neck": ("v-neck", "v neck"),
    "crew": ("crew neck", "crew-neck", "round neck"),
    "mock": ("mock neck", "mock-neck"),
    "turtleneck": ("turtleneck", "turtle neck"),
    "collared": ("collar", "button-down", "button down"),
    "halter": ("halter",),
    "off-shoulder": ("off shoulder", "off-shoulder", "one shoulder"),
}

OCCASIONS = {
    "office": ("office", "workwear", "formal", "business"),
    "casual": ("casual", "everyday", "daily"),
    "party": ("party", "evening", "cocktail", "night out"),
    "wedding": ("wedding", "bridal", "bridesmaid"),
    "beach": ("beach", "resort", "vacation", "holiday"),
    "sport": ("sport", "athletic", "running", "training", "active"),
}

SPECIALTY = {
    "plus": ("plus size", "plus-size", "curve"),
    "petite": ("petite",),
    "tall": ("tall ", " elongated"),
    "maternity": ("maternity", "nursing"),
}

LICENSED = ("disney", "marvel", "barbie", "hello kitty", "pokemon", "star wars")

SIZE_RE = re.compile(
    r"(?<![A-Za-z0-9])(XXS|XS|S|M|L|XL|XXL|XXXL|2XL|3XL|"
    r"UK\s?\d{1,2}|US\s?\d{1,2}|\d{2,3}\s?cm)(?![A-Za-z0-9])",
    re.I,
)

FILTER_KEYS = (
    "sort", "brand", "new_in", "size", "price", "colour", "material",
    "specialty_size", "collection", "length", "pattern", "campaigns",
    "fit", "shape", "multipack", "product_standard", "collar",
    "adaptive", "licensed", "occasion", "delivery", "category",
)

PRICE_BANDS = (
    ("under_2500", "Under ₹2,500", 0, 2500),
    ("2500_5000", "₹2,500 – ₹5,000", 2500, 5000),
    ("5000_10000", "₹5,000 – ₹10,000", 5000, 10000),
    ("10000_plus", "₹10,000+", 10000, None),
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _match_key(blob: str, mapping: dict[str, tuple[str, ...]]) -> str | None:
    for key, needles in mapping.items():
        if any(n in blob for n in needles):
            return key
    return None


def extract_brand(name: str) -> str | None:
    if not name:
        return None
    for brand in KNOWN_BRANDS:
        if name.lower().startswith(brand.lower()):
            return brand
    # "Brand Women's …" / "Brand Men …"
    parts = re.split(r"\s+(?:Women'?s|Men'?s|Ladies|Womens|Mens|Women|Men)\b", name, maxsplit=1)
    head = parts[0].strip()
    tokens = head.split()
    ok_case = (not head.isupper()) or (head.isupper() and len(tokens) <= 2)
    if 1 <= len(tokens) <= 3 and len(head) <= 32 and ok_case:
        if tokens[0].lower() not in {"the", "new", "a", "an", "for"}:
            return head
    return None


def enrich_product(product: dict[str, Any]) -> dict[str, Any]:
    """Return product with facets (+ brand) filled. Mutates a shallow copy."""
    p = dict(product)
    existing = p.get("facets") if isinstance(p.get("facets"), dict) else {}
    name = p.get("name") or ""
    blob = _norm(name)
    color = _norm(p.get("color") or "")

    brand = p.get("brand") or existing.get("brand") or extract_brand(name)

    colour = color if color and color != "multi" else None
    if not colour:
        for c in COLOURS:
            if c != "multi" and re.search(rf"\b{re.escape(c)}\b", blob):
                colour = "grey" if c == "gray" else c
                break
    if not colour and color:
        colour = color

    material = existing.get("material")
    if not material:
        for m in MATERIALS:
            if re.search(rf"\b{re.escape(m)}\b", blob):
                material = m
                break

    sizes = list(existing.get("size") or [])
    if not sizes:
        sizes = sorted({m.group(1).upper().replace(" ", "") for m in SIZE_RE.finditer(name)})

    created = p.get("created_at")
    new_in = False
    if created:
        try:
            ts = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            new_in = (datetime.now(timezone.utc) - ts).days <= 45
        except ValueError:
            new_in = False

    occasions = list(existing.get("occasion") or [])
    if not occasions:
        occasions = [k for k, needles in OCCASIONS.items() if any(n in blob for n in needles)]

    facets = {
        "brand": brand,
        "colour": colour,
        "material": material,
        "size": sizes,
        "specialty_size": _match_key(blob, SPECIALTY) or existing.get("specialty_size"),
        "length": _match_key(blob, LENGTHS) or existing.get("length"),
        "pattern": _match_key(blob, PATTERNS) or existing.get("pattern"),
        "fit": _match_key(blob, FITS) or existing.get("fit"),
        "shape": _match_key(blob, SHAPES) or existing.get("shape"),
        "collar": _match_key(blob, COLLARS) or existing.get("collar"),
        "multipack": bool(existing.get("multipack") or re.search(r"\b(pack of|multipack|set of)\b", blob)),
        "occasion": occasions,
        "collection": existing.get("collection"),
        "campaigns": existing.get("campaigns"),
        "new_in": bool(existing.get("new_in") if "new_in" in existing else new_in),
        "product_standard": existing.get("product_standard"),
        "adaptive": bool(existing.get("adaptive") or "adaptive" in blob),
        "licensed": bool(existing.get("licensed") or any(x in blob for x in LICENSED)),
        # Delivery is cart/PIN dependent — not a static product attribute.
        "delivery": existing.get("delivery"),
    }
    p["brand"] = brand
    p["facets"] = facets
    return p


def enrich_catalog(products: Iterable[dict]) -> list[dict]:
    return [enrich_product(p) for p in products]


def _price_in_band(price: float | None, band_key: str) -> bool:
    if price is None:
        return False
    for key, _label, lo, hi in PRICE_BANDS:
        if key != band_key:
            continue
        if price < lo:
            return False
        if hi is not None and price >= hi:
            return False
        return True
    return False


def product_matches(p: dict, filters: dict[str, Any]) -> bool:
    f = p.get("facets") or {}
    cat = (filters.get("category") or "").strip().lower()
    if cat and cat != "all" and (p.get("category") or "").lower() != cat:
        return False

    brand = (filters.get("brand") or "").strip()
    if brand and (p.get("brand") or f.get("brand") or "").lower() != brand.lower():
        return False

    colour = (filters.get("colour") or filters.get("color") or "").strip().lower()
    if colour and (f.get("colour") or "").lower() != colour:
        return False

    for key in ("material", "length", "pattern", "fit", "shape", "collar",
                "specialty_size", "collection", "campaigns", "product_standard", "delivery"):
        want = (filters.get(key) or "").strip().lower()
        if want and str(f.get(key) or "").lower() != want:
            return False

    if filters.get("new_in") in ("1", "true", "yes", True):
        if not f.get("new_in"):
            return False

    if filters.get("multipack") in ("1", "true", "yes", True):
        if not f.get("multipack"):
            return False

    if filters.get("adaptive") in ("1", "true", "yes", True):
        if not f.get("adaptive"):
            return False

    if filters.get("licensed") in ("1", "true", "yes", True):
        if not f.get("licensed"):
            return False

    size = (filters.get("size") or "").strip().upper()
    if size:
        sizes = {str(s).upper() for s in (f.get("size") or [])}
        if size not in sizes:
            return False

    occasion = (filters.get("occasion") or "").strip().lower()
    if occasion:
        occ = {str(o).lower() for o in (f.get("occasion") or [])}
        if occasion not in occ:
            return False

    price_band = (filters.get("price") or "").strip()
    if price_band:
        try:
            price = float(p["price"]) if p.get("price") is not None else None
        except (TypeError, ValueError):
            price = None
        if not _price_in_band(price, price_band):
            return False

    min_price = filters.get("min_price")
    max_price = filters.get("max_price")
    if min_price not in (None, ""):
        try:
            if p.get("price") is None or float(p["price"]) < float(min_price):
                return False
        except (TypeError, ValueError):
            return False
    if max_price not in (None, ""):
        try:
            if p.get("price") is None or float(p["price"]) > float(max_price):
                return False
        except (TypeError, ValueError):
            return False

    return True


def sort_products(products: list[dict], sort_key: str | None) -> list[dict]:
    key = (sort_key or "featured").lower()
    if key == "price_asc":
        return sorted(products, key=lambda p: (p.get("price") is None, p.get("price") or 0))
    if key == "price_desc":
        return sorted(products, key=lambda p: (p.get("price") is None, -(p.get("price") or 0)))
    if key in ("newest", "new"):
        return sorted(products, key=lambda p: p.get("created_at") or "", reverse=True)
    if key == "name":
        return sorted(products, key=lambda p: (p.get("name") or "").lower())
    return products  # featured = catalog order


def filter_catalog(
    catalog: list[dict],
    filters: dict[str, Any] | None = None,
    *,
    limit: int = 24,
    offset: int = 0,
) -> tuple[list[dict], int]:
    filters = filters or {}
    matched = [p for p in catalog if product_matches(p, filters)]
    matched = sort_products(matched, filters.get("sort"))
    total = len(matched)
    return matched[offset: offset + limit], total


def _facet_label(value: str) -> str:
    """Pretty label; keep known brand casing when possible."""
    raw = (value or "").strip()
    if not raw:
        return raw
    for brand in KNOWN_BRANDS:
        if brand.lower() == raw.lower():
            return brand
    return raw.replace("_", " ").title()


def facet_options(catalog: list[dict], filters: dict[str, Any] | None = None) -> dict[str, list[dict]]:
    """Option lists with counts, respecting other active filters (faceted search)."""
    filters = dict(filters or {})
    # When computing options for a key, ignore that key so users can switch values.
    base_keys = [k for k in filters if k not in ("sort", "limit", "offset", "exclude")]

    def counts_for(field: str, getter) -> list[dict]:
        local = {k: v for k, v in filters.items() if k != field and k in base_keys + ["category", "min_price", "max_price"]}
        c: Counter = Counter()
        for p in catalog:
            if not product_matches(p, local):
                continue
            val = getter(p)
            if val is None or val == "" or val is False:
                continue
            if isinstance(val, (list, tuple, set)):
                for item in val:
                    if item:
                        c[str(item)] += 1
            else:
                c[str(val)] += 1
        return [{"value": k, "label": _facet_label(k), "count": n}
                for k, n in c.most_common(40)]

    price_opts = []
    local_price = {k: v for k, v in filters.items() if k != "price"}
    for key, label, _lo, _hi in PRICE_BANDS:
        n = sum(1 for p in catalog if product_matches(p, local_price) and _price_in_band(
            float(p["price"]) if p.get("price") is not None else None, key))
        if n:
            price_opts.append({"value": key, "label": label, "count": n})

    new_in_count = sum(1 for p in catalog if product_matches(p, {k: v for k, v in filters.items() if k != "new_in"}) and (p.get("facets") or {}).get("new_in"))

    return {
        "sort": [
            {"value": "featured", "label": "Featured", "count": None},
            {"value": "newest", "label": "Newest", "count": None},
            {"value": "price_asc", "label": "Price: Low to high", "count": None},
            {"value": "price_desc", "label": "Price: High to low", "count": None},
            {"value": "name", "label": "Name", "count": None},
        ],
        "brand": counts_for("brand", lambda p: p.get("brand") or (p.get("facets") or {}).get("brand")),
        "new_in": [{"value": "true", "label": "New in", "count": new_in_count}] if new_in_count else [],
        "size": counts_for("size", lambda p: (p.get("facets") or {}).get("size")),
        "price": price_opts,
        "colour": counts_for("colour", lambda p: (p.get("facets") or {}).get("colour")),
        "material": counts_for("material", lambda p: (p.get("facets") or {}).get("material")),
        "specialty_size": counts_for("specialty_size", lambda p: (p.get("facets") or {}).get("specialty_size")),
        "collection": counts_for("collection", lambda p: (p.get("facets") or {}).get("collection")),
        "length": counts_for("length", lambda p: (p.get("facets") or {}).get("length")),
        "pattern": counts_for("pattern", lambda p: (p.get("facets") or {}).get("pattern")),
        "campaigns": counts_for("campaigns", lambda p: (p.get("facets") or {}).get("campaigns")),
        "fit": counts_for("fit", lambda p: (p.get("facets") or {}).get("fit")),
        "shape": counts_for("shape", lambda p: (p.get("facets") or {}).get("shape")),
        "multipack": counts_for("multipack", lambda p: "true" if (p.get("facets") or {}).get("multipack") else None),
        "product_standard": counts_for("product_standard", lambda p: (p.get("facets") or {}).get("product_standard")),
        "collar": counts_for("collar", lambda p: (p.get("facets") or {}).get("collar")),
        "adaptive": counts_for("adaptive", lambda p: "true" if (p.get("facets") or {}).get("adaptive") else None),
        "licensed": counts_for("licensed", lambda p: "true" if (p.get("facets") or {}).get("licensed") else None),
        "occasion": counts_for("occasion", lambda p: (p.get("facets") or {}).get("occasion")),
        "delivery": counts_for("delivery", lambda p: (p.get("facets") or {}).get("delivery")),
        "category": counts_for("category", lambda p: p.get("category")),
    }
