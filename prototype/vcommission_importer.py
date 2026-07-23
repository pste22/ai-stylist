"""VCommission affiliate feed importer.

Pulls product feeds for Myntra, Ajio, Nykaa Fashion, and Amazon India from
VCommission's publisher API and upserts them into Supabase.

Usage (once you have credentials):
  python vcommission_importer.py --dry-run          # print stats, no writes
  python vcommission_importer.py                    # full sync all advertisers
  python vcommission_importer.py --advertiser myntra  # one advertiser only

Environment variables (add to prototype/.env):
  VC_API_KEY          Your VCommission publisher API key
  VC_PUBLISHER_ID     Your VCommission publisher / affiliate ID
  SUPABASE_URL        Supabase project URL (already set)
  SUPABASE_SECRET_KEY Supabase service-role key (already set)

VCommission API docs: https://help.vcommission.com/publisher/api
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── VCommission advertiser config ────────────────────────────────────────────
# offer_id: VCommission's internal program/offer ID for each brand.
# Fill these in once your account is approved and you can see them in the
# Publisher dashboard → My Programs.

@dataclass
class Advertiser:
    key: str           # slug used as source identifier in DB
    name: str          # human label
    offer_id: str      # VCommission offer/program ID — fill in from dashboard
    feed_url: str      # product feed URL template (use {api_key} placeholder)
    feed_format: str   # "xml" | "json" | "csv"
    category_map: dict[str, str] = field(default_factory=dict)

ADVERTISERS: dict[str, Advertiser] = {
    "myntra": Advertiser(
        key="myntra",
        name="Myntra",
        offer_id="FILL_IN_FROM_DASHBOARD",
        # VCommission product feed URL — check your dashboard for the exact URL.
        # Typical pattern:
        feed_url="https://api.vcommission.com/v2/feeds?key={api_key}&offer_id={offer_id}&format=xml",
        feed_format="xml",
        category_map={
            "Kurtas": "tops",
            "Kurtis": "tops",
            "Tops": "tops",
            "T-Shirts": "tops",
            "Shirts": "tops",
            "Blouses": "tops",
            "Dresses": "dresses",
            "Gowns": "dresses",
            "Sarees": "dresses",
            "Lehengas": "dresses",
            "Jeans": "bottoms",
            "Trousers": "bottoms",
            "Skirts": "bottoms",
            "Shorts": "bottoms",
            "Leggings": "bottoms",
            "Palazzos": "bottoms",
            "Jackets": "outerwear",
            "Blazers": "outerwear",
            "Coats": "outerwear",
            "Sweaters": "outerwear",
            "Sweatshirts": "outerwear",
            "Shrugs": "outerwear",
            "Heels": "shoes",
            "Flats": "shoes",
            "Sneakers": "shoes",
            "Sandals": "shoes",
            "Footwear": "shoes",
            "Handbags": "bags",
            "Clutches": "bags",
            "Jewellery": "accessories",
            "Watches": "accessories",
            "Sunglasses": "accessories",
            "Belts": "accessories",
            "Scarves": "accessories",
        },
    ),
    "ajio": Advertiser(
        key="ajio",
        name="Ajio",
        offer_id="FILL_IN_FROM_DASHBOARD",
        feed_url="https://api.vcommission.com/v2/feeds?key={api_key}&offer_id={offer_id}&format=xml",
        feed_format="xml",
        category_map={
            "Dresses": "dresses",
            "Kurtas & Suits": "tops",
            "Tops": "tops",
            "T-Shirts": "tops",
            "Shirts": "tops",
            "Jeans": "bottoms",
            "Trousers": "bottoms",
            "Skirts": "bottoms",
            "Jackets": "outerwear",
            "Blazers": "outerwear",
            "Footwear": "shoes",
            "Bags": "bags",
            "Accessories": "accessories",
        },
    ),
    "nykaa_fashion": Advertiser(
        key="nykaa_fashion",
        name="Nykaa Fashion",
        offer_id="FILL_IN_FROM_DASHBOARD",
        feed_url="https://api.vcommission.com/v2/feeds?key={api_key}&offer_id={offer_id}&format=xml",
        feed_format="xml",
        category_map={
            "Dresses": "dresses",
            "Tops": "tops",
            "Kurtas": "tops",
            "Bottoms": "bottoms",
            "Jeans": "bottoms",
            "Skirts": "bottoms",
            "Outerwear": "outerwear",
            "Jackets": "outerwear",
            "Shoes": "shoes",
            "Heels": "shoes",
            "Flats": "shoes",
            "Bags": "bags",
            "Jewellery": "accessories",
            "Accessories": "accessories",
        },
    ),
    "amazon_india": Advertiser(
        key="amazon_india",
        name="Amazon India Fashion",
        offer_id="FILL_IN_FROM_DASHBOARD",
        feed_url="https://api.vcommission.com/v2/feeds?key={api_key}&offer_id={offer_id}&format=xml",
        feed_format="xml",
        category_map={
            "Clothing": "tops",
            "Women's Clothing": "dresses",
            "Men's Clothing": "tops",
            "Dresses": "dresses",
            "Tops & Tees": "tops",
            "Jeans": "bottoms",
            "Trousers": "bottoms",
            "Skirts": "bottoms",
            "Jackets & Coats": "outerwear",
            "Shoes": "shoes",
            "Handbags & Clutches": "bags",
            "Jewellery": "accessories",
            "Watches": "accessories",
            "Sunglasses": "accessories",
        },
    ),
}

# ── Valid categories in our schema ────────────────────────────────────────────
VALID_CATEGORIES = {"dresses", "tops", "bottoms", "outerwear", "shoes", "bags", "accessories"}

# ── Deeplink builder ──────────────────────────────────────────────────────────

def build_affiliate_url(product_url: str, publisher_id: str, offer_id: str) -> str:
    """Generate a VCommission tracking deeplink for a product URL.

    VCommission deeplink format (verify against your dashboard):
      https://click.vcmm.in/?aff_id=PUBLISHER_ID&offer_id=OFFER_ID&url=ENCODED_URL
    """
    encoded = urllib.parse.quote(product_url, safe="")
    return (
        f"https://click.vcmm.in/"
        f"?aff_id={publisher_id}&offer_id={offer_id}&url={encoded}"
    )


# ── Feed fetcher ──────────────────────────────────────────────────────────────

def fetch_feed(url: str, timeout: int = 30) -> bytes:
    """Download a feed URL and return raw bytes."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mira-Stylist/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# ── XML parser (covers Myntra, Ajio, Nykaa, Amazon India VCommission feeds) ──

def _text(el: ET.Element | None, tag: str, default: str = "") -> str:
    if el is None:
        return default
    child = el.find(tag)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def parse_xml_feed(raw: bytes, advertiser: Advertiser,
                   publisher_id: str) -> list[dict]:
    """Parse a VCommission XML product feed into our schema rows.

    VCommission feeds vary slightly per advertiser but share common tags.
    Adjust tag names below if the actual feed uses different ones.
    """
    root = ET.fromstring(raw)
    # VCommission feeds usually wrap items in <products><product>...</product></products>
    # or <items><item>...</item></items>. Try both.
    items = root.findall(".//product") or root.findall(".//item")
    log.info("  Parsed %d raw items from %s feed", len(items), advertiser.name)

    products: list[dict] = []
    skipped = 0
    for item in items:
        # ── Core fields ───────────────────────────────────────────────────────
        sku        = _text(item, "id") or _text(item, "sku") or _text(item, "product_id")
        name       = _text(item, "name") or _text(item, "title")
        raw_price  = _text(item, "sale_price") or _text(item, "price") or _text(item, "selling_price")
        image_url  = _text(item, "image") or _text(item, "image_url") or _text(item, "image_link")
        product_url = _text(item, "url") or _text(item, "link") or _text(item, "product_url")
        raw_cat    = _text(item, "category") or _text(item, "product_type")
        color      = _text(item, "color") or _text(item, "colour")
        brand      = _text(item, "brand")
        gender_raw = _text(item, "gender").lower()

        # ── Validate required fields ──────────────────────────────────────────
        if not (sku and name and product_url and image_url):
            skipped += 1
            continue
        try:
            price = float(re.sub(r"[^\d.]", "", raw_price))
        except ValueError:
            skipped += 1
            continue
        if price <= 0:
            skipped += 1
            continue

        # ── Category normalisation ────────────────────────────────────────────
        category = advertiser.category_map.get(raw_cat, "")
        if not category:
            # Try partial match on first word of category
            first = raw_cat.split()[0] if raw_cat else ""
            category = advertiser.category_map.get(first, "")
        if category not in VALID_CATEGORIES:
            skipped += 1
            continue

        # ── Gender ────────────────────────────────────────────────────────────
        if "men" in gender_raw and "women" not in gender_raw:
            gender = "men"
        elif "women" in gender_raw or "female" in gender_raw or "girl" in gender_raw:
            gender = "women"
        else:
            gender = "unisex"

        # ── Build affiliate tracking URL ──────────────────────────────────────
        affiliate_url = build_affiliate_url(product_url, publisher_id, advertiser.offer_id)

        # ── Compose product ID (source-scoped) ───────────────────────────────
        product_id = f"vc-{advertiser.key}-{sku}"

        products.append({
            "id":            product_id,
            "source":        f"vcommission_{advertiser.key}",
            "name":          f"{brand} {name}".strip() if brand else name,
            "category":      category,
            "color":         color or None,
            "price":         price,
            "currency":      "INR",
            "style":         [],
            "gender":        gender,
            "image_url":     image_url,
            "affiliate_url": affiliate_url,
            "is_active":     True,
            "vc_advertiser": advertiser.key,
            "vc_sku":        sku,
        })

    log.info("  → %d valid products, %d skipped", len(products), skipped)
    return products


# ── Supabase upserter ─────────────────────────────────────────────────────────

def upsert_to_supabase(products: list[dict]) -> dict:
    """Upsert products into Supabase. Returns {"inserted": N, "updated": N}."""
    from supabase import create_client

    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SECRET_KEY"]
    db = create_client(url, key)

    BATCH = 200
    total_upserted = 0
    for i in range(0, len(products), BATCH):
        batch = products[i : i + BATCH]
        result = (
            db.table("products")
            .upsert(batch, on_conflict="id")
            .execute()
        )
        total_upserted += len(batch)
        log.info("  Upserted batch %d–%d", i + 1, i + len(batch))
        time.sleep(0.1)  # stay under Supabase rate limits

    return {"upserted": total_upserted}


def mark_inactive(advertiser_key: str, active_ids: set[str]) -> int:
    """Mark products from this advertiser that are no longer in the feed as inactive."""
    from supabase import create_client

    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SECRET_KEY"]
    db = create_client(url, key)

    # Fetch all current IDs for this advertiser
    result = (
        db.table("products")
        .select("id")
        .eq("vc_advertiser", advertiser_key)
        .eq("is_active", True)
        .execute()
    )
    existing_ids = {row["id"] for row in (result.data or [])}
    stale_ids = existing_ids - active_ids

    if stale_ids:
        db.table("products").update({"is_active": False}).in_("id", list(stale_ids)).execute()
        log.info("  Marked %d products inactive (no longer in feed)", len(stale_ids))
    return len(stale_ids)


# ── Main sync logic ───────────────────────────────────────────────────────────

def sync_advertiser(
    advertiser: Advertiser,
    api_key: str,
    publisher_id: str,
    dry_run: bool = False,
) -> dict:
    log.info("▶ %s (offer_id=%s)", advertiser.name, advertiser.offer_id)

    if advertiser.offer_id.startswith("FILL_IN"):
        log.warning("  ⚠️  offer_id not configured — skipping %s", advertiser.name)
        return {"skipped": True, "reason": "offer_id not set"}

    feed_url = advertiser.feed_url.format(api_key=api_key, offer_id=advertiser.offer_id)
    log.info("  Fetching feed: %s", feed_url)

    try:
        raw = fetch_feed(feed_url)
    except Exception as exc:
        log.error("  Feed fetch failed: %s", exc)
        return {"error": str(exc)}

    if advertiser.feed_format == "xml":
        products = parse_xml_feed(raw, advertiser, publisher_id)
    else:
        log.error("  Unsupported feed format: %s", advertiser.feed_format)
        return {"error": "unsupported format"}

    if dry_run:
        log.info("  DRY RUN — would upsert %d products", len(products))
        if products:
            log.info("  Sample product: %s", json.dumps(products[0], indent=2))
        return {"dry_run": True, "would_upsert": len(products)}

    result = upsert_to_supabase(products)
    active_ids = {p["id"] for p in products}
    stale_count = mark_inactive(advertiser.key, active_ids)
    return {**result, "deactivated": stale_count}


def load_env() -> None:
    """Load prototype/.env if running standalone."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    load_env()

    parser = argparse.ArgumentParser(description="VCommission feed importer")
    parser.add_argument("--dry-run", action="store_true", help="Fetch & parse but don't write to DB")
    parser.add_argument("--advertiser", choices=list(ADVERTISERS), help="Sync only one advertiser")
    args = parser.parse_args()

    api_key      = os.environ.get("VC_API_KEY", "")
    publisher_id = os.environ.get("VC_PUBLISHER_ID", "")

    if not api_key or not publisher_id:
        log.error(
            "VC_API_KEY and VC_PUBLISHER_ID must be set in prototype/.env\n"
            "  Get them from your VCommission publisher dashboard → Settings → API"
        )
        raise SystemExit(1)

    targets = [ADVERTISERS[args.advertiser]] if args.advertiser else list(ADVERTISERS.values())

    summary: dict[str, dict] = {}
    for adv in targets:
        result = sync_advertiser(adv, api_key, publisher_id, dry_run=args.dry_run)
        summary[adv.key] = result

    log.info("\n── Import summary ──")
    for k, v in summary.items():
        log.info("  %-20s %s", k, v)


if __name__ == "__main__":
    main()
