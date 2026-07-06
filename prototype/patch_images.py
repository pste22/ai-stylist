#!/usr/bin/env python3
"""Patch image_url for all expanded products with verified Unsplash photo IDs."""
from __future__ import annotations
import json, os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

DATA_FILE = Path(__file__).parent / "data" / "affiliate_products.json"

# 25 confirmed-working Unsplash fashion/lifestyle photo IDs
VERIFIED = [
    "1515886657613-9f3515b0c78f",
    "1512436991641-6745cdb1723f",
    "1469334031218-e382a71b716b",
    "1490481651871-ab68de25d43d",
    "1542291026-7eec264c27ff",
    "1525562723836-dca67a71d5f1",
    "1434389677669-e08b4cac3105",
    "1539109136881-3be0616acf4b",
    "1468495244123-6c6c332eeece",
    "1509631179647-0177331693ae",
    "1491553895911-0055eca6402d",
    "1521572163474-6864f9cf17ab",
    "1503342217505-b0a15ec3261c",
    "1543163521-1bf539c55dd2",
    "1556905055-8f358a7a47b2",
    "1617038260897-41a1f14a8ca0",
    "1604695573706-53170668f6a6",
    "1562157873-818bc0726f68",
    "1507003211169-0a1dd7228f2d",
    "1553062407-98eeb64c6a62",
    "1584917865442-de89df76afd3",
    "1606760227091-3dd870d97f1d",
    "1571019613454-1cb2f99b2d8b",
    "1518310383802-640c2de311b2",
    "1602810316498-ab67cf68c8e1",
]

def photo_url(product_id: str) -> str:
    idx = abs(hash(product_id)) % len(VERIFIED)
    return f"https://images.unsplash.com/photo-{VERIFIED[idx]}?w=500&q=80&fit=crop&auto=format"

def main():
    with DATA_FILE.open() as f:
        products = json.load(f)

    patched = 0
    for p in products:
        url = p.get("image_url", "")
        # Patch any unsplash URL — some IDs from the previous run were still 404
        needs_patch = not url or "images.unsplash.com" in url
        if needs_patch:
            p["image_url"] = photo_url(p["id"])
            patched += 1

    print(f"Patched {patched} / {len(products)} products")
    with DATA_FILE.open("w") as f:
        json.dump(products, f, indent=2)
    print(f"Written to {DATA_FILE}")

    # Update in Supabase
    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    updated = 0
    for p in products:
        if p.get("image_url") and "images.unsplash.com" in p["image_url"]:
            sb.table("products").update({"image_url": p["image_url"]}).eq("id", p["id"]).execute()
            updated += 1
    print(f"Updated {updated} products in Supabase ✓")

if __name__ == "__main__":
    main()
