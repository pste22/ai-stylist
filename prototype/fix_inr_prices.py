"""Convert USD-valued prices to realistic INR prices.

Current state: all products stored with USD values ($6–$140) tagged as INR.
Fix: multiply by USD→INR rate and snap to Indian price points (e.g. ₹999, ₹1,499).

Run:
  python fix_inr_prices.py --dry-run   # preview, no writes
  python fix_inr_prices.py             # apply to all active products
"""
from __future__ import annotations
import argparse, logging, os, time

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

USD_TO_INR = 84.0   # approximate rate July 2026; update when PA API available

# Indian e-commerce price snapping breakpoints
# Each entry: (max_inr, snap_to) — snap to nearest multiple of snap_to below that ceiling
SNAP_RULES = [
    (300,    49),
    (700,    99),
    (1500,  199),
    (3000,  299),
    (6000,  499),
    (12000, 999),
    (25000, 999),
    (99999, 999),
]

def snap_to_indian_price(inr: float) -> int:
    """Round to the nearest Indian e-commerce price point ending in 99 or 49/99."""
    for ceiling, step in SNAP_RULES:
        if inr <= ceiling:
            snapped = round(inr / step) * step
            # Ensure it ends in 99 for cleaner feel
            snapped = (snapped // step) * step + (step - 1)
            return max(snapped, step - 1)
    return int(round(inr / 999) * 999 + 998)


def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main():
    load_env()
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from supabase import create_client
    db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

    # Fetch all active products
    log.info("Fetching active products...")
    result = db.table("products").select("id,name,price,currency").eq("is_active", True).execute()
    products = result.data or []
    log.info("Found %d active products", len(products))

    updates = []
    for p in products:
        old_price = float(p["price"] or 0)
        if old_price <= 0:
            continue
        inr_raw = old_price * USD_TO_INR
        inr_snapped = snap_to_indian_price(inr_raw)
        updates.append({"id": p["id"], "old": old_price, "new": inr_snapped, "name": p["name"]})

    if not updates:
        log.info("Nothing to update.")
        return

    # Preview sample
    log.info("\nSample conversions:")
    for u in updates[:12]:
        log.info("  $%-6.2f → ₹%-7d  %s", u["old"], u["new"], u["name"][:55])

    import statistics
    new_prices = [u["new"] for u in updates]
    log.info(
        "\nSummary: %d products | ₹%d–₹%d | median ₹%d",
        len(updates), min(new_prices), max(new_prices), int(statistics.median(new_prices))
    )

    if args.dry_run:
        log.info("DRY RUN — no writes.")
        return

    # Group products by their new price to minimise API calls
    from collections import defaultdict
    by_price: dict[int, list[str]] = defaultdict(list)
    for u in updates:
        by_price[u["new"]].append(u["id"])

    log.info("\nApplying price updates (%d unique price points)...", len(by_price))
    done = 0
    ID_CHUNK = 200   # Supabase in_() limit
    for price, ids in by_price.items():
        for i in range(0, len(ids), ID_CHUNK):
            chunk = ids[i:i + ID_CHUNK]
            db.table("products").update({"price": price, "currency": "INR"}).in_("id", chunk).execute()
        done += len(ids)
        if done % 200 == 0 or done == len(updates):
            log.info("  Updated %d / %d", done, len(updates))
        time.sleep(0.05)

    log.info("Done. All %d products now have INR prices.", len(updates))


if __name__ == "__main__":
    main()
