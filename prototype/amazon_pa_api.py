"""
Amazon Product Advertising API v5 — lightweight client (no SDK needed).

Required env vars (add to prototype/.env):
  AMAZON_ACCESS_KEY   — from Associates dashboard → Product Advertising API
  AMAZON_SECRET_KEY   — same place
  AMAZON_PARTNER_TAG  — your Associates tag (already set: 21112112-20)

How to get PA-API credentials in 3 minutes:
  1. Go to  https://associates.amazon.com
  2. Top menu → Tools → Product Advertising API
  3. Click "Manage your credentials" → "Add credentials"
  4. Copy Access Key ID  → AMAZON_ACCESS_KEY
  5. Copy Secret Key     → AMAZON_SECRET_KEY
  Note: PA-API requires at least 3 qualifying sales in the past 180 days
        OR you can request access with an established site.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
import datetime

HOST     = "webservices.amazon.com"
REGION   = "us-east-1"
SERVICE  = "ProductAdvertisingAPI"
PATH     = "/paapi5/searchitems"
ENDPOINT = f"https://{HOST}{PATH}"
TARGET   = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"

RESOURCES = [
    "Images.Primary.Large",
    "Images.Primary.Medium",
    "ItemInfo.Title",
    "ItemInfo.ByLineInfo",
    "Offers.Listings.Price",
]


# ── AWS Signature Version 4 ────────────────────────────────────────────────────

def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, datestamp: str) -> bytes:
    k = _sign(f"AWS4{secret}".encode("utf-8"), datestamp)
    k = _sign(k, REGION)
    k = _sign(k, SERVICE)
    return _sign(k, "aws4_request")


def _auth_headers(access_key: str, secret_key: str, payload: str) -> dict:
    now       = datetime.datetime.utcnow()
    amzdate   = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")

    headers = {
        "content-encoding": "amz-1.0",
        "content-type":     "application/json; charset=UTF-8",
        "host":             HOST,
        "x-amz-date":       amzdate,
        "x-amz-target":     TARGET,
    }
    sorted_hdrs    = sorted(headers.items())
    canonical_hdrs = "\n".join(f"{k}:{v}" for k, v in sorted_hdrs) + "\n"
    signed_hdrs    = ";".join(k for k, _ in sorted_hdrs)
    payload_hash   = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    canonical = "\n".join([
        "POST", PATH, "",
        canonical_hdrs, signed_hdrs, payload_hash,
    ])
    cred_scope     = f"{datestamp}/{REGION}/{SERVICE}/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256", amzdate, cred_scope,
        hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    ])
    sig = hmac.new(
        _signing_key(secret_key, datestamp),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return {
        **headers,
        "Authorization": (
            f"AWS4-HMAC-SHA256 Credential={access_key}/{cred_scope}, "
            f"SignedHeaders={signed_hdrs}, Signature={sig}"
        ),
    }


# ── Public API ─────────────────────────────────────────────────────────────────

def search_items(
    keywords: str,
    *,
    search_index: str = "Fashion",
    item_count: int = 10,
    min_price_cents: int | None = None,
    max_price_cents: int | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
    partner_tag: str | None = None,
) -> list[dict]:
    """
    Search Amazon and return structured product dicts.

    Each dict:  {asin, name, brand, image_url, price, affiliate_url}
    Raises EnvironmentError if credentials are missing.
    Raises RuntimeError on API error (includes body for debugging).
    """
    ak  = access_key  or os.environ.get("AMAZON_ACCESS_KEY",  "")
    sk  = secret_key  or os.environ.get("AMAZON_SECRET_KEY",  "")
    tag = partner_tag or os.environ.get("AMAZON_PARTNER_TAG", "")
    if not ak or not sk or not tag:
        raise EnvironmentError(
            "AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_PARTNER_TAG must be set. "
            "See prototype/amazon_pa_api.py for instructions."
        )

    body: dict = {
        "Keywords":    keywords,
        "SearchIndex": search_index,
        "ItemCount":   min(item_count, 10),
        "PartnerTag":  tag,
        "PartnerType": "Associates",
        "Marketplace": "www.amazon.com",
        "Resources":   RESOURCES,
    }
    if min_price_cents is not None:
        body["MinPrice"] = min_price_cents
    if max_price_cents is not None:
        body["MaxPrice"] = max_price_cents

    payload = json.dumps(body)
    hdrs    = _auth_headers(ak, sk, payload)
    req     = urllib.request.Request(
        ENDPOINT, data=payload.encode("utf-8"), headers=hdrs, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"PA-API HTTP {e.code}: {body_err[:500]}") from e

    items   = data.get("SearchResult", {}).get("Items", [])
    results = []
    for item in items:
        asin = item.get("ASIN", "")
        if not asin:
            continue
        title = (item.get("ItemInfo", {})
                     .get("Title", {})
                     .get("DisplayValue", "")) or ""
        brand = (item.get("ItemInfo", {})
                     .get("ByLineInfo", {})
                     .get("Brand", {})
                     .get("DisplayValue", "")) or ""
        img = (item.get("Images", {}).get("Primary", {}).get("Large",  {}).get("URL") or
               item.get("Images", {}).get("Primary", {}).get("Medium", {}).get("URL") or "")
        listings  = item.get("Offers", {}).get("Listings", [])
        price_amt = (listings[0].get("Price", {}).get("Amount", 0) if listings else 0)
        price     = round(float(price_amt), 2) if price_amt else 0.0
        affiliate_url = (
            f"https://www.amazon.com/dp/{asin}"
            f"?tag={tag}&linkCode=ll1&language=en_US"
        )
        results.append({
            "asin":          asin,
            "name":          title[:140],
            "brand":         brand,
            "image_url":     img,
            "price":         price,
            "affiliate_url": affiliate_url,
        })
    return results
