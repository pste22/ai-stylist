from look_engine import build_look_around, build_looks


def _product(product_id, category, price, *, style=None):
    return {
        "id": product_id,
        "name": product_id.replace("-", " ").title(),
        "category": category,
        "price": price,
        "style": style or ["festival"],
        "affiliate_url": f"https://merchant.example/{product_id}",
        # build_looks skips anything unrenderable; without an image every product
        # was filtered out and the fixture silently asserted against zero looks.
        "image_url": f"https://img.example/{product_id}.jpg",
    }


def test_builds_three_complete_grounded_looks():
    catalog = [
        _product("dress-one", "dresses", 90),
        _product("shoes-one", "shoes", 80),
        _product("accessory-one", "accessories", 30),
        _product("top-one", "tops", 40),
        _product("bottom-one", "bottoms", 60),
        _product("shoes-two", "shoes", 70),
        _product("top-two", "tops", 45),
        _product("bottom-two", "bottoms", 65),
        _product("outerwear-one", "outerwear", 100),
        _product("accessory-two", "accessories", 35),
        # The third template ("Ethnic Glam") is anchored on the ethnic category, so
        # without one of these the engine can only ever return two looks.
        _product("ethnic-one", "ethnic", 85),
    ]

    looks = build_looks(catalog, occasion="Festival", vibe="festival", budget_max=120)

    assert len(looks) == 3
    assert all(look["items"] for look in looks)
    assert all(item["affiliate_url"] for look in looks for item in look["items"])
    assert all(look["total_price"] > 0 for look in looks)


def test_never_returns_products_without_affiliate_links():
    catalog = [
        _product("dress-one", "dresses", 90),
        _product("shoes-one", "shoes", 80),
        _product("accessory-one", "accessories", 30),
        _product("top-one", "tops", 40),
        _product("bottom-one", "bottoms", 60),
        _product("shoes-two", "shoes", 70),
        _product("top-two", "tops", 45),
        _product("bottom-two", "bottoms", 65),
        _product("outerwear-one", "outerwear", 100),
        _product("accessory-two", "accessories", 35),
    ]
    catalog[0]["affiliate_url"] = None

    looks = build_looks(catalog, occasion="Wedding")

    ids = {item["id"] for look in looks for item in look["items"]}
    assert "dress-one" not in ids


def _full_catalog():
    return [
        _product("dress-hero", "dresses", 90),
        _product("top-hero", "tops", 40),
        _product("bottom-one", "bottoms", 55),
        _product("shoes-one", "shoes", 70, style=["heels"]),
        _product("bag-one", "bags", 45, style=["clutch"]),
        _product("acc-one", "accessories", 25, style=["earrings"]),
    ]


def test_build_look_around_dress_is_head_to_toe():
    look = build_look_around(_full_catalog()[0], _full_catalog(), occasion="party")
    assert look is not None
    cats = {item["category"] for item in look["items"]}
    assert "dresses" in cats
    assert "shoes" in cats
    assert "bags" in cats
    assert look["slots"]["outfit"][0]["id"] == "dress-hero"
    assert look["total_price"] > 90
    assert look["name"] == "Night-out edit"


def test_build_look_around_top_adds_bottom():
    hero = _product("top-hero", "tops", 40)
    look = build_look_around(hero, _full_catalog(), occasion="office")
    assert look is not None
    outfit_ids = {p["id"] for p in look["slots"]["outfit"]}
    assert "top-hero" in outfit_ids
    assert "bottom-one" in outfit_ids


def test_build_look_around_needs_companions():
    lonely = [_product("only-dress", "dresses", 80)]
    assert build_look_around(lonely[0], lonely, occasion="casual") is None


def test_build_look_around_shoes_keeps_hero_in_shoes_slot():
    hero = _product("shoes-hero", "shoes", 80, style=["heels"])
    look = build_look_around(hero, _full_catalog() + [hero], occasion="party")
    assert look is not None
    assert look["slots"]["shoes"]["id"] == "shoes-hero"
    assert look["slots"]["outfit"]
    assert look["name"] == "Night-out edit"


def test_build_look_around_skips_companions_without_affiliate():
    catalog = _full_catalog()
    for p in catalog[1:]:
        p["affiliate_url"] = None
    assert build_look_around(catalog[0], catalog, occasion="casual") is None
