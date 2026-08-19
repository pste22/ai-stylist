"""Contract test for the virtual try-on request builder.

This test defines the EXACT contract the overnight agent must implement in
`prototype/tryon.py`. It is intentionally committed BEFORE the implementation
exists — the agent's job is to make it pass without weakening these assertions.

Run from the prototype/ directory:
    .venv/bin/python -m pytest test_tryon.py -v
"""
import base64

import pytest

from tryon import build_tryon_request  # implemented by the agent in prototype/tryon.py


# A tiny valid base64 payload (not a real image — the builder must not decode it).
_IMG_B64 = base64.b64encode(b"fake-jpeg-bytes").decode()

_PRODUCT = {
    "id": "prod-123",
    "name": "Allen Solly Women Blouse",
    "category": "tops",
    "image_url": "https://m.media-amazon.com/images/I/71rTi9Q0L3L._AC_UL320_.jpg",
}


def test_valid_request_returns_expected_shape():
    req = build_tryon_request(_PRODUCT, _IMG_B64, "image/jpeg")
    assert isinstance(req, dict)
    assert req["product_id"] == "prod-123"
    assert req["product_name"] == "Allen Solly Women Blouse"
    assert req["product_image_url"] == _PRODUCT["image_url"]
    assert req["user_image_b64"] == _IMG_B64
    assert req["user_mime"] == "image/jpeg"
    # A non-empty instruction prompt that references the product so the model
    # knows what to place on the person.
    assert isinstance(req["prompt"], str) and req["prompt"].strip()
    assert "Allen Solly Women Blouse" in req["prompt"]


def test_mime_defaults_to_jpeg():
    req = build_tryon_request(_PRODUCT, _IMG_B64)
    assert req["user_mime"] == "image/jpeg"


def test_empty_user_image_raises():
    with pytest.raises(ValueError):
        build_tryon_request(_PRODUCT, "", "image/jpeg")


def test_none_user_image_raises():
    with pytest.raises(ValueError):
        build_tryon_request(_PRODUCT, None, "image/jpeg")


def test_none_product_raises():
    with pytest.raises(ValueError):
        build_tryon_request(None, _IMG_B64, "image/jpeg")


def test_product_without_image_url_raises():
    bad = {"id": "x", "name": "No Image Product"}
    with pytest.raises(ValueError):
        build_tryon_request(bad, _IMG_B64, "image/jpeg")


def test_unsupported_mime_raises():
    with pytest.raises(ValueError):
        build_tryon_request(_PRODUCT, _IMG_B64, "image/gif")


@pytest.mark.parametrize("mime", ["image/jpeg", "image/png", "image/webp"])
def test_supported_mimes_accepted(mime):
    req = build_tryon_request(_PRODUCT, _IMG_B64, mime)
    assert req["user_mime"] == mime


def test_party_alias_is_office_scene():
    from tryon import SCENES, normalize_video_kind
    assert normalize_video_kind("party") == "office"
    assert normalize_video_kind("office") in SCENES
    assert normalize_video_kind("spin") == "spin"
    assert normalize_video_kind(None) == "spin"


def test_spin_prompt_is_fashion_reel_not_turntable():
    from tryon import spin_prompt
    p = spin_prompt("VERO MODA Women's Slim")
    assert "VERO MODA Women's Slim" in p
    assert "turntable" not in p.lower()
    assert "shoulder" in p.lower()
    assert "9:16" in p
    assert "identical" in p.lower()


def test_saree_showcase_uses_pallu_language():
    from tryon import spin_prompt
    p = spin_prompt("Pink Banarasi Saree")
    assert "pallu" in p.lower()
    western = spin_prompt("Slim Fit Jeans")
    assert "pallu" not in western.lower()


def test_scene_motion_is_occasion_specific():
    from tryon import scene_motion_prompt
    date = scene_motion_prompt("silk dress", "date")
    sangeet = scene_motion_prompt("silk dress", "sangeet")
    beach = scene_motion_prompt("silk dress", "beach")
    assert date != sangeet != beach
    assert "neckline" in date.lower() or "collarbone" in date.lower()
    assert "twirl" in sangeet.lower()
    assert "breeze" in beach.lower() or "walk" in beach.lower()
    assert "9:16" in date


def test_scene_still_starts_in_a_reel_pose():
    from tryon import scene_still_prompt
    still = scene_still_prompt("office blazer", "office")
    assert "hip" in still.lower()
    saree = scene_still_prompt("Red Silk Saree", "sangeet")
    assert "pallu" in saree.lower() or "dupatta" in saree.lower()


def test_video_error_message_maps_known_failures():
    from tryon import video_error_message
    assert "too long" in video_error_message(TimeoutError("video generation timed out")).lower()
    assert "preview check" in video_error_message(RuntimeError("audio for your prompt")).lower()
    assert "busy" in video_error_message(RuntimeError("429 RESOURCE_EXHAUSTED")).lower()
    generic = video_error_message(RuntimeError("generate_audio is only supported in Gemini Enterprise"))
    assert "try again" in generic.lower()
    assert "traceback" not in generic.lower()
