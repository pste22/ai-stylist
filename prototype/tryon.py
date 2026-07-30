"""Virtual try-on request builder — pure, dependency-free.

Assembles + validates the data needed for a Gemini virtual try-on
(`recontext_image`) call, without importing the SDK or touching the network,
so it stays trivially unit-testable. The actual generation call lives in
`live_server.py`; this module only shapes and validates its inputs.

Contract is pinned by `test_tryon.py`.
"""
from __future__ import annotations

# Image formats Gemini accepts for the person photo.
ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp"}


def build_tryon_request(product, user_image_b64, user_mime: str = "image/jpeg") -> dict:
    """Validate inputs and assemble the try-on request payload.

    Args:
        product: catalog product dict; must have a non-empty ``image_url``.
        user_image_b64: base64 of the user's photo (non-empty).
        user_mime: MIME of the user photo; one of ``ALLOWED_MIMES``.

    Returns:
        dict with keys ``product_id``, ``product_name``, ``product_image_url``,
        ``user_image_b64``, ``user_mime``, ``prompt``.

    Raises:
        ValueError: on any invalid input.
    """
    if not isinstance(product, dict):
        raise ValueError("product must be a dict")

    product_image_url = (product.get("image_url") or "").strip()
    if not product_image_url:
        raise ValueError("product is missing an image_url")

    if not user_image_b64:
        raise ValueError("user_image_b64 is required")

    if user_mime not in ALLOWED_MIMES:
        raise ValueError(
            f"unsupported user_mime {user_mime!r}; expected one of {sorted(ALLOWED_MIMES)}"
        )

    product_name = (product.get("name") or "this item").strip() or "this item"

    prompt = (
        f"Generate a photorealistic image of the person in the FIRST photo "
        f"wearing the {product_name} shown in the SECOND photo. "
        f"Keep the person's face, hair, pose, skin tone and body proportions "
        f"unchanged; fit the garment naturally and realistically to their body. "
        f"Return only the resulting image."
    )

    return {
        "product_id": product.get("id"),
        "product_name": product_name,
        "product_image_url": product_image_url,
        "user_image_b64": user_image_b64,
        "user_mime": user_mime,
        "prompt": prompt,
    }
