from look_engine import build_looks


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
