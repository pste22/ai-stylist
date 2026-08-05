"""Personal recommendation engine driven by the shopper's own history.

Scores every catalog product against an affinity profile built from what the
user has purchased (buy_click), loved (would_buy / wishlist), tried on, and
viewed (shown) — weighted by action strength and recency — so "recommend
something for me" always reflects their actual taste, not a generic feed.

    affinity = brand + category + color counters, plus a target price band
    score(p) = category-affinity + brand-affinity + color-affinity
               + price-band fit + popularity prior

Purchased items are excluded (they already own them); a per-category cap
keeps the strip varied instead of six near-identical dresses.
Pure in-memory: safe to call on the hot chat path.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from shop_agent import popularity_score

# How strongly each interaction signals taste.
ACTION_WEIGHTS: dict[str, float] = {
    "buy_click": 5.0,   # purchased — strongest signal
    "would_buy": 3.0,   # loved / hearted
    "wishlist": 3.0,
    "try_on": 2.5,      # tried on virtually
    "shown": 0.4,       # merely watched
}

_RECENCY_HALF_LIFE_DAYS = 30.0
_MAX_PER_CATEGORY = 3


def _recency(ts: str | None) -> float:
    """1.0 for today, halving every ~30 days; unknown timestamps count fully."""
    if not ts:
        return 1.0
    try:
        then = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        days = max((datetime.now(timezone.utc) - then).days, 0)
    except (ValueError, TypeError):
        return 1.0
    return 0.5 ** (days / _RECENCY_HALF_LIFE_DAYS)


def build_affinity(events: list[dict], by_id: dict[str, dict]) -> dict:
    """Aggregate weighted brand/category/color counters + price target."""
    brands: Counter = Counter()
    cats: Counter = Counter()
    colors: Counter = Counter()
    price_sum = 0.0
    price_w = 0.0
    purchased: set[str] = set()

    for e in events or []:
        pid = e.get("product_id")
        p = by_id.get(pid) if pid else None
        if p is None:
            continue
        w = ACTION_WEIGHTS.get(e.get("action") or "", 0.0) * _recency(e.get("ts"))
        if w <= 0:
            continue
        if e.get("action") == "buy_click":
            purchased.add(pid)
        if p.get("brand"):
            brands[p["brand"].lower()] += w
        if p.get("category"):
            cats[p["category"].lower()] += w
        if p.get("color"):
            colors[p["color"].lower()] += w
        try:
            price = float(p.get("price") or 0.0)
        except (TypeError, ValueError):
            price = 0.0
        if price > 0:
            price_sum += price * w
            price_w += w

    return {
        "brands": brands,
        "categories": cats,
        "colors": colors,
        "target_price": (price_sum / price_w) if price_w else None,
        "purchased": purchased,
    }


def _norm(counter: Counter, key: str | None) -> float:
    if not key or not counter:
        return 0.0
    top = counter.most_common(1)[0][1]
    return (counter.get(key.lower(), 0.0) / top) if top else 0.0


def _price_fit(price: float, target: float | None) -> float:
    """1.0 at the user's typical spend, fading to 0 at 3x away."""
    if not target or price <= 0:
        return 0.0
    ratio = price / target if price > target else target / price
    return max(0.0, 1.0 - (ratio - 1.0) / 2.0)


def recommend(
    catalog: list[dict],
    events: list[dict],
    *,
    by_id: dict[str, dict],
    n: int = 6,
    exclude_ids: set[str] | None = None,
) -> list[dict]:
    """Top-n personalized picks; popularity-ranked diverse picks when no history."""
    exclude = set(exclude_ids or set())
    aff = build_affinity(events, by_id)
    exclude |= aff["purchased"]

    max_pop = max((popularity_score(p) for p in catalog), default=1.0) or 1.0
    has_history = bool(aff["brands"] or aff["categories"] or aff["colors"])

    scored: list[tuple[float, dict]] = []
    for p in catalog:
        if not p.get("id") or p["id"] in exclude:
            continue
        pop = popularity_score(p) / max_pop
        if has_history:
            try:
                price = float(p.get("price") or 0.0)
            except (TypeError, ValueError):
                price = 0.0
            score = (
                3.0 * _norm(aff["categories"], p.get("category"))
                + 2.5 * _norm(aff["brands"], p.get("brand"))
                + 1.5 * _norm(aff["colors"], p.get("color"))
                + 1.2 * _price_fit(price, aff["target_price"])
                + 0.8 * pop
            )
        else:
            score = pop
        scored.append((score, p))

    scored.sort(key=lambda t: -t[0])

    picks: list[dict] = []
    per_cat: Counter = Counter()
    for score, p in scored:
        cat = (p.get("category") or "other").lower()
        if per_cat[cat] >= _MAX_PER_CATEGORY:
            continue
        per_cat[cat] += 1
        picks.append({**p, "mix_role": "recommended"})
        if len(picks) >= n:
            break
    # Backfill if diversity cap left gaps
    if len(picks) < n:
        chosen = {p["id"] for p in picks}
        for score, p in scored:
            if p["id"] in chosen:
                continue
            picks.append({**p, "mix_role": "recommended"})
            if len(picks) >= n:
                break
    return picks
