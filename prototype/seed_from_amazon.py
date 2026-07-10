"""
Seed the products database with real Amazon fashion products.

Supports two backends (auto-detected from .env):
  1. Rainforest API  — works immediately, no sales requirement
                       Free trial = 100 requests ≈ 1 000 products
  2. PA-API          — free but needs 10 qualifying sales in 30 days

Usage:
  cd prototype
  python seed_from_amazon.py              # up to 1 000 products
  python seed_from_amazon.py --limit 200  # smaller batch to test
  python seed_from_amazon.py --dry-run    # print without writing to DB
  python seed_from_amazon.py --replace    # clear existing amazon rows first
  python seed_from_amazon.py --backend rainforest  # force Rainforest API
  python seed_from_amazon.py --backend paapi       # force PA-API
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import uuid

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

sys.path.insert(0, os.path.dirname(__file__))

# ── Search plan: (query, category, gender) ────────────────────────────────────
# 60 queries × 10 items ≈ 600 unique products per run.
# 100 queries × 10 items ≈ 1 000 unique products.
QUERIES: list[tuple[str, str, str]] = [
    # Women — dresses
    ("women summer casual dress",        "dresses",     "women"),
    ("women floral maxi dress",          "dresses",     "women"),
    ("women wrap midi dress",            "dresses",     "women"),
    ("women bodycon mini dress",         "dresses",     "women"),
    ("women boho sundress",              "dresses",     "women"),
    ("women satin slip dress",           "dresses",     "women"),
    ("women cocktail party dress",       "dresses",     "women"),
    ("women smocked tiered dress",       "dresses",     "women"),
    ("women sweater dress fall",         "dresses",     "women"),
    ("women shirt dress belted",         "dresses",     "women"),
    # Women — tops
    ("women chiffon blouse work",        "tops",        "women"),
    ("women crop top casual",            "tops",        "women"),
    ("women ribbed tank top",            "tops",        "women"),
    ("women oversized sweatshirt",       "tops",        "women"),
    ("women lace trim camisole",         "tops",        "women"),
    ("women knit sweater pullover",      "tops",        "women"),
    ("women off shoulder top",           "tops",        "women"),
    ("women peplum top work",            "tops",        "women"),
    # Women — bottoms
    ("women high waist skinny jeans",    "bottoms",     "women"),
    ("women wide leg trousers",          "bottoms",     "women"),
    ("women yoga leggings high waist",   "bottoms",     "women"),
    ("women pleated midi skirt",         "bottoms",     "women"),
    ("women denim shorts",               "bottoms",     "women"),
    ("women cargo pants women",          "bottoms",     "women"),
    ("women flare jeans",                "bottoms",     "women"),
    ("women linen wide pants",           "bottoms",     "women"),
    # Women — outerwear
    ("women trench coat classic",        "outerwear",   "women"),
    ("women puffer jacket winter",       "outerwear",   "women"),
    ("women blazer work office",         "outerwear",   "women"),
    ("women faux leather jacket",        "outerwear",   "women"),
    ("women longline cardigan",          "outerwear",   "women"),
    ("women shacket shirt jacket",       "outerwear",   "women"),
    # Women — shoes
    ("women white sneakers fashion",     "shoes",       "women"),
    ("women block heel sandals",         "shoes",       "women"),
    ("women ankle boots heeled",         "shoes",       "women"),
    ("women pointed toe pumps",          "shoes",       "women"),
    ("women platform sneakers",          "shoes",       "women"),
    ("women slip on loafers",            "shoes",       "women"),
    ("women running shoes lightweight",  "shoes",       "women"),
    ("women knee high boots",            "shoes",       "women"),
    ("women mule heels",                 "shoes",       "women"),
    # Women — bags
    ("women leather shoulder tote bag",  "bags",        "women"),
    ("women mini crossbody bag",         "bags",        "women"),
    ("women clutch evening bag",         "bags",        "women"),
    ("women canvas tote bag",            "bags",        "women"),
    ("women backpack fashion leather",   "bags",        "women"),
    ("women satchel handbag",            "bags",        "women"),
    # Women — accessories
    ("women gold hoop earrings",         "accessories", "women"),
    ("women oversized sunglasses uv",    "accessories", "women"),
    ("women silk scarf hair",            "accessories", "women"),
    ("women dainty layered necklace",    "accessories", "women"),
    ("women wide brim hat",              "accessories", "women"),
    ("women leather belt",               "accessories", "women"),
    # Women — activewear
    ("women sports bra medium support",  "activewear",  "women"),
    ("women bike shorts high waist",     "activewear",  "women"),
    ("women zip up hoodie gym",          "activewear",  "women"),
    ("women athletic tank top",          "activewear",  "women"),
    # Men — tops
    ("men slim fit polo shirt",          "men_tops",    "men"),
    ("men oxford button down shirt",     "men_tops",    "men"),
    ("men pullover hoodie",              "men_tops",    "men"),
    ("men graphic tee",                  "men_tops",    "men"),
    ("men linen shirt summer",           "men_tops",    "men"),
    ("men henley long sleeve",           "men_tops",    "men"),
    ("men merino wool sweater",          "men_tops",    "men"),
    # Men — bottoms
    ("men slim chino pants",             "men_bottoms", "men"),
    ("men slim fit dark jeans",          "men_bottoms", "men"),
    ("men jogger pants tapered",         "men_bottoms", "men"),
    ("men dress trousers",               "men_bottoms", "men"),
    ("men swim shorts",                  "men_bottoms", "men"),
    # Men — outerwear
    ("men bomber jacket",                "outerwear",   "men"),
    ("men puffer vest",                  "outerwear",   "men"),
    ("men wool blend overcoat",          "outerwear",   "men"),
    ("men denim jacket",                 "outerwear",   "men"),
    ("men windbreaker jacket",           "outerwear",   "men"),
    # Men — shoes
    ("men white leather sneakers",       "shoes",       "men"),
    ("men chelsea boots leather",        "shoes",       "men"),
    ("men loafers casual",               "shoes",       "men"),
    ("men running shoes",                "shoes",       "men"),
    ("men oxford dress shoes",           "shoes",       "men"),
    # Men — activewear
    ("men gym shorts dry fit",           "activewear",  "men"),
    ("men compression shirt",            "activewear",  "men"),
    ("men athletic jogger",              "activewear",  "men"),
]

_COLOR_WORDS = {
    "black", "white", "navy", "beige", "brown", "grey", "gray",
    "blue", "red", "pink", "green", "yellow", "orange", "purple",
    "cream", "tan", "camel", "olive", "burgundy", "blush", "sage",
    "khaki", "charcoal", "indigo", "rust", "gold", "silver", "nude",
    "coral", "teal", "lavender", "mint", "ivory",
}


def _extract_color(name: str) -> str:
    nl = name.lower()
    for c in _COLOR_WORDS:
        if c in nl:
            return c
    return "multi"


def _make_id(asin: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"amazon:{asin}"))


def _detect_backend() -> str:
    has_rainforest = bool(os.environ.get("RAINFOREST_API_KEY"))
    has_paapi      = bool(os.environ.get("AMAZON_ACCESS_KEY")) and \
                     bool(os.environ.get("AMAZON_SECRET_KEY"))
    if has_rainforest:
        return "rainforest"
    if has_paapi:
        return "paapi"
    return "none"


def _fetch(backend: str, query: str) -> list[dict]:
    if backend == "rainforest":
        from rainforest_products import search_products
        return search_products(query)
    if backend == "paapi":
        from amazon_pa_api import search_items
        return search_items(query)
    raise EnvironmentError("no-backend")


def run(limit: int = 1000, dry_run: bool = False,
        replace: bool = False, backend: str = "auto") -> None:

    from supabase import create_client
    sb  = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    tag = os.environ.get("AMAZON_PARTNER_TAG", "")

    if backend == "auto":
        backend = _detect_backend()

    if backend == "none":
        print("""
❌  No product API credentials found.

Choose one of these options:

  Option A — Rainforest API (recommended, works immediately):
    1. Sign up free at https://www.rainforestapi.com/
       Free trial = 100 requests ≈ 1 000 products
    2. Add to prototype/.env:
         RAINFOREST_API_KEY=your_key_here
    3. Re-run:  python seed_from_amazon.py

  Option B — Amazon PA-API (free but needs 10 sales in 30 days):
    1. Drive 10 qualifying purchases via your affiliate links
    2. Return to https://associates.amazon.com → Tools → PA-API
    3. Add credentials to prototype/.env:
         AMAZON_ACCESS_KEY=...
         AMAZON_SECRET_KEY=...
    4. Re-run:  python seed_from_amazon.py

  Option C — Amazon Creators API (alternative free route):
    1. Visit the Creators API link on your PA-API page
    2. Follow their registration process
""")
        sys.exit(1)

    print(f"Backend: {backend.upper()}  |  Partner tag: {tag or '(none)'}")

    if replace and not dry_run:
        print("Clearing existing amazon-source products…")
        sb.table("products").delete().eq("source", "amazon").execute()

    existing   = sb.table("products").select("asin").execute()
    seen_asins = {r["asin"] for r in (existing.data or []) if r.get("asin")}
    print(f"Products already in DB: {len(seen_asins)}\n")

    inserted = skipped = errors = 0

    for query, category, gender in QUERIES:
        if inserted >= limit:
            break
        print(f"🔍  {query!r} → {category}/{gender}", flush=True)
        try:
            items = _fetch(backend, query)
        except EnvironmentError as e:
            print(f"\n❌  {e}")
            sys.exit(1)
        except RuntimeError as e:
            print(f"   API error: {e}")
            errors += 1
            time.sleep(3)
            continue

        for item in items:
            if inserted >= limit:
                break
            asin = item.get("asin", "")
            if not asin or asin in seen_asins:
                skipped += 1
                continue
            if not item.get("image_url"):
                skipped += 1
                continue
            price = item.get("price", 0)
            if not price or price < 5:
                skipped += 1
                continue

            seen_asins.add(asin)
            row = {
                "id":            _make_id(asin),
                "source":        "amazon",
                "asin":          asin,
                "name":          item["name"],
                "category":      category,
                "color":         _extract_color(item["name"]),
                "price":         price,
                "style":         [],
                "gender":        gender,
                "image_url":     item["image_url"],
                "affiliate_url": item["affiliate_url"],
                "partner_tag":   tag,
                "is_active":     True,
            }
            if dry_run:
                print(f"  DRY  {asin}  ${price:>7.2f}  {item['name'][:60]}")
            else:
                # Only send columns that exist in the schema
                safe_row = {k: v for k, v in row.items()
                            if k not in ("rating", "ratings_total")}
                sb.table("products").upsert(safe_row, on_conflict="id").execute()
                print(f"  ✓  {asin}  ${price:>7.2f}  {item['name'][:60]}")
            inserted += 1

        time.sleep(1.2)   # be polite to both APIs

    print(f"\n{'[DRY RUN] ' if dry_run else ''}✅  inserted={inserted}  skipped={skipped}  errors={errors}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Seed DB with real Amazon fashion products")
    ap.add_argument("--limit",   type=int,  default=1000, help="max products to insert")
    ap.add_argument("--dry-run", action="store_true",     help="print without writing to DB")
    ap.add_argument("--replace", action="store_true",     help="delete existing amazon rows first")
    ap.add_argument("--backend", choices=["auto","rainforest","paapi"], default="auto")
    args = ap.parse_args()
    run(limit=args.limit, dry_run=args.dry_run, replace=args.replace, backend=args.backend)
