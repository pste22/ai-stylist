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


# Curated, occasion-led scenes for the "see it in a setting" videos.
# India-aspirational and tasteful; each is art-directed (locked lighting/vibe).
SCENES = ("sangeet", "beach", "date", "office", "vacation", "redcarpet")

_SCENE_SETTINGS = {
    "sangeet":   "at a joyful Indian sangeet celebration — warm fairy lights and softly blurred "
                 "marigold and floral decor behind, festive golden-hour ambiance",
    "beach":     "standing on a sandy beach at golden hour — gentle waves and warm low sunlight behind",
    "date":      "at an intimate candle-lit rooftop restaurant at night — soft city bokeh lights behind, "
                 "warm romantic ambiance",
    "office":    "at an elegant evening cocktail / office party — a stylish modern venue with soft "
                 "ambient lighting and gentle bokeh",
    "vacation":  "exploring a picturesque travel destination — a sunlit heritage palace courtyard, "
                 "natural daylight and a scenic backdrop",
    "redcarpet": "on a glamorous red carpet — an elegant backdrop with soft camera-flash sparkle",
}


def scene_still_prompt(product_name: str, scene: str) -> str:
    """Prompt to relocate the person (from the front try-on) into a scene as a still."""
    name = (product_name or "the outfit").strip() or "the outfit"
    setting = _SCENE_SETTINGS.get(scene, "in a beautiful, elegant setting")
    return (
        f"Re-render the SAME person wearing the SAME {name} from the input image, now {setting}. "
        f"Keep their face, hair, body and the exact outfit identical to the input. "
        f"Full body in frame, natural confident pose, photorealistic and editorial. "
        f"No text, no logos, no watermark."
    )


def scene_motion_prompt(product_name: str, scene: str) -> str:
    """Prompt to animate the scene still into a short cinematic clip (subtle ambient motion)."""
    name = (product_name or "the outfit").strip() or "the outfit"
    return (
        f"A short, photorealistic cinematic video of the person in the {name}. "
        f"Subtle, natural ambient motion — a gentle breeze moving hair and fabric, a soft smile, "
        f"the surroundings quietly alive — while the person stays elegantly in place, full body in "
        f"frame. Keep identity and outfit consistent throughout. No text or logos."
    )


def spin_prompt(product_name: str) -> str:
    """Prompt for the Veo 360° 'spin' video, seeded from the front try-on image."""
    name = (product_name or "the outfit").strip() or "the outfit"
    return (
        f"The person slowly turns a full 360 degrees in place to show the {name} from "
        f"every angle — front, side, back, side, front — a smooth fashion-runway turntable "
        f"rotation. Keep the person's identity, hair and the outfit consistent throughout; "
        f"studio background, full body in frame, natural lighting."
    )


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
            f"Editorial confidence, natural light, identity and garment unchanged."
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
        f"Frame it like a premium editorial fashion lookbook shot: confident posture, "
        f"natural soft studio light, clean backdrop, fabric drape and fit that feel "
        f"elevated and exciting on them — a real 'wow, that's me upgraded' moment. "
        f"Keep their face, hair, skin tone, identity and body proportions EXACTLY as in "
        f"the first photo — no beauty filters, no slimming, no face morphing; only change "
        f"the outfit to the garment. Fit the garment naturally with realistic cloth folds. "
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
