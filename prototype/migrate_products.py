#!/usr/bin/env python3
"""One-time migration: seed Supabase products table from local JSON files.

Usage (from prototype/):
    python migrate_products.py                      # migrate affiliate_products.json
    python migrate_products.py --also-local         # also migrate data/products.json (demo items)
    python migrate_products.py --dry-run            # preview without writing
    python migrate_products.py --migrate-events     # also port events.jsonl → Supabase events table

Idempotent: uses upsert on conflict(id) so safe to re-run.

Env required:
    SUPABASE_URL
    SUPABASE_SECRET_KEY
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Make sure prototype/ is on path when run from root
sys.path.insert(0, str(Path(__file__).parent))

DATA_DIR = Path(__file__).parent / "data"
AFFILIATE_FILE = DATA_DIR / "affiliate_products.json"
LOCAL_FILE = DATA_DIR / "products.json"


def load_affiliate_products() -> list[dict]:
    """Load data/affiliate_products.json and normalise to Supabase schema."""
    with AFFILIATE_FILE.open(encoding="utf-8") as f:
        raw = json.load(f)

    records = []
    for item in raw:
        if item.get("_comment"):
            continue  # skip placeholder rows
        records.append(
            {
                "id": item["id"],
                "source": "curated",
                "asin": item.get("asin") or item.get("id"),
                "name": item["name"],
                "category": item["category"],
                "color": item.get("color"),
                "price": float(item["price"]) if item.get("price") is not None else None,
                "style": item.get("style") or [],
                "gender": item.get("gender", "unisex"),
                "image_url": item.get("image_url"),
                "affiliate_url": item.get("affiliate_url"),
                "partner_tag": os.environ.get("AMAZON_PARTNER_TAG"),
                "is_active": True,
            }
        )
    return records


def load_local_products() -> list[dict]:
    """Load data/products.json (demo catalog) and normalise to Supabase schema."""
    with LOCAL_FILE.open(encoding="utf-8") as f:
        raw = json.load(f)

    records = []
    for item in raw:
        records.append(
            {
                "id": item["id"],
                "source": "local",
                "asin": None,
                "name": item["name"],
                "category": item["category"],
                "color": item.get("color"),
                "price": float(item["price"]) if item.get("price") is not None else None,
                "style": item.get("style") or [],
                "gender": item.get("gender", "unisex"),
                "image_url": None,
                "affiliate_url": None,
                "partner_tag": None,
                "is_active": True,
            }
        )
    return records


def upsert_to_supabase(records: list[dict], dry_run: bool = False) -> int:
    """Upsert records into Supabase products table in chunks."""
    if dry_run:
        print(f"[dry-run] Would upsert {len(records)} products:")
        for r in records:
            print(f"  {r['id']} | {r['source']:8} | {r['name'][:50]}")
        return len(records)

    from supabase import create_client
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SECRET_KEY", "")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SECRET_KEY must be set.", file=sys.stderr)
        sys.exit(1)

    db = create_client(url, key)
    chunk_size = 100
    total = 0
    for i in range(0, len(records), chunk_size):
        chunk = records[i : i + chunk_size]
        db.table("products").upsert(chunk, on_conflict="id").execute()
        total += len(chunk)
        print(f"  upserted {total}/{len(records)} products…")

    return total


def migrate_events(dry_run: bool = False) -> int:
    """Port existing events.jsonl → Supabase events table."""
    from event_store import migrate_jsonl_to_supabase
    if dry_run:
        jsonl = DATA_DIR / "events.jsonl"
        if not jsonl.exists():
            print("[dry-run] No events.jsonl found.")
            return 0
        count = sum(1 for _ in jsonl.open(encoding="utf-8") if _.strip())
        print(f"[dry-run] Would migrate {count} events from events.jsonl → Supabase.")
        return count
    return migrate_jsonl_to_supabase()


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate product/event data to Supabase")
    parser.add_argument("--also-local", action="store_true",
                        help="Also migrate data/products.json (demo catalog)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without writing to Supabase")
    parser.add_argument("--migrate-events", action="store_true",
                        help="Also port events.jsonl → Supabase events table")
    args = parser.parse_args()

    print("=== Mira — Supabase product migration ===\n")

    # Affiliate products (primary real catalog)
    print(f"Loading {AFFILIATE_FILE.name}…")
    affiliate = load_affiliate_products()
    print(f"  {len(affiliate)} curated affiliate products found.")
    upsert_to_supabase(affiliate, dry_run=args.dry_run)

    # Demo / local catalog (optional)
    if args.also_local and LOCAL_FILE.exists():
        print(f"\nLoading {LOCAL_FILE.name}…")
        local = load_local_products()
        print(f"  {len(local)} local demo products found.")
        upsert_to_supabase(local, dry_run=args.dry_run)

    # Events migration (optional)
    if args.migrate_events:
        print("\nMigrating events.jsonl…")
        n = migrate_events(dry_run=args.dry_run)
        print(f"  Done: {n} events.")

    print("\nMigration complete.")
    if not args.dry_run:
        print("Tip: set PRODUCT_SOURCE=supabase in .env and restart the server.")


if __name__ == "__main__":
    main()
