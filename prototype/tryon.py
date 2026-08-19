"""Virtual try-on request builder — pure, dependency-free.

Assembles + validates the data needed for a Gemini virtual try-on
(`recontext_image`) call, without importing the SDK or touching the network,
so it stays trivially unit-testable. The actual generation call lives in
`live_server.py`; this module only shapes and validates its inputs.

Contract is pinned by `test_tryon.py`.
"""
from __future__ import annotations

import re

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

# UI labels like "Party" still send the backend key "office"; accept the label too.
_SCENE_ALIASES = {
    "party": "office",
    "date night": "date",
    "datenight": "date",
    "red carpet": "redcarpet",
    "red-carpet": "redcarpet",
}


def normalize_video_kind(kind: str | None) -> str:
    """Map a client video-kind string onto spin or a SCENES key."""
    k = (kind or "spin").strip().lower()
    return _SCENE_ALIASES.get(k, k) or "spin"


def video_error_message(exc: BaseException) -> str:
    """User-facing copy for a Veo / polling failure. Never leak stack traces."""
    s = f"{type(exc).__name__} {exc}".lower()
    if "timeout" in s:
        return "That video took too long — tap the scene to try again."
    if any(tok in s for tok in (
        "safety", "rai", "person_generation", "audio for your prompt",
        "could not create your video", "filtered",
    )):
        return "This clip didn't pass the preview check — try another scene or photo."
    if any(tok in s for tok in ("429", "resource_exhausted", "resource exhausted", "quota")):
        return "Mira's studio is busy right now — please try again in a moment."
    if "generate_audio" in s:
        return "Couldn't generate the video. Please try again."
    return "Something went wrong generating the video. Please try again."

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


# Indian fashion-Reel body language (hair-touch + downward glance, collarbone/
# neckline pose, walk-away to show the back, saree pallu drape + confident smile).
# Veo 3.1 follows one camera + one continuous action best — do not stack cuts.
_ETHNIC_RE = re.compile(
    r"saree|sari|lehenga|anarkali|kurta|kurti|salwar|sharara|gharara|dupatta",
    re.I,
)

_SCENE_MOTION = {
    "sangeet": (
        "One continuous action: a joyful fashion twirl so the outfit flares and catches "
        "the fairy lights, then they settle facing the camera with a bright, confident smile."
    ),
    "beach": (
        "One continuous action: a slow walk a few steps toward the camera, hair and fabric "
        "lifting in the sea breeze, then a glance off to the side with a soft smile."
    ),
    "date": (
        "One continuous action: they look down at the outfit as if checking the mirror, "
        "then lift their chin to the camera with a small smile, fingertips grazing the "
        "neckline or collarbone so the fit is the hero."
    ),
    "office": (
        "One continuous action: a gentle in-place sway as if music is playing, weight on "
        "one hip, one hand on the waist, ending on a confident smile at the camera."
    ),
    "vacation": (
        "One continuous action: a relaxed stroll a few steps, then they look back over "
        "one shoulder at the camera so the back of the outfit is visible."
    ),
    "redcarpet": (
        "One continuous action: a short fashion-walk, stop on the mark, shift weight onto "
        "one hip and hold a red-carpet pose, chin slightly lifted."
    ),
}


def _is_ethnic_drape(product_name: str) -> bool:
    return bool(_ETHNIC_RE.search(product_name or ""))


def _reel_camera() -> str:
    return (
        "Vertical 9:16 Instagram fashion reel, locked-off smartphone camera, "
        "subject centered, photorealistic natural light."
    )


def _identity_guard(name: str) -> str:
    return (
        f"Keep the person's face, hair, skin, body and the exact {name} identical to the "
        "input image — no beauty filters, no slimming, no face morphing, no extra people. "
        "No text, logos, or watermark."
    )


def _drape_beat(name: str) -> str:
    if _is_ethnic_drape(name):
        return (
            f"Let the pallu or dupatta of the {name} drape and catch the light as they move; "
            "the fabric should feel alive, never glued to the body."
        )
    return (
        f"Let the fabric of the {name} move with the body — folds, hem and sleeves should "
        "show how it actually wears."
    )


def scene_still_prompt(product_name: str, scene: str) -> str:
    """Prompt to relocate the person (from the front try-on) into a scene as a still."""
    name = (product_name or "the outfit").strip() or "the outfit"
    setting = _SCENE_SETTINGS.get(scene, "in a beautiful, elegant setting")
    pose = (
        "Fashion-reel starting pose: weight on one hip, relaxed shoulders, one hand lightly "
        "at the hair or garment, soft smile, looking slightly off-camera."
    )
    if _is_ethnic_drape(name):
        pose = (
            "Fashion-reel starting pose: pallu or dupatta draped over one shoulder, one hand "
            "lightly adjusting the drape, weight on one hip, soft smile, looking slightly off-camera."
        )
    return (
        f"Re-render the SAME person wearing the SAME {name} from the input image, now {setting}. "
        f"{pose} Full body in frame, photorealistic and editorial. {_identity_guard(name)}"
    )


def scene_motion_prompt(product_name: str, scene: str) -> str:
    """Animate the scene still as an Instagram-style fashion reel (one action)."""
    name = (product_name or "the outfit").strip() or "the outfit"
    action = _SCENE_MOTION.get(
        scene,
        "One continuous action: a slow graceful turn with a look over the shoulder.",
    )
    return (
        f"{_reel_camera()} Full body in frame. The same person wearing the same {name} as in "
        f"the input image. {action} {_drape_beat(name)} {_identity_guard(name)} "
        "Quiet ambient sound, fabric rustle, no voiceover."
    )


def spin_prompt(product_name: str) -> str:
    """Showcase clip: Instagram-reel body language, seeded from the front try-on."""
    name = (product_name or "the outfit").strip() or "the outfit"
    if _is_ethnic_drape(name):
        action = (
            "One continuous action: they lightly touch their hair, glance down at the drape, "
            "then a slow graceful turn until they look back over one shoulder with a soft "
            "confident smile, so the pallu and the back of the blouse are visible."
        )
    else:
        action = (
            "One continuous action: a slow fashion-reel showcase — weight shifts onto one hip, "
            "one hand smooths the garment, then they rotate until they glance back over one "
            "shoulder at the camera with a soft smile, showing how the outfit sits front-to-back. "
            "Not a mechanical 360 spin; it should feel like an Indian fashion creator filming a Reel."
        )
    return (
        f"{_reel_camera()} Full body in frame, clean studio or plain wall behind. "
        f"The same person wearing the same {name} as in the input image. {action} "
        f"{_drape_beat(name)} {_identity_guard(name)} Quiet room ambience, no voiceover."
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
