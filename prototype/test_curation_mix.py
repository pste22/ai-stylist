"""Unit tests for 2-on-brief + 1 curiosity mix and shopping-buddy complements."""
from __future__ import annotations

from curation_mix import (
    build_curation_mix,
    complements_for,
    detect_category,
    detect_color_key,
    majority_color_ok,
    render_mix_prompt,
)


def _p(pid, category, color, price=1000, **extra):
    return {
        "id": pid,
        "name": f"{color.title()} {category.title()} {pid}",
        "category": category,
        "color": color,
        "price": price,
        "style": ["casual"],
        "affiliate_url": f"https://ex/{pid}",
        "image_url": f"https://img/{pid}.jpg",
        **extra,
    }


def _catalog():
    return [
        _p("p1", "tops", "purple", 900),
        _p("p2", "tops", "lavender", 1200),
        _p("p3", "tops", "purple", 1500),
        _p("p4", "tops", "red", 2800),
        _p("p5", "tops", "black", 1100),
        _p("b1", "bottoms", "black", 2000),
        _p("a1", "accessories", "gold", 800),
        _p("s1", "shoes", "black", 2500),
        _p("t1", "tops", "white", 1400),
        _p("bag1", "bags", "black", 1800),
    ]


def test_detect_purple_tops():
    assert detect_category("today I want purple tops") == "tops"
    assert detect_category("show me some tops") == "tops"
    assert detect_color_key("today I want purple tops") == "purple"


def test_whats_missing_is_not_accessories():
    """'hat' used to match inside \"what's\" and dump accessory cards."""
    assert detect_category("Complete the look — fill what's missing") is None
    assert detect_category("fill what's missing") is None
    assert detect_category("show me some tops") == "tops"
    assert detect_category("baseball cap") == "accessories"
    assert detect_category("show me some hats") == "accessories"


def test_photo_quality_amazon_beats_pexels():
    from curation_mix import photo_quality
    amazon = _p("amz", "tops", "white", 1000,
                image_url="https://m.media-amazon.com/images/I/xx.jpg")
    pexels = _p("px", "tops", "white", 5000,
                image_url="https://images.pexels.com/photos/xx.jpg")
    other = _p("cdn", "tops", "white", 2000,
               image_url="https://cdn.shopify.com/xx.jpg")
    assert photo_quality(amazon) > photo_quality(other) > photo_quality(pexels)


def test_mix_prefers_real_photos_over_pexels():
    cat = _catalog() + [
        {**_p("px", "tops", "purple", 9000),
         "image_url": "https://images.pexels.com/photos/standin.jpg"},
        {**_p("amz", "tops", "purple", 1400),
         "image_url": "https://m.media-amazon.com/images/I/real.jpg"},
    ]
    mix = build_curation_mix(cat, "purple tops", n=3, category="tops")
    assert mix
    assert mix[0]["id"] != "px"
    assert any(p["id"] == "amz" for p in mix)


def test_mix_majority_on_brief_with_curiosity():
    mix = build_curation_mix(_catalog(), "purple tops", n=3, category="tops")
    assert 1 <= len(mix) <= 3
    roles = [p.get("mix_role") for p in mix]
    assert roles.count("curiosity") <= 1
    assert majority_color_ok(mix, "purple", min_share=0.5) or any(
        r == "curiosity" for r in roles
    )
    # At least one on-brief purple-ish
    assert any(p.get("mix_role") == "on_brief" for p in mix)


def test_curiosity_prefers_accent_or_premium():
    mix = build_curation_mix(_catalog(), "show me purple tops", n=3)
    curiosity = [p for p in mix if p.get("mix_role") == "curiosity"]
    if curiosity:
        c = curiosity[0]
        blob = f"{c.get('color')} {c.get('name')}".lower()
        assert "red" in blob or "black" in blob or c["price"] >= 1500


def test_complements_for_pants():
    hero = _p("hero", "bottoms", "navy", 2200)
    comps = complements_for(hero, _catalog(), n=3)
    cats = {p["category"] for p in comps}
    assert "bottoms" not in cats
    assert cats & {"tops", "accessories", "shoes", "bags", "outerwear"}
    assert all(p.get("mix_role") == "complement" for p in comps)


def test_look_slots_for_top_picks_bottoms_shoes_bag():
    from curation_mix import look_slots_for
    hero = _p("hero-top", "tops", "white", 1200)
    slots = look_slots_for(hero, _catalog())
    cats = [p["category"] for p in slots]
    assert cats == ["bottoms", "shoes", "bags"]
    assert "hero-top" not in {p["id"] for p in slots}
    assert all(p.get("mix_role") == "look_slot" for p in slots)


def test_look_slots_for_dress_skips_bottoms():
    from curation_mix import look_slots_for
    hero = _p("hero-dress", "dresses", "red", 3000)
    cats = {p["category"] for p in look_slots_for(hero, _catalog())}
    assert "bottoms" not in cats
    assert "shoes" in cats
    assert "bags" in cats


def test_bottoms_variety_offers_several_styles():
    from curation_mix import bottom_style, bottoms_variety_for
    cat = _catalog() + [
        _p("b-jean", "bottoms", "blue", 1800, name="Blue Skinny Jeans",
           image_url="https://m.media-amazon.com/jean.jpg"),
        _p("b-skirt", "bottoms", "black", 1600, name="Black Midi Skirt",
           image_url="https://m.media-amazon.com/skirt.jpg"),
        _p("b-trouser", "bottoms", "beige", 2200, name="Beige Wide Trousers",
           image_url="https://m.media-amazon.com/trouser.jpg"),
        _p("b-short", "bottoms", "white", 900, name="White Linen Shorts",
           image_url="https://m.media-amazon.com/short.jpg"),
        _p("b-palazzo", "bottoms", "navy", 1900, name="Navy Palazzo Pants",
           image_url="https://m.media-amazon.com/palazzo.jpg"),
    ]
    hero = _p("hero-top", "tops", "white", 1200)
    picks = bottoms_variety_for(hero, cat, n=5)
    assert len(picks) >= 4
    assert all(p["category"] == "bottoms" for p in picks)
    assert all(p.get("mix_role") == "bottoms_option" for p in picks)
    assert "hero-top" not in {p["id"] for p in picks}
    styles = {bottom_style(p) for p in picks}
    assert len(styles) >= 3


def test_bottoms_variety_skips_mens_when_womens_exist():
    from curation_mix import bottoms_variety_for
    cat = [
        _p("mb1", "bottoms", "black", 1500, gender="men", name="Men Slim Jeans",
           image_url="https://m.media-amazon.com/m.jpg"),
        _p("wb1", "bottoms", "navy", 1600, gender="women", name="Women Navy Trousers",
           image_url="https://m.media-amazon.com/w1.jpg"),
        _p("wb2", "bottoms", "beige", 1700, gender="women", name="Women Beige Skirt",
           image_url="https://m.media-amazon.com/w2.jpg"),
        _p("wb3", "bottoms", "white", 1800, gender="unisex", name="Unisex White Shorts",
           image_url="https://m.media-amazon.com/w3.jpg"),
    ]
    hero = _p("hero-top", "tops", "white", 1200, gender="women")
    ids = {p["id"] for p in bottoms_variety_for(hero, cat, n=6)}
    assert "mb1" not in ids
    assert ids & {"wb1", "wb2", "wb3"}


def test_trending_badges_need_real_reviews():
    from curation_mix import trending_complements
    cat = [
        _p("bag-hot", "bags", "black", 2000, rating=4.6, ratings_total=800,
           image_url="https://m.media-amazon.com/baghot.jpg"),
        _p("bag-cold", "bags", "brown", 1500,
           image_url="https://m.media-amazon.com/bagcold.jpg"),
        _p("shoe-hot", "shoes", "black", 2500, rating=4.4, ratings_total=300,
           image_url="https://m.media-amazon.com/shoehot.jpg"),
        _p("shoe-cold", "shoes", "nude", 1800,
           image_url="https://m.media-amazon.com/shoecold.jpg"),
    ]
    items = trending_complements(cat, n_each=2)
    by_id = {p["id"]: p for p in items}
    assert by_id["bag-hot"].get("badge") == "trending"
    assert by_id["shoe-hot"].get("badge") == "trending"
    assert by_id["bag-cold"].get("badge") != "trending"
    assert {p["category"] for p in items} == {"bags", "shoes"}


def test_style_suggestions_for_top_has_bottoms_and_trending():
    from curation_mix import style_suggestions_for
    cat = _catalog() + [
        _p("b-jean", "bottoms", "blue", 1800, name="Blue Skinny Jeans",
           image_url="https://m.media-amazon.com/jean.jpg"),
        _p("b-skirt", "bottoms", "black", 1600, name="Black Midi Skirt",
           image_url="https://m.media-amazon.com/skirt.jpg"),
        _p("bag-hot", "bags", "tan", 2200, rating=4.7, ratings_total=1200,
           image_url="https://m.media-amazon.com/bag.jpg"),
        _p("shoe-hot", "shoes", "nude", 2800, rating=4.5, ratings_total=640,
           image_url="https://m.media-amazon.com/shoe.jpg"),
    ]
    hero = _p("hero-top", "tops", "white", 1200)
    items = style_suggestions_for(hero, cat, bottoms_n=4, trending_n_each=2)
    roles = {p.get("mix_role") for p in items}
    cats = {p["category"] for p in items}
    assert "bottoms_option" in roles
    assert "trending" in roles
    assert "bottoms" in cats
    assert "bags" in cats
    assert "shoes" in cats
    assert all(p["id"] != "hero-top" for p in items)


def test_card_fields_pass_trending_badge():
    from curation_mix import card_fields
    p = _p("bag-hot", "bags", "black", 2000, rating=4.6, ratings_total=800,
           mix_role="trending", badge="trending")
    card = card_fields(p)
    assert card["badge"] == "trending"
    assert card["rating"] == 4.6
    assert card["ratings_total"] == 800
    assert card["mix_role"] == "trending"


def test_render_tags_curiosity():
    mix = build_curation_mix(_catalog(), "purple tops", n=3)
    text = render_mix_prompt(mix)
    if any(p.get("mix_role") == "curiosity" for p in mix):
        assert "CURIOSITY" in text


def test_no_invent_outside_catalog():
    tiny = [_p("only", "tops", "purple", 1000)]
    mix = build_curation_mix(tiny, "purple tops", n=3)
    assert all(p["id"] == "only" for p in mix)
    assert sum(1 for p in mix if p.get("mix_role") == "curiosity") <= 1


def test_resolve_tommy_red_dresses_falls_back_to_brand_cat():
    from curation_mix import resolve_shop_query
    cat = [
        {**_p("td1", "dresses", "multi", 4000), "brand": "Tommy Hilfiger", "name": "Tommy Hilfiger Polo Dress"},
        {**_p("td2", "dresses", "navy", 4500), "brand": "Tommy Hilfiger", "name": "Tommy Hilfiger Navy Dress"},
        {**_p("rd1", "dresses", "red", 2000), "brand": "BIBA", "name": "BIBA Red Dress"},
    ]
    hit = resolve_shop_query(cat, "show me some red dresses from tommy", n=4)
    assert hit["brand"] == "Tommy Hilfiger"
    assert hit["category"] == "dresses"
    assert hit["color"] == "red"
    assert hit["mode"] == "brand_cat"  # no red Tommy — relax color
    assert all(p["brand"] == "Tommy Hilfiger" for p in hit["products"])
    assert hit["notes"]
