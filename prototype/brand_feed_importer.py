"""Direct brand / D2C product feed importer (CSV).

Use this when a brand (Snitch, etc.) partners with Mira outside VCommission.
Works today — no network approval required.

Usage:
  python brand_feed_importer.py --file data/brand_feed_template.csv --retailer snitch --dry-run
  python brand_feed_importer.py --file /path/to/snitch.csv --retailer snitch

CSV columns (required): id, name, price, image_url, affiliate_url
Optional: brand, category, color, currency, gender, size_range, style

Env: SUPABASE_URL, SUPABASE_SECRET_KEY
"""
from __future__ import annotations

import argparse
import csv
import logging
import os
import re
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

VALID_CATEGORIES = {
    "dresses", "tops", "bottoms", "outerwear", "shoes", "bags", "accessories", "activewear",
}

CATEGORY_ALIASES = {
    "dress": "dresses", "gown": "dresses", "kurta": "tops", "shirt": "tops",
    "tshirt": "tops", "t-shirt": "tops", "top": "tops", "jeans": "bottoms",
    "trouser": "bottoms", "pants": "bottoms", "skirt": "bottoms",
    "jacket": "outerwear", "blazer": "outerwear", "sneaker": "shoes",
    "heel": "shoes", "bag": "bags", "watch": "accessories",
}


def _norm_category(raw: str) -> str:
    s = (raw or "").strip().lower()
    if s in VALID_CATEGORIES:
        return s
    for k, v in CATEGORY_ALIASES.items():
        if k in s:
            return v
    return "accessories"


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "brand"


def load_csv(path: Path, retailer: str) -> list[dict]:
    rows: list[dict] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            pid = (row.get("id") or "").strip()
            name = (row.get("name") or "").strip()
            url = (row.get("affiliate_url") or row.get("url") or "").strip()
            image = (row.get("image_url") or "").strip()
            if not pid or not name or not url:
                log.warning("  skip line %d — missing id/name/url", i)
                continue
            try:
                price = float(str(row.get("price") or "0").replace(",", "").replace("₹", ""))
            except ValueError:
                log.warning("  skip line %d — bad price", i)
                continue
            brand = (row.get("brand") or retailer).strip()
            retailer_slug = _slug(brand or retailer)
            style_raw = (row.get("style") or "").strip()
            styles = [s.strip() for s in re.split(r"[|,]", style_raw) if s.strip()]
            gender = (row.get("gender") or "unisex").strip().lower()
            if gender not in ("men", "women", "unisex"):
                gender = "unisex"
            # Keep stable ids even when CSV mixes multiple brands
            product_id = pid if pid.startswith("brand-") else f"brand-{retailer_slug}-{pid}"
            rows.append({
                "id": product_id,
                "source": f"brand_{retailer_slug}",
                "asin": None,
                "name": name if name.lower().startswith(brand.lower()) else f"{brand} {name}",
                "brand": brand,
                "category": _norm_category(row.get("category") or ""),
                "color": (row.get("color") or None),
                "price": price,
                "style": styles,
                "gender": gender,
                "image_url": image or None,
                "affiliate_url": url,
                "partner_tag": f"direct-{retailer_slug}",
                "is_active": True,
                "facets": {
                    "retailer": retailer_slug,
                    "retailer_label": brand.title() if brand else retailer.title(),
                    "size_range": (row.get("size_range") or "").strip() or None,
                    "feed": "brand_csv",
                },
            })
    return rows


def upsert(products: list[dict]) -> int:
    from supabase import create_client
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SECRET_KEY"]
    db = create_client(url, key)
    # Strip facets if column missing — try full first
    batch_size = 100
    n = 0
    for i in range(0, len(products), batch_size):
        batch = products[i : i + batch_size]
        try:
            db.table("products").upsert(batch, on_conflict="id").execute()
        except Exception:
            slim = [{k: v for k, v in p.items() if k != "facets"} for p in batch]
            db.table("products").upsert(slim, on_conflict="id").execute()
        n += len(batch)
        time.sleep(0.05)
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description="Import a brand CSV feed into Mira")
    ap.add_argument("--file", required=True, help="Path to CSV")
    ap.add_argument("--retailer", required=True, help="Retailer slug e.g. snitch")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = Path(args.file).expanduser()
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    products = load_csv(path, args.retailer)
    log.info("Parsed %d products for retailer=%s", len(products), args.retailer)
    if not products:
        raise SystemExit("No products parsed")

    if args.dry_run:
        for p in products[:5]:
            log.info("  sample: %s | ₹%s | %s", p["id"], p["price"], p["affiliate_url"][:60])
        log.info("Dry run — no writes")
        return

    n = upsert(products)
    log.info("Upserted %d products", n)


if __name__ == "__main__":
    main()
