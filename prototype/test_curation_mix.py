"""Unit tests for 2-on-brief + 1 curiosity mix and shopping-buddy complements."""
from __future__ import annotations

from curation_mix import (
    build_curation_mix,
    complements_for,
    correct_shop_typos,
    detect_brand,
    detect_category,
    detect_color_key,
    detect_pattern,
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


def test_typo_topas_means_tops():
    assert detect_category("show me some topas") == "tops"
    assert detect_category("show me some shos") == "shoes"
    assert detect_category("show me some drsses") == "dresses"
    assert detect_category("fill what's missing") is None


def test_ranking_phrases_are_not_product_words():
    assert detect_category("best selling shoes") == "shoes"
    assert detect_category("top rated shoes") == "shoes"
    fixed, subs = correct_shop_typos("best selling shoes")
    assert "belt" not in fixed.lower()
    assert not any(dst == "belt" for _, dst in subs)


def test_chat_typos_colors_patterns_and_brands():
    """Typed chat should survive the usual fat-finger spellings."""
    assert detect_color_key("show me purpel tops") == "purple"
    assert detect_color_key("blak dress") == "black"
    assert detect_color_key("whyte shirt") == "white"
    assert detect_pattern("florl kurti") == "floral"
    cat = [
        {**_p("t1", "tops", "red"), "brand": "Zara"},
        {**_p("td1", "dresses", "navy"), "brand": "Tommy Hilfiger"},
        {**_p("s1", "shoes", "black"), "brand": "Aldo"},
    ]
    assert detect_brand("from zra", cat) == "Zara"
    assert detect_brand("tomy dresses", cat) == "Tommy Hilfiger"
    corrected, subs = correct_shop_typos(
        "show me purpel topas from zra", extra_words=("zara", "tommy")
    )
    assert "purple" in corrected.lower()
    assert "tops" in corrected.lower()
    assert "zara" in corrected.lower()
    assert {src for src, _ in subs} >= {"purpel", "topas", "zra"}
    # Everyday English must not snap onto catalog/brand tokens.
    still, still_subs = correct_shop_typos("let me see some tops", extra_words=("lee",))
    assert "let" in still.lower()
    assert not any(src == "let" for src, _ in still_subs)
    missing, missing_subs = correct_shop_typos("fill what's missing")
    assert detect_category(missing) is None
    assert not any(dst == "tee" for _, dst in missing_subs)


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


def test_homepage_trending_rails_fills_without_images():
    from curation_mix import homepage_trending_rails
    cat = _catalog()  # no image_url on these rows
    feed = homepage_trending_rails(cat, n_each=2)
    assert feed["rails"]["clothes"]
    assert feed["rails"]["shoes"]
    assert feed["rails"]["bags"]  # Structured Tote from accessories via bag hint


def test_homepage_trending_rails_split_clothes_shoes_bags():
    from curation_mix import homepage_trending_rails
    cat = _catalog() + [
        _p("d-hot", "dresses", "yellow", 2200, style=["trendy", "linen"],
           image_url="https://m.media-amazon.com/d.jpg", rating=4.6, ratings_total=400),
        _p("d-cold", "dresses", "grey", 1800,
           image_url="https://images.pexels.com/photos/1.jpeg"),
        _p("sh-hot", "shoes", "black", 2800, style=["platform", "trendy"],
           image_url="https://m.media-amazon.com/s.jpg", rating=4.5, ratings_total=200),
        _p("bg-hot", "bags", "tan", 1900, name="Mini Shoulder Bag Chain Strap",
           style=["trendy"], image_url="https://m.media-amazon.com/b.jpg",
           rating=4.7, ratings_total=900),
    ]
    feed = homepage_trending_rails(cat, n_each=3)
    assert set(feed["rails"]) == {"clothes", "shoes", "bags"}
    assert feed["rails"]["clothes"][0]["id"] == "d-hot"
    assert feed["rails"]["shoes"][0]["id"] == "sh-hot"
    assert feed["rails"]["bags"][0]["id"] == "bg-hot"
    assert feed["rails"]["clothes"][0].get("badge") == "trending"
    ids = {p["id"] for p in feed["items"]}
    assert {"d-hot", "sh-hot", "bg-hot"} <= ids


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


def test_companion_top_for_keeps_hero_top():
    from curation_mix import companion_top_for
    hero = _p("hero-top", "tops", "white", 1200)
    pinned = companion_top_for(hero, _catalog())
    assert pinned["id"] == "hero-top"
    assert pinned.get("mix_role") == "pinned_top"


def test_companion_top_for_shoe_picks_a_top():
    from curation_mix import companion_top_for
    hero = _p("hero-shoe", "shoes", "black", 3000)
    pinned = companion_top_for(hero, _catalog())
    assert pinned is not None
    assert pinned["category"] == "tops"
    assert pinned["id"] != "hero-shoe"


def test_shop_look_for_top_offers_several_bottoms():
    from curation_mix import shop_look_for
    cat = _catalog() + [
        _p("b-jean", "bottoms", "blue", 1800, name="Blue Skinny Jeans",
           image_url="https://m.media-amazon.com/jean.jpg"),
        _p("b-skirt", "bottoms", "black", 1600, name="Black Midi Skirt",
           image_url="https://m.media-amazon.com/skirt.jpg"),
        _p("b-trouser", "bottoms", "beige", 2200, name="Beige Wide Trousers",
           image_url="https://m.media-amazon.com/trouser.jpg"),
        _p("bag-hot", "bags", "tan", 2200, rating=4.7, ratings_total=1200,
           image_url="https://m.media-amazon.com/bag.jpg"),
        _p("shoe-hot", "shoes", "nude", 2800, rating=4.5, ratings_total=640,
           image_url="https://m.media-amazon.com/shoe.jpg"),
    ]
    hero = _p("hero-top", "tops", "white", 1200)
    look = shop_look_for(hero, cat, bottoms_n=4, trending_n_each=2)
    assert look["pinned"]["id"] == "hero-top"
    assert len(look["bottoms"]) >= 3
    assert all(p["category"] == "bottoms" for p in look["bottoms"])
    assert {p["category"] for p in look["accents"]} <= {"bags", "shoes"}
    assert all(p["id"] != "hero-top" for p in look["bottoms"])
    assert all(76 <= p.get("match_score", 0) <= 96 for p in look["bottoms"])


def test_look_match_pct_rewards_contrast_and_reviews():
    from curation_mix import look_match_pct
    hero = _p("hero-top", "tops", "white", 1200, style=["casual"])
    pair = _p("b-jean", "bottoms", "navy", 1800, style=["casual"],
              rating=4.6, ratings_total=400,
              image_url="https://m.media-amazon.com/jean.jpg")
    clash = _p("b-x", "bottoms", "white", 8000, gender="men",
               image_url="https://images.pexels.com/x.jpg")
    assert look_match_pct(hero, pair) > look_match_pct(hero, clash)
    assert 76 <= look_match_pct(hero, pair) <= 96


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
