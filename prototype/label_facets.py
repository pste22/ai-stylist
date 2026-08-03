"""Label all active products with filter facets and persist to Supabase.

Usage:
  python label_facets.py            # enrich + upsert brand/facets
  python label_facets.py --dry-run  # print coverage stats only

Requires migrate_product_facets.sql to have been applied (brand + facets columns).
If columns are missing, prints the SQL path and still shows dry-run coverage.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

from dotenv import load_dotenv

load_dotenv()

from product_facets import enrich_product  # noqa: E402


def load_all(client):
    rows = []
    start = 0
    while True:
        page = (
            client.table("products")
            .select("id,name,category,color,price,gender,style,created_at,brand,facets")
            .eq("is_active", True)
            .range(start, start + 999)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        if len(page) < 1000:
            break
        start += 1000
    return rows


def coverage(enriched: list[dict]) -> dict:
    keys = [
        "brand", "colour", "material", "size", "specialty_size", "length",
        "pattern", "fit", "shape", "collar", "multipack", "occasion",
        "new_in", "adaptive", "licensed",
    ]
    out = {}
    n = len(enriched) or 1
    for k in keys:
        hit = 0
        for p in enriched:
            f = p.get("facets") or {}
            v = f.get(k) if k != "brand" else (p.get("brand") or f.get("brand"))
            if v not in (None, "", [], False):
                hit += 1
        out[k] = f"{hit}/{len(enriched)} ({100*hit/n:.0f}%)"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SECRET_KEY", "")
    if not url or not key:
        print("SUPABASE_URL / SUPABASE_SECRET_KEY required", file=sys.stderr)
        return 1

    from supabase import create_client
    client = create_client(url, key)

    try:
        rows = load_all(client)
    except Exception as exc:
        print(f"Failed to load products (apply migrate_product_facets.sql first?): {exc}")
        # Fallback without brand/facets columns
        rows = []
        start = 0
        while True:
            page = (
                client.table("products")
                .select("id,name,category,color,price,gender,style,created_at")
                .eq("is_active", True)
                .range(start, start + 999)
                .execute()
                .data
                or []
            )
            rows.extend(page)
            if len(page) < 1000:
                break
            start += 1000
        print(f"Loaded {len(rows)} rows without brand/facets columns.")
        print("Run prototype/migrate_product_facets.sql in the Supabase SQL editor, then re-run.")

    enriched = [enrich_product(r) for r in rows]
    print("coverage:")
    for k, v in coverage(enriched).items():
        print(f"  {k:16} {v}")
    brands = Counter(p.get("brand") for p in enriched if p.get("brand"))
    print("top brands:", brands.most_common(10))

    if args.dry_run:
        return 0

    # Upsert in batches
    batch = []
    updated = 0
    for p in enriched:
        batch.append({
            "id": p["id"],
            "brand": p.get("brand"),
            "facets": p.get("facets") or {},
        })
        if len(batch) >= 100:
            try:
                client.table("products").upsert(batch, on_conflict="id").execute()
            except Exception as exc:
                print("Upsert failed — apply migrate_product_facets.sql first.", exc)
                return 1
            updated += len(batch)
            batch = []
            print(f"  upserted {updated}…")
    if batch:
        try:
            client.table("products").upsert(batch, on_conflict="id").execute()
        except Exception as exc:
            print("Upsert failed — apply migrate_product_facets.sql first.", exc)
            return 1
        updated += len(batch)
    print(f"Done. Labeled {updated} products.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
