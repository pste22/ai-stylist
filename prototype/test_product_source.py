"""Tests for the Amazon affiliate source (P3-1).

Credential-free: we exercise the PA-API → our-schema normalization with a sample item
and the source factory's graceful fallback. No network, no keys.
"""
from __future__ import annotations

import os

import product_source as ps


# A trimmed-down shape of one PA-API SearchItems result item.
_SAMPLE_ITEM = {
    "ASIN": "B0EXAMPLE1",
    "DetailPageURL": "https://www.amazon.com/dp/B0EXAMPLE1?tag=mira-20",
    "ItemInfo": {"Title": {"DisplayValue": "Relaxed Linen Button-Down Shirt"}},
    "Offers": {"Listings": [{"Price": {"Amount": 42.99, "Currency": "USD"}}]},
    "Images": {"Primary": {"Medium": {"URL": "https://m.media-amazon.com/img1.jpg"}}},
}


def test_normalize_maps_core_fields():
    p = ps.normalize_paapi_item(_SAMPLE_ITEM)
    assert p["id"] == "B0EXAMPLE1"
    assert p["name"] == "Relaxed Linen Button-Down Shirt"
    assert p["price"] == 42.99
    assert p["category"] == "tops"  # inferred from "shirt"
    assert p["affiliate_url"].endswith("tag=mira-20")  # monetizable, already tagged
    assert p["image_url"] == "https://m.media-amazon.com/img1.jpg"


def test_normalize_degrades_when_fields_missing():
    p = ps.normalize_paapi_item({"ASIN": "B0BARE"})
    assert p["id"] == "B0BARE"
    assert p["name"] == "Untitled"
    assert p["price"] is None
    assert p["affiliate_url"] is None
    assert p["image_url"] is None


def test_infer_category():
    assert ps._infer_category("Suede Chelsea Boots") == "shoes"
    assert ps._infer_category("Floral Wrap Dress") == "dresses"
    assert ps._infer_category("Quilted Puffer Jacket") == "outerwear"
    assert ps._infer_category("Mystery Object") is None


def test_get_source_defaults_to_local():
    assert isinstance(ps.get_source("local"), ps.LocalJsonSource)


def test_get_source_amazon_falls_back_without_keys(monkeypatch):
    # No Amazon credentials in env → must degrade to local, never crash.
    for k in ("AMAZON_ACCESS_KEY", "AMAZON_SECRET_KEY", "AMAZON_PARTNER_TAG"):
        monkeypatch.delenv(k, raising=False)
    assert isinstance(ps.get_source("amazon"), ps.LocalJsonSource)


def test_amazon_affiliate_url_from_asin(monkeypatch):
    monkeypatch.setenv("AMAZON_PARTNER_TAG", "mira-20")
    url = ps.amazon_affiliate_url("B0EXAMPLE1")
    assert url == "https://www.amazon.com/dp/B0EXAMPLE1/?tag=mira-20"
    # explicit tag overrides env
    assert ps.amazon_affiliate_url("B0ABC", "other-21").endswith("tag=other-21")


def test_curated_source_reads_real_items(tmp_path, monkeypatch):
    import json

    monkeypatch.setenv("AMAZON_PARTNER_TAG", "mira-20")
    seed = tmp_path / "affiliate_products.json"
    seed.write_text(json.dumps([
        {"_comment": "template row — must be ignored", "asin": "B0XXXXXXXXX"},
        {"asin": "B0REAL1", "id": "B0REAL1", "name": "Linen Shirt",
         "category": "tops", "color": "sand", "price": 39.0,
         "style": ["casual"], "gender": "unisex", "image_url": "x.jpg",
         "affiliate_url": ""},  # empty → auto-built from ASIN
    ]))
    src = ps.CuratedAmazonSource(path=str(seed))
    results = src.search(category="tops")
    assert len(results) == 1  # template row dropped
    assert results[0]["affiliate_url"] == "https://www.amazon.com/dp/B0REAL1/?tag=mira-20"


def test_curated_source_template_only_raises(tmp_path):
    import json

    seed = tmp_path / "affiliate_products.json"
    seed.write_text(json.dumps([{"_comment": "only a template here"}]))
    try:
        ps.CuratedAmazonSource(path=str(seed))
        assert False, "expected RuntimeError for template-only file"
    except RuntimeError:
        pass


def test_get_source_curated_falls_back_when_unseeded(monkeypatch):
    # Don't assert against the bundled data file — it is seeded now, which made this
    # test fail for a reason that had nothing to do with the fallback it covers.
    def _raise():
        raise RuntimeError("template-only seed file")

    monkeypatch.setattr(ps, "CuratedAmazonSource", lambda *a, **k: _raise())
    assert isinstance(ps.get_source("curated"), ps.LocalJsonSource)


def test_get_source_curated_used_when_seeded():
    assert isinstance(ps.get_source("curated"), ps.CuratedAmazonSource)
