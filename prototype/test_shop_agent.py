"""Unit tests for the deterministic typed-search agent + recommender."""
from __future__ import annotations

import shop_agent
from shop_agent import answer, parse_query, popularity_score
from recommender import build_affinity, recommend


def _p(pid, category, color, price=1000, brand=None, rating=None, votes=None, **extra):
    return {
        "id": pid,
        "name": f"{(brand + ' ') if brand else ''}{color.title()} {category.title()} {pid}",
        "category": category,
        "color": color,
        "price": price,
        "brand": brand,
        "rating": rating,
        "ratings_total": votes,
        "style": ["casual"],
        "affiliate_url": f"https://ex/{pid}",
        "image_url": f"https://img/{pid}.jpg",
        **extra,
    }


def _catalog():
    return [
        _p("td1", "dresses", "multi", 4000, brand="Tommy Hilfiger", rating=4.4, votes=900),
        _p("td2", "dresses", "navy", 4500, brand="Tommy Hilfiger", rating=4.0, votes=50),
        _p("td3", "dresses", "white", 3500, brand="Tommy Hilfiger", rating=4.8, votes=5),
        _p("rd1", "dresses", "red", 2000, brand="BIBA", rating=4.2, votes=3000),
        _p("rd2", "dresses", "maroon", 2400, brand="BIBA", rating=3.9, votes=120),
        _p("t1", "tops", "red", 900, brand="Zara", rating=4.1, votes=400),
        _p("s1", "shoes", "black", 2500, brand="Aldo", rating=4.5, votes=1500),
        _p("b1", "bags", "gold", 5000, brand="Aldo", rating=4.3, votes=800),
    ]


# ── parsing ──────────────────────────────────────────────────────────────────

def test_parse_count_price_sort():
    q = parse_query("show me 5 best selling red dresses under 3,000")
    assert q["count"] == 5
    assert q["price_max"] == 3000
    assert q["sort"] == "popular"

    q = parse_query("a few cheapest tops between 1k and 2k")
    assert q["count"] == 3
    assert q["price_min"] == 1000 and q["price_max"] == 2000
    assert q["sort"] == "price_asc"

    q = parse_query("dresses under 2k")  # the 2 in "2k" must not become a count
    assert q["count"] is None
    assert q["price_max"] == 2000


def test_parse_recommend_intent():
    assert parse_query("recommend something for me")["recommend"] is True
    assert parse_query("surprise me with picks")["recommend"] is True
    assert parse_query("show me red dresses")["recommend"] is False


# ── search ───────────────────────────────────────────────────────────────────

def test_tommy_red_dresses_relaxes_color_with_note():
    hit = answer(_catalog(), "show me 5 red dresses of tommy")
    assert hit["brand"] == "Tommy Hilfiger"
    assert hit["mode"] == "brand_cat"  # no red Tommy → color relaxed
    assert hit["products"]
    assert all(p["brand"] == "Tommy Hilfiger" for p in hit["products"])
    assert hit["notes"]
    assert hit["label"] and "Tommy" in hit["label"]


def test_count_honored_and_popularity_ranked():
    hit = answer(_catalog(), "show me 2 dresses")
    assert len(hit["products"]) == 2
    # rd1 (4.2★ × 3000 votes) is the best-selling dress → must lead
    assert hit["products"][0]["id"] == "rd1"


def test_price_filter_applies():
    hit = answer(_catalog(), "dresses under 2500")
    assert hit["products"]
    assert all(p["price"] <= 2500 for p in hit["products"])


def test_price_relaxed_when_budget_impossible():
    hit = answer(_catalog(), "tommy dresses under 100")
    assert hit["products"]  # closest matches shown, not an empty pane
    assert any("closest" in n.lower() or "₹" in n for n in hit["notes"])


def test_sorry_message_when_pool_exhausted():
    cat = _catalog()
    all_dress_ids = {p["id"] for p in cat if p["category"] == "dresses"}
    hit = answer(cat, "show me more dresses", exclude_ids=all_dress_ids)
    assert not hit["products"]
    assert hit["message"] and "sorry" in hit["message"].lower()


def test_unknown_brand_honesty_note():
    hit = answer(_catalog(), "show me purple gowns from gucci")
    # Gucci isn't carried → close alternatives WITH an honest note
    assert hit["products"]
    assert any("gucci" in n.lower() for n in hit["notes"])


def test_unknown_brand_sorry():
    hit = answer(_catalog(), "show me gucci belts")
    # No gucci, no belts ("belt" maps to accessories which is empty here)
    assert not hit["products"]
    assert hit["message"]


def test_name_term_fallback_finds_miscategorised_kurtas():
    cat = _catalog() + [
        # Kurtas categorised as "dresses" — taxonomy miss, common in feed imports
        _p("k1", "dresses", "purple", 3000, brand="W",
           name="W for Woman Purple Embroidered Kurta"),
        _p("k2", "dresses", "green", 2100, brand="W",
           name="W for Woman Green Printed Kurta"),
    ]
    hit = answer(cat, "show me 10 kurtas")
    ids = {p["id"] for p in hit["products"]}
    assert {"k1", "k2"} <= ids
    assert hit["mode"] == "name_match"
    assert "Kurta" in (hit["label"] or "")


def test_label_never_claims_relaxed_facets():
    # No red Tommy dresses exist → label must not say "Red"
    hit = answer(_catalog(), "show me 5 red dresses of tommy")
    assert "Red" not in (hit["label"] or "")
    assert "Tommy" in (hit["label"] or "")


def test_show_me_some_tops_is_tops_category():
    """The first typed ask 'show me some tops' must resolve to tops, not bags/dresses."""
    hit = answer(_catalog(), "show me some tops")
    assert hit["category"] == "tops"
    assert hit["mode"] in ("category", "cat_color")
    assert hit["products"]
    assert all(p["category"] == "tops" for p in hit["products"])
    assert hit["label"] and "Top" in hit["label"]


def test_chitchat_is_not_a_shop_ask():
    hit = answer(_catalog(), "hello how are you today")
    assert hit["mode"] == "none"
    assert not hit["products"] and not hit["message"]


def test_cache_hit_on_repeat():
    cat = _catalog()
    shop_agent._query_cache.clear()
    first = answer(cat, "red dresses")
    again = answer(cat, "red dresses")
    assert [p["id"] for p in first["products"]] == [p["id"] for p in again["products"]]
    assert again.get("cached") is True


def test_popularity_score_prefers_volume():
    hot = _p("hot", "tops", "red", rating=4.3, votes=8000)
    niche = _p("niche", "tops", "red", rating=5.0, votes=2)
    assert popularity_score(hot) > popularity_score(niche)


# ── recommender ──────────────────────────────────────────────────────────────

def test_recommend_reflects_history():
    cat = _catalog()
    by_id = {p["id"]: p for p in cat}
    events = [
        {"product_id": "rd1", "action": "would_buy", "ts": None},
        {"product_id": "rd2", "action": "buy_click", "ts": None},
        {"product_id": "t1", "action": "shown", "ts": None},
    ]
    aff = build_affinity(events, by_id)
    assert aff["categories"].most_common(1)[0][0] == "dresses"
    assert "rd2" in aff["purchased"]

    recs = recommend(cat, events, by_id=by_id, n=4)
    ids = [p["id"] for p in recs]
    assert "rd2" not in ids  # already purchased
    # Dresses (their favourite category) should lead
    assert recs[0]["category"] == "dresses"
    assert all(p.get("mix_role") == "recommended" for p in recs)


def test_recommend_cold_start_popularity():
    cat = _catalog()
    by_id = {p["id"]: p for p in cat}
    recs = recommend(cat, [], by_id=by_id, n=3)
    assert len(recs) == 3
    # Diverse: no more than 3 of the same category enforced by cap
    assert recs  # popularity-ranked, never empty on a non-empty catalog


def test_complete_look_chip_is_not_an_accessories_dump():
    hit = answer(_catalog(), "Complete the look — fill what's missing")
    assert hit["category"] is None
    assert hit["mode"] == "none"


def test_amazon_photo_ranks_above_pexels_when_popularity_ties():
    shop_agent._query_cache.clear()
    cat = [
        _p("px", "tops", "white", 4000, rating=4.5, votes=100,
           image_url="https://images.pexels.com/photos/boot.jpg"),
        _p("amz", "tops", "white", 4000, rating=4.5, votes=100,
           image_url="https://m.media-amazon.com/images/I/shirt.jpg"),
    ]
    hit = answer(cat, "show me some tops")
    assert hit["products"]
    assert hit["products"][0]["id"] == "amz"
    assert "px" not in {p["id"] for p in hit["products"]}


if __name__ == "__main__":
    import sys
    mod = sys.modules[__name__]
    fails = 0
    for name in dir(mod):
        if name.startswith("test_"):
            try:
                getattr(mod, name)()
                print(f"  ok  {name}")
            except AssertionError as e:
                fails += 1
                print(f"FAIL  {name}: {e}")
    print("PASS" if not fails else f"{fails} FAILURES")
    sys.exit(1 if fails else 0)
