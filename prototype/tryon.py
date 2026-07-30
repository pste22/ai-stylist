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

# Ordered camera angles for the "see it from all sides" try-on turntable.
# "front" is generated from the person + garment; the rest are generated FROM the
# front result so identity, hair and garment stay consistent across angles.
TRYON_VIEWS = ("front", "side", "back")

_VIEW_LABELS = {"front": "Front", "side": "Side", "back": "Back", "three_quarter": "¾"}


def view_label(view: str) -> str:
    """Human-friendly label for a view key."""
    return _VIEW_LABELS.get(view, view.title())


def view_instruction(product_name: str, view: str) -> str:
    """Prompt for re-rendering the already-generated front try-on from another angle.

    The base image supplied to the model is the FRONT try-on result, so these
    prompts ask for a rotated view of that same person + outfit.
    """
    name = (product_name or "the outfit").strip() or "the outfit"
    if view == "front":
        # Front is produced by build_tryon_request; kept here for completeness.
        return (
            f"Photorealistic front view of the person wearing the {name}. "
            f"Keep identity, hair, pose and garment realistic."
        )
    if view == "side":
        return (
            f"Show the EXACT same person wearing the EXACT same {name}, turned 90° "
            f"to a side profile. FULL-LENGTH head-to-toe framing — do not crop the head "
            f"or feet. Keep their face, hair, body and the garment identical; "
            f"same lighting and background. Return only the image."
        )
    if view == "back":
        return (
            f"Show the EXACT same person wearing the EXACT same {name}, viewed from "
            f"directly behind so the back of the outfit is visible. FULL-LENGTH head-to-toe "
            f"framing — do not crop the head or feet. Keep their hair, body and the garment "
            f"identical; same lighting and background. Return only the image."
        )
    return (
        f"Show the EXACT same person wearing the EXACT same {name} from a three-quarter "
        f"angle. Keep identity and garment identical. Return only the image."
    )


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
        f"Generate a photorealistic, FULL-LENGTH (head-to-toe) image of the person in "
        f"the FIRST photo wearing the {product_name} shown in the SECOND photo. "
        f"Show the person's COMPLETE face clearly and their ENTIRE body from the top of "
        f"the head down to the feet — do not crop the head, face or legs. "
        f"Frame it like a full-body fashion showroom / fitting-room photo: the person "
        f"standing straight, centered, against a clean studio background. "
        f"Keep their face, hair, skin tone and body proportions EXACTLY as in the first "
        f"photo; only change their outfit to the garment. Fit the garment naturally. "
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
