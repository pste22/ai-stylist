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
    assert detect_color_key("today I want purple tops") == "purple"


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
