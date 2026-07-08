"""
Populate the products database with real Amazon fashion products via PA-API.

Usage:
  cd prototype
  python seed_from_amazon.py             # fetch up to 1000 products
  python seed_from_amazon.py --limit 200 # smaller batch
  python seed_from_amazon.py --dry-run   # print without writing to DB
  python seed_from_amazon.py --replace   # clear existing amazon rows first

Requires AMAZON_ACCESS_KEY + AMAZON_SECRET_KEY + AMAZON_PARTNER_TAG in .env
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
from amazon_pa_api import search_items   # noqa: E402

# ── Search plan: (keywords, category, gender, search_index) ───────────────────
# 55 queries × 10 items = up to 550 unique products per run.
# Run twice (or add more queries) to reach 1 000.
QUERIES: list[tuple[str, str, str, str]] = [
    # ── Women's dresses ──────────────────────────────────────────────────────
    ("women summer casual dress",        "dresses",     "women", "Fashion"),
    ("women floral maxi dress",          "dresses",     "women", "Fashion"),
    ("women wrap midi dress",            "dresses",     "women", "Fashion"),
    ("women bodycon mini dress",         "dresses",     "women", "Fashion"),
    ("women boho sundress",              "dresses",     "women", "Fashion"),
    ("women satin slip dress",           "dresses",     "women", "Fashion"),
    ("women cocktail party dress",       "dresses",     "women", "Fashion"),
    # ── Women's tops ─────────────────────────────────────────────────────────
    ("women chiffon blouse work",        "tops",        "women", "Fashion"),
    ("women crop top casual",            "tops",        "women", "Fashion"),
    ("women ribbed tank top",            "tops",        "women", "Fashion"),
    ("women oversized sweatshirt",       "tops",        "women", "Fashion"),
    ("women lace trim camisole",         "tops",        "women", "Fashion"),
    ("women knit sweater pullover",      "tops",        "women", "Fashion"),
    # ── Women's bottoms ──────────────────────────────────────────────────────
    ("women high waist skinny jeans",    "bottoms",     "women", "Fashion"),
    ("women wide leg trousers",          "bottoms",     "women", "Fashion"),
    ("women yoga leggings",              "bottoms",     "women", "Fashion"),
    ("women pleated midi skirt",         "bottoms",     "women", "Fashion"),
    ("women denim shorts",               "bottoms",     "women", "Fashion"),
    ("women cargo pants",                "bottoms",     "women", "Fashion"),
    # ── Women's outerwear ────────────────────────────────────────────────────
    ("women trench coat classic",        "outerwear",   "women", "Fashion"),
    ("women puffer jacket winter",       "outerwear",   "women", "Fashion"),
    ("women blazer work office",         "outerwear",   "women", "Fashion"),
    ("women faux leather jacket",        "outerwear",   "women", "Fashion"),
    ("women longline cardigan",          "outerwear",   "women", "Fashion"),
    # ── Women's shoes ────────────────────────────────────────────────────────
    ("women white sneakers fashion",     "shoes",       "women", "Shoes"),
    ("women block heel sandals",         "shoes",       "women", "Shoes"),
    ("women ankle boots heeled",         "shoes",       "women", "Shoes"),
    ("women pointed toe pumps",          "shoes",       "women", "Shoes"),
    ("women platform sneakers chunky",   "shoes",       "women", "Shoes"),
    ("women slip on loafers",            "shoes",       "women", "Shoes"),
    ("women running shoes lightweight",  "shoes",       "women", "Shoes"),
    # ── Women's bags ─────────────────────────────────────────────────────────
    ("women leather shoulder tote bag",  "bags",        "women", "Fashion"),
    ("women mini crossbody bag",         "bags",        "women", "Fashion"),
    ("women clutch evening bag",         "bags",        "women", "Fashion"),
    ("women canvas tote bag",            "bags",        "women", "Fashion"),
    ("women backpack leather fashion",   "bags",        "women", "Fashion"),
    # ── Women's accessories ──────────────────────────────────────────────────
    ("women gold hoop earrings",         "accessories", "women", "Fashion"),
    ("women oversized sunglasses uv",    "accessories", "women", "Fashion"),
    ("women silk hair scarf",            "accessories", "women", "Fashion"),
    ("women dainty layered necklace",    "accessories", "women", "Fashion"),
    # ── Women's activewear ───────────────────────────────────────────────────
    ("women sports bra medium support",  "activewear",  "women", "Fashion"),
    ("women bike shorts high waist",     "activewear",  "women", "Fashion"),
    ("women zip up hoodie gym",          "activewear",  "women", "Fashion"),
    # ── Men's tops ───────────────────────────────────────────────────────────
    ("men slim fit polo shirt",          "men_tops",    "men",   "Fashion"),
    ("men oxford button down shirt",     "men_tops",    "men",   "Fashion"),
    ("men pullover hoodie",              "men_tops",    "men",   "Fashion"),
    ("men graphic tee",                  "men_tops",    "men",   "Fashion"),
    ("men linen shirt summer",           "men_tops",    "men",   "Fashion"),
    # ── Men's bottoms ────────────────────────────────────────────────────────
    ("men slim chino pants",             "men_bottoms", "men",   "Fashion"),
    ("men slim fit jeans dark",          "men_bottoms", "men",   "Fashion"),
    ("men jogger pants",                 "men_bottoms", "men",   "Fashion"),
    # ── Men's outerwear ──────────────────────────────────────────────────────
    ("men bomber jacket",                "outerwear",   "men",   "Fashion"),
    ("men puffer vest",                  "outerwear",   "men",   "Fashion"),
    ("men wool blend overcoat",          "outerwear",   "men",   "Fashion"),
    # ── Men's shoes ──────────────────────────────────────────────────────────
    ("men white leather sneakers",       "shoes",       "men",   "Shoes"),
    ("men chelsea boots",                "shoes",       "men",   "Shoes"),
    ("men loafers casual",               "shoes",       "men",   "Shoes"),
    ("men running shoes",                "shoes",       "men",   "Shoes"),
    # ── Men's activewear ─────────────────────────────────────────────────────
    ("men gym shorts dry fit",           "activewear",  "men",   "Fashion"),
    ("men compression tights running",   "activewear",  "men",   "Fashion"),
]

_COLOR_WORDS = {
    "black", "white", "navy", "beige", "brown", "grey", "gray",
    "blue", "red", "pink", "green", "yellow", "orange", "purple",
    "cream", "tan", "camel", "olive", "burgundy", "blush", "sage",
    "khaki", "charcoal", "indigo", "rust", "gold", "silver", "nude",
}


def _extract_color(name: str) -> str:
    nl = name.lower()
    for c in _COLOR_WORDS:
        if c in nl:
            return c
    return "multi"


def _make_id(asin: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"amazon:{asin}"))


def run(limit: int = 1000, dry_run: bool = False, replace: bool = False) -> None:
    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    tag = os.environ.get("AMAZON_PARTNER_TAG", "")

    if replace and not dry_run:
        print("Deleting existing amazon-source products…")
        sb.table("products").delete().eq("source", "amazon").execute()

    # Load already-known ASINs to skip duplicates
    existing   = sb.table("products").select("asin").execute()
    seen_asins = {r["asin"] for r in (existing.data or []) if r.get("asin")}
    print(f"Products already in DB: {len(seen_asins)}")

    inserted = skipped = errors = 0

    for keywords, category, gender, search_index in QUERIES:
        if inserted >= limit:
            break
        print(f"\n🔍  {keywords!r} → {category}/{gender}", flush=True)
        try:
            items = search_items(keywords, search_index=search_index, item_count=10)
        except EnvironmentError as e:
            print(f"\n❌  {e}")
            print("\nAdd these to prototype/.env then re-run:")
            print("  AMAZON_ACCESS_KEY=<your-access-key>")
            print("  AMAZON_SECRET_KEY=<your-secret-key>")
            sys.exit(1)
        except RuntimeError as e:
            print(f"  API error: {e}")
            errors += 1
            time.sleep(3)
            continue

        for item in items:
            if inserted >= limit:
                break
            asin = item["asin"]
            if asin in seen_asins:
                skipped += 1
                continue
            if not item.get("image_url"):
                skipped += 1
                continue
            if not item.get("price") or item["price"] < 5:
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
                "price":         item["price"],
                "style":         [],
                "gender":        gender,
                "image_url":     item["image_url"],
                "affiliate_url": item["affiliate_url"],
                "partner_tag":   tag,
                "is_active":     True,
            }
            if dry_run:
                print(f"  DRY  {asin}  ${item['price']:>7.2f}  {item['name'][:55]}")
            else:
                sb.table("products").upsert(row, on_conflict="id").execute()
            inserted += 1
            print(f"  ✓ {asin}  ${item['price']:>7.2f}  {item['name'][:55]}")

        time.sleep(1.1)   # PA-API enforces ≤1 req/sec

    print(f"\n{'DRY RUN — ' if dry_run else ''}✅  inserted={inserted}  skipped={skipped}  errors={errors}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Seed DB with real Amazon fashion products")
    ap.add_argument("--limit",   type=int,  default=1000, help="max products to insert")
    ap.add_argument("--dry-run", action="store_true",     help="print without writing")
    ap.add_argument("--replace", action="store_true",     help="delete existing amazon rows first")
    args = ap.parse_args()
    run(limit=args.limit, dry_run=args.dry_run, replace=args.replace)
