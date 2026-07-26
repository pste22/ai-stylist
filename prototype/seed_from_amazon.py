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
    # ── Women — dresses (premium brands) ─────────────────────────────────────
    ("Mango women midi dress",                    "dresses",    "women"),
    ("Vero Moda women dress",                     "dresses",    "women"),
    ("Only women bodycon dress",                  "dresses",    "women"),
    ("W for woman ethnic dress",                  "dresses",    "women"),
    ("Biba women anarkali dress",                 "dresses",    "women"),
    ("H&M women wrap dress",                      "dresses",    "women"),
    ("Marks Spencer women dress",                 "dresses",    "women"),
    ("Tommy Hilfiger women dress",                "dresses",    "women"),
    ("Calvin Klein women dress",                  "dresses",    "women"),
    ("AND women cocktail dress",                  "dresses",    "women"),
    # ── Women — tops (premium) ────────────────────────────────────────────────
    ("Van Heusen women formal shirt",             "tops",       "women"),
    ("Allen Solly women top",                     "tops",       "women"),
    ("Vero Moda women blouse",                    "tops",       "women"),
    ("Mango women silk blouse",                   "tops",       "women"),
    ("H&M women premium top",                     "tops",       "women"),
    ("Only women printed top",                    "tops",       "women"),
    ("Marks Spencer women shirt",                 "tops",       "women"),
    ("Global Desi women kurti",                   "tops",       "women"),
    ("Libas women embroidered kurti",             "tops",       "women"),
    ("W for woman women kurti",                   "tops",       "women"),
    # ── Women — bottoms (premium) ─────────────────────────────────────────────
    ("Levi's women skinny jeans",                 "bottoms",    "women"),
    ("Pepe Jeans women jeans",                    "bottoms",    "women"),
    ("Lee Cooper women jeans",                    "bottoms",    "women"),
    ("Vero Moda women trousers",                  "bottoms",    "women"),
    ("Only women wide leg pants",                 "bottoms",    "women"),
    ("H&M women palazzo pants",                   "bottoms",    "women"),
    ("Marks Spencer women trousers",              "bottoms",    "women"),
    # ── Women — outerwear (premium) ───────────────────────────────────────────
    ("Mango women trench coat",                   "outerwear",  "women"),
    ("Tommy Hilfiger women jacket",               "outerwear",  "women"),
    ("Superdry women jacket",                     "outerwear",  "women"),
    ("H&M women blazer",                          "outerwear",  "women"),
    ("Vero Moda women blazer",                    "outerwear",  "women"),
    ("United Colors Benetton women jacket",       "outerwear",  "women"),
    # ── Women — shoes (premium) ───────────────────────────────────────────────
    ("Steve Madden women heels",                  "shoes",      "women"),
    ("Carlton London women pumps",                "shoes",      "women"),
    ("Aldo women ankle boots",                    "shoes",      "women"),
    ("Mango women leather sandals",               "shoes",      "women"),
    ("Tommy Hilfiger women sneakers",             "shoes",      "women"),
    ("Clarks women formal shoes",                 "shoes",      "women"),
    ("Charles Keith women heels",                 "shoes",      "women"),
    ("Catwalk women block heels",                 "shoes",      "women"),
    # ── Women — bags (premium) ────────────────────────────────────────────────
    ("Lavie women handbag",                       "bags",       "women"),
    ("Hidesign women leather bag",                "bags",       "women"),
    ("Fossil women crossbody bag",                "bags",       "women"),
    ("Caprese women tote bag",                    "bags",       "women"),
    ("Aldo women shoulder bag",                   "bags",       "women"),
    ("Charles Keith women clutch",                "bags",       "women"),
    ("Tommy Hilfiger women handbag",              "bags",       "women"),
    # ── Women — accessories (premium) ─────────────────────────────────────────
    ("Fossil women watch",                        "accessories","women"),
    ("Titan women watch",                         "accessories","women"),
    ("Michael Kors women sunglasses",             "accessories","women"),
    ("Ray-Ban women sunglasses",                  "accessories","women"),
    ("Guess women jewellery",                     "accessories","women"),
    ("Swarovski women bracelet",                  "accessories","women"),
    # ── Women — activewear (premium) ──────────────────────────────────────────
    ("Nike women sports bra",                     "activewear", "women"),
    ("Adidas women leggings",                     "activewear", "women"),
    ("Puma women gym top",                        "activewear", "women"),
    ("Under Armour women activewear",             "activewear", "women"),
    ("Reebok women training shoes",               "activewear", "women"),
    # ── Men — tops (premium) ──────────────────────────────────────────────────
    ("Tommy Hilfiger men polo shirt",             "tops",       "men"),
    ("Calvin Klein men t-shirt",                  "tops",       "men"),
    ("Van Heusen men formal shirt",               "tops",       "men"),
    ("Arrow men shirt",                           "tops",       "men"),
    ("Allen Solly men shirt",                     "tops",       "men"),
    ("Peter England men formal shirt",            "tops",       "men"),
    ("Raymond men shirt",                         "tops",       "men"),
    ("Superdry men t-shirt",                      "tops",       "men"),
    ("Marks Spencer men shirt",                   "tops",       "men"),
    ("United Colors Benetton men shirt",          "tops",       "men"),
    # ── Men — bottoms (premium) ───────────────────────────────────────────────
    ("Levi's men slim fit jeans",                 "bottoms",    "men"),
    ("Pepe Jeans men jeans",                      "bottoms",    "men"),
    ("Van Heusen men formal trousers",            "bottoms",    "men"),
    ("Arrow men chinos",                          "bottoms",    "men"),
    ("Allen Solly men trousers",                  "bottoms",    "men"),
    ("Lee men jeans",                             "bottoms",    "men"),
    # ── Men — outerwear (premium) ─────────────────────────────────────────────
    ("Tommy Hilfiger men jacket",                 "outerwear",  "men"),
    ("Superdry men bomber jacket",                "outerwear",  "men"),
    ("United Colors Benetton men jacket",         "outerwear",  "men"),
    ("Mango men blazer",                          "outerwear",  "men"),
    ("Van Heusen men blazer",                     "outerwear",  "men"),
    # ── Men — shoes (premium) ─────────────────────────────────────────────────
    ("Red Tape men leather shoes",                "shoes",      "men"),
    ("Clarks men formal shoes",                   "shoes",      "men"),
    ("Tommy Hilfiger men sneakers",               "shoes",      "men"),
    ("Adidas men sneakers",                       "shoes",      "men"),
    ("Nike men running shoes",                    "shoes",      "men"),
    ("Woodland men boots",                        "shoes",      "men"),
    ("Hush Puppies men loafers",                  "shoes",      "men"),
    # ── Men — bags (premium) ──────────────────────────────────────────────────
    ("Tommy Hilfiger men messenger bag",          "bags",       "men"),
    ("Fossil men wallet leather",                 "bags",       "men"),
    ("Hidesign men leather bag",                  "bags",       "men"),
    # ── Men — accessories (premium) ───────────────────────────────────────────
    ("Fossil men watch",                          "accessories","men"),
    ("Titan men watch",                           "accessories","men"),
    ("Ray-Ban men sunglasses",                    "accessories","men"),
    ("Tommy Hilfiger men belt",                   "accessories","men"),
    # ── Men — activewear (premium) ────────────────────────────────────────────
    ("Nike men dri-fit t-shirt",                  "activewear", "men"),
    ("Adidas men training shorts",                "activewear", "men"),
    ("Puma men gym wear",                         "activewear", "men"),
    ("Under Armour men compression",              "activewear", "men"),
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


def _fetch(backend: str, query: str, sort_by: str = "average_review") -> list[dict]:
    if backend == "rainforest":
        from rainforest_products import search_products
        return search_products(query, sort_by=sort_by)
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
            items = _fetch(backend, query, sort_by="average_review")
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
            if not price or price < 1500:  # premium only — skip under ₹1,500
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
                "currency":      "INR",
                "style":         [],
                "gender":        gender,
                "image_url":     item["image_url"],
                "affiliate_url": item["affiliate_url"],
                "partner_tag":   tag,
                "is_active":     True,
            }
            if dry_run:
                print(f"  DRY  {asin}  ₹{price:>8.0f}  {item['name'][:60]}")
            else:
                safe_row = {k: v for k, v in row.items()
                            if k not in ("rating", "ratings_total")}
                sb.table("products").upsert(safe_row, on_conflict="id").execute()
                print(f"  ✓  {asin}  ₹{price:>8.0f}  {item['name'][:60]}")
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
