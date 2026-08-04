#!/usr/bin/env python3
"""Backfill Amazon image galleries via Rainforest type=product.

Search only returns the main hero image. The PDP call returns the full
thumbnail strip (front / back / detail / …) Amazon shows on the listing.

Cost: 1 Rainforest credit per ASIN.

Usage (from prototype/):
  .venv/bin/python enrich_amazon_galleries.py --limit 50
  .venv/bin/python enrich_amazon_galleries.py --limit 200 --sleep 1.2
  .venv/bin/python enrich_amazon_galleries.py --asin B0XXXX --dry-run

Requires: RAINFOREST_API_KEY, SUPABASE_URL, SUPABASE_SECRET_KEY in .env
Also run migrate_product_image_urls.sql once in Supabase.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sys.path.insert(0, os.path.dirname(__file__))

from rainforest_products import get_product  # noqa: E402


def _needs_gallery(row: dict) -> bool:
    urls = row.get("image_urls") or []
    if isinstance(urls, str):
        return True
    return len(urls) < 2


def run(*, limit: int, sleep_s: float, dry_run: bool, asin: str | None) -> None:
    from supabase import create_client

    if not os.environ.get("RAINFOREST_API_KEY"):
        print("❌  RAINFOREST_API_KEY missing in prototype/.env")
        sys.exit(1)

    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

    if asin:
        rows = [{"id": asin, "asin": asin, "image_urls": []}]
    else:
        # Prefer Amazon rows that still only have a single (or no) gallery image
        res = (
            sb.table("products")
            .select("id,asin,image_url,image_urls")
            .eq("source", "amazon")
            .eq("is_active", True)
            .not_.is_("asin", "null")
            .limit(min(limit * 3, 3000))
            .execute()
        )
        rows = [r for r in (res.data or []) if r.get("asin") and _needs_gallery(r)]
        rows = rows[:limit]

    print(f"Enriching {len(rows)} product(s)…\n")
    ok = fail = skipped = 0

    for i, row in enumerate(rows, 1):
        a = row["asin"]
        print(f"[{i}/{len(rows)}] {a}", flush=True)
        try:
            detail = get_product(a)
        except Exception as exc:
            print(f"   ✗ {exc}")
            fail += 1
            time.sleep(sleep_s)
            continue

        urls = detail.get("image_urls") or []
        if len(urls) < 2:
            print(f"   · only {len(urls)} image(s) on PDP — skipped")
            skipped += 1
            time.sleep(sleep_s)
            continue

        patch = {
            "image_url":  urls[0],
            "image_urls": urls,
        }
        if dry_run:
            print(f"   DRY  {len(urls)} images  first={urls[0][:70]}…")
        else:
            sb.table("products").update(patch).eq("asin", a).execute()
            print(f"   ✓  {len(urls)} images saved")
        ok += 1
        time.sleep(sleep_s)

    print(f"\n✅  updated={ok}  skipped={skipped}  errors={fail}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Enrich Amazon products with full image galleries")
    ap.add_argument("--limit", type=int, default=50, help="max ASINs to enrich")
    ap.add_argument("--sleep", type=float, default=1.2, help="seconds between API calls")
    ap.add_argument("--asin", default=None, help="enrich a single ASIN")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run(limit=args.limit, sleep_s=args.sleep, dry_run=args.dry_run, asin=args.asin)
