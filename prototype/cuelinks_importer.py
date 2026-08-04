"""Cuelinks affiliate importer (Publisher API v3).

Cuelinks does NOT ship a product catalog feed. Flow is:
  1) Brand CSV → products in Supabase (brand_feed_importer.py) with raw merchant URLs
  2) This script converts those URLs → tracked Cuelinks links (clnk.in)

Setup:
  1. Apply as publisher: https://www.cuelinks.com/
  2. Create API key with scopes: read:campaigns, write:links
  3. Add to prototype/.env:
       CUELINKS_API_KEY=...
  4. python cuelinks_importer.py --list-campaigns
  5. python cuelinks_importer.py --convert-brand-links --limit 50

Docs: https://developers.cuelinks.com/docs
Base: https://developers.cuelinks.com/pub_api/v3
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

load_dotenv(Path(__file__).parent / ".env")

BASE = os.environ.get(
    "CUELINKS_API_BASE",
    "https://developers.cuelinks.com/pub_api/v3",
)


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _get(path: str, api_key: str, params: dict | None = None) -> dict | list:
    qs = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{BASE.rstrip('/')}/{path.lstrip('/')}{qs}"
    req = urllib.request.Request(url, headers=_headers(api_key))
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post(path: str, api_key: str, body: dict) -> dict:
    url = f"{BASE.rstrip('/')}/{path.lstrip('/')}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=_headers(api_key), method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_campaigns(api_key: str, *, q: str = "", country_id: int = 252, per_page: int = 50) -> list:
    """List campaigns (India = country_id 252)."""
    params: dict = {"per_page": per_page, "sort": "epc_7d", "order": "desc"}
    if q:
        params["q"] = q
    else:
        params["country_id"] = country_id
    try:
        data = _get("campaigns", api_key, params)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        log.error("Campaigns fetch failed (%s): %s", exc.code, body[:300])
        raise
    if isinstance(data, dict):
        return data.get("data") or data.get("campaigns") or []
    return data


def convert_link(api_key: str, url: str, *, subid: str | None = None) -> str | None:
    """Convert a merchant URL into a tracked Cuelinks affiliate link."""
    body: dict = {"url": url}
    if subid:
        body["subid"] = subid
    try:
        data = _post("links/convert", api_key, body)
    except urllib.error.HTTPError as exc:
        body_err = exc.read().decode("utf-8", errors="replace")
        log.warning("  convert failed (%s): %s", exc.code, body_err[:200])
        return None
    # Response shapes vary slightly by tier
    if isinstance(data, dict):
        for key in ("short_url", "tracking_url", "affiliate_url", "url", "link"):
            if data.get(key):
                return data[key]
        nested = data.get("data") or {}
        if isinstance(nested, dict):
            for key in ("short_url", "tracking_url", "affiliate_url", "url", "link"):
                if nested.get(key):
                    return nested[key]
    return None


def convert_brand_links(*, api_key: str, limit: int, dry_run: bool, sleep_s: float) -> None:
    """Rewrite brand_* product affiliate_urls via Cuelinks convert."""
    from supabase import create_client

    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    # Pull brand-sourced rows that are not yet clnk.in / cuelinks tracked
    res = (
        sb.table("products")
        .select("id,affiliate_url,source,brand")
        .like("source", "brand_%")
        .eq("is_active", True)
        .limit(min(limit * 2, 2000))
        .execute()
    )
    rows = [
        r for r in (res.data or [])
        if r.get("affiliate_url")
        and "clnk.in" not in (r["affiliate_url"] or "")
        and "cuelinks.com" not in (r["affiliate_url"] or "")
    ][:limit]

    log.info("Converting %d brand URLs…", len(rows))
    ok = fail = 0
    for i, row in enumerate(rows, 1):
        raw = row["affiliate_url"]
        log.info("[%d/%d] %s", i, len(rows), row["id"])
        if dry_run:
            log.info("  DRY would convert %s", raw[:80])
            ok += 1
            continue
        tracked = convert_link(api_key, raw, subid=f"mira-{row['id'][:40]}")
        if not tracked:
            fail += 1
            time.sleep(sleep_s)
            continue
        sb.table("products").update({
            "affiliate_url": tracked,
            "partner_tag": "cuelinks",
        }).eq("id", row["id"]).execute()
        log.info("  ✓ %s", tracked[:80])
        ok += 1
        time.sleep(sleep_s)
    log.info("Done. converted=%d failed=%d", ok, fail)


def main() -> None:
    ap = argparse.ArgumentParser(description="Cuelinks v3 — campaigns + brand link convert")
    ap.add_argument("--list-campaigns", action="store_true")
    ap.add_argument("--q", default="", help="Campaign search query e.g. myntra")
    ap.add_argument("--convert-brand-links", action="store_true",
                    help="Wrap brand_* product URLs with Cuelinks tracking")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--sleep", type=float, default=0.8)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    api_key = os.environ.get("CUELINKS_API_KEY", "")
    if not api_key:
        log.error(
            "CUELINKS_API_KEY missing.\n"
            "  1) Apply at https://www.cuelinks.com/ (publisher)\n"
            "  2) Create API key with read:campaigns + write:links\n"
            "  3) Add CUELINKS_API_KEY=... to prototype/.env\n"
            "Meanwhile brand CSV is already importable via brand_feed_importer.py"
        )
        raise SystemExit(1)

    if args.list_campaigns:
        camps = fetch_campaigns(api_key, q=args.q)
        log.info("Found %d campaigns", len(camps))
        for c in camps[:30]:
            name = c.get("name")
            epc = c.get("epc_7d")
            status = c.get("access_status")
            log.info("  %-28s  epc7d=%-6s  access=%s", name, epc, status)
        return

    if args.convert_brand_links:
        convert_brand_links(
            api_key=api_key,
            limit=args.limit,
            dry_run=args.dry_run,
            sleep_s=args.sleep,
        )
        return

    log.info(
        "Nothing to do. Try:\n"
        "  python cuelinks_importer.py --list-campaigns --q myntra\n"
        "  python cuelinks_importer.py --convert-brand-links --limit 50"
    )


if __name__ == "__main__":
    main()
