"""One-time script: patch all Amazon product URLs in Supabase to use mirastylist-21.

Run once:
  cd prototype && python patch_amazon_tag.py
"""
import os, re, sys

TAG = "mirastylist-21"

def load_env():
    env = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env): return
    for line in open(env):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

load_env()

from supabase import create_client
db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# Fetch all active Amazon products (have an ASIN or amazon.com URL)
result = db.table("products").select("id,asin,affiliate_url").eq("is_active", True).execute()
products = result.data or []
amazon = [p for p in products if p.get("asin") or
          ("amazon." in (p.get("affiliate_url") or ""))]

print(f"Found {len(amazon)} Amazon products to patch")

updated = 0
for p in amazon:
    url = p.get("affiliate_url") or ""
    asin = p.get("asin") or ""

    # Build canonical tagged URL
    if asin:
        new_url = f"https://www.amazon.in/dp/{asin}/?tag={TAG}"
    elif "amazon." in url:
        # Strip any existing tag and add ours
        url_clean = re.sub(r"[?&]tag=[^&]*", "", url).rstrip("?&")
        sep = "&" if "?" in url_clean else "?"
        new_url = f"{url_clean}{sep}tag={TAG}"
    else:
        continue

    if new_url == url:
        continue

    db.table("products").update({
        "affiliate_url": new_url,
        "partner_tag": TAG,
    }).eq("id", p["id"]).execute()
    updated += 1

print(f"✅ Patched {updated} product URLs → tag={TAG}")
