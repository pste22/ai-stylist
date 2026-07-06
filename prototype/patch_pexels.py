"""
Patch all products with category-appropriate Pexels CDN photo URLs.
These photo IDs are confirmed HTTP 200 from Codespaces.
"""
import json, os, sys, pathlib
from supabase import create_client

DATA_FILE = pathlib.Path(__file__).parent / "data" / "affiliate_products.json"

# Confirmed working Pexels photo IDs mapped to fashion categories.
# Each list has multiple IDs so adjacent products in the same category
# get visually distinct photos (deterministic via hash % len).
CATEGORY_PHOTOS: dict[str, list[int]] = {
    "dresses":     [1536619, 2220316, 1375736, 2584285, 3622608],
    "tops":        [996329,  1021693, 2682452, 4348401, 3622609],
    "bottoms":     [2385477, 4609110, 5709894, 8386440, 7760462],
    "outerwear":   [2303846, 5699516, 4345149, 934070,  6069245],
    "shoes":       [298863,  1040173, 1457983, 1456706, 4623619],
    "bags":        [1055691, 1126993, 937481,  2303846, 5699516],
    "accessories": [934070,  4345149, 2682452, 1375736, 5710984],
    "activewear":  [5710984, 7760462, 5709894, 4609110, 3622609],
    "men_tops":    [937481,  1126993, 6069245, 4348401, 2682452],
    "men_bottoms": [8386440, 2385477, 4609110, 7760462, 3622608],
}

FALLBACK = [1536619, 2220316, 1375736, 998863, 2303846]


def pexels_url(photo_id: int) -> str:
    return (
        f"https://images.pexels.com/photos/{photo_id}/"
        f"pexels-photo-{photo_id}.jpeg"
        f"?auto=compress&cs=tinysrgb&w=500&h=650&fit=crop"
    )


def photo_for(product: dict) -> str:
    cat = (product.get("category") or "").lower()
    pool = CATEGORY_PHOTOS.get(cat, FALLBACK)
    idx = abs(hash(product["id"])) % len(pool)
    return pexels_url(pool[idx])


def main():
    # ── Load JSON ──────────────────────────────────────────────────────────
    with open(DATA_FILE) as f:
        products = json.load(f)

    patched = []
    for p in products:
        p["image_url"] = photo_for(p)
        patched.append(p)

    with open(DATA_FILE, "w") as f:
        json.dump(patched, f, indent=2)
    print(f"Patched {len(patched)} products in {DATA_FILE}")

    # ── Push to Supabase ───────────────────────────────────────────────────
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        dotenv = pathlib.Path(__file__).parent / ".env"
        if dotenv.exists():
            for line in dotenv.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")

    if not url or not key:
        print("No Supabase credentials found — skipping DB update")
        return

    sb = create_client(url, key)
    ok = err = 0
    for p in patched:
        try:
            sb.table("products").update({"image_url": p["image_url"]}).eq("id", p["id"]).execute()
            ok += 1
        except Exception as e:
            print(f"  ERROR {p['id']}: {e}")
            err += 1

    print(f"Supabase: {ok} updated, {err} errors")


if __name__ == "__main__":
    main()
