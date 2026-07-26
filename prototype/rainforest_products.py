"""
Rainforest API client — real Amazon product data without PA-API credentials.

Why this instead of PA-API:
  PA-API requires 10 qualifying sales in 30 days (you don't have them yet).
  Rainforest API wraps Amazon data directly — no sales requirement, instant access.

Sign up (free trial = 100 requests = ~1 000 products):
  https://www.rainforestapi.com/  →  "Start Free Trial"
  Copy your API key and add to prototype/.env:
    RAINFOREST_API_KEY=your_key_here

Pricing after trial:
  Starter : $15/mo  →    750 requests  (~  7 500 products)
  Business: $50/mo  →  5 000 requests  (~ 50 000 products)
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
import urllib.error

BASE_URL = "https://api.rainforestapi.com/request"


def search_products(
    query: str,
    *,
    page: int = 1,
    api_key: str | None = None,
    amazon_domain: str = "amazon.in",
    sort_by: str = "featured",       # featured | average_review | price_low_to_high
) -> list[dict]:
    """
    Search Amazon via Rainforest API.

    Returns list of:
      {asin, name, brand, image_url, price, rating, ratings_total, affiliate_url}
    Raises EnvironmentError if RAINFOREST_API_KEY is not set.
    Raises RuntimeError on API error.
    """
    key = api_key or os.environ.get("RAINFOREST_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "RAINFOREST_API_KEY not set. "
            "Sign up free at https://www.rainforestapi.com/ and add it to prototype/.env"
        )
    tag = os.environ.get("AMAZON_PARTNER_TAG", "")

    params = {
        "api_key":       key,
        "type":          "search",
        "amazon_domain": amazon_domain,
        "search_term":   query,
        "sort_by":       sort_by,
        "page":          str(page),
    }
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "mira-stylist/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Rainforest API HTTP {e.code}: {body[:400]}") from e

    results = []
    for item in data.get("search_results", []):
        asin = item.get("asin", "")
        if not asin:
            continue
        title = item.get("title", "") or ""
        brand = item.get("brand", "") or ""
        image = item.get("image", "") or ""
        price_raw = (item.get("price", {}) or {}).get("value") or \
                    (item.get("prices", [{}]) or [{}])[0].get("value") or 0
        rating        = item.get("rating", 0) or 0
        ratings_total = item.get("ratings_total", 0) or 0

        affiliate_url = (
            f"https://www.amazon.in/dp/{asin}"
            f"?tag={tag}&linkCode=ll1"
            if tag else f"https://www.amazon.in/dp/{asin}"
        )
        if not image or not title:
            continue
        results.append({
            "asin":          asin,
            "name":          title[:140],
            "brand":         brand,
            "image_url":     image,
            "price":         round(float(price_raw), 2) if price_raw else 0.0,
            "rating":        float(rating),
            "ratings_total": int(ratings_total),
            "affiliate_url": affiliate_url,
        })
    return results
