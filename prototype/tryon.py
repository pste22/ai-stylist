"""Virtual try-on request builder — pure, dependency-free.

Assembles + validates the data needed for a Gemini virtual try-on
(`recontext_image`) call, without importing the SDK or touching the network,
so it stays trivially unit-testable. The actual generation call lives in
`live_server.py`; this module only shapes and validates its inputs.

Contract is pinned by `test_tryon.py`.
"""
from __future__ import annotations

import base64
import re
from urllib.parse import quote, urlparse, urlunparse

# Image formats Gemini accepts for the person photo.
ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp"}
_MIME_ALIASES = {"image/jpg": "image/jpeg"}

# Gemini 2.5 Flash Image accepts at most 3 images per request. The front still
# occupies one slot, so the full-look composite can attach at most two extras.
MAX_LOOK_REF_IMAGES = 2

_AMAZON_IMG_BLOCK = re.compile(r"\._.+\.(jpe?g|png|webp)$", re.I)
_AMAZON_HOSTS = (
    "m.media-amazon.com",
    "images-eu.ssl-images-amazon.com",
    "images-na.ssl-images-amazon.com",
)

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
        "could not create your video", "filtered", "empty clip", "no clip",
        "no video",
    )):
        return "This clip didn't pass the preview check — try another scene or photo."
    if any(tok in s for tok in ("429", "resource_exhausted", "resource exhausted", "quota")):
        return "Mira's studio is busy right now — please try again in a moment."
    if "generate_audio" in s:
        return "Couldn't generate the video. Please try again."
    return "Something went wrong generating the video. Please try again."


def is_video_filter_failure(exc: BaseException) -> bool:
    """True when Veo finished but RAI/audio filters dropped the clip — worth one simpler retry."""
    s = f"{type(exc).__name__} {exc}".lower()
    if "timeout" in s:
        return False
    return any(tok in s for tok in (
        "safety", "rai", "audio for your prompt", "could not create your video",
        "filtered", "empty clip", "no clip", "no video",
    ))


def veo_filter_reason(resp) -> str | None:
    """Read RAI filter copy off a Veo operation response (SDK nesting varies)."""
    if resp is None:
        return None
    objs: list = [resp]
    if isinstance(resp, dict):
        inner = resp.get("generate_video_response") or resp.get("generateVideoResponse")
        if inner:
            objs.append(inner)
    else:
        inner = getattr(resp, "generate_video_response", None) or getattr(resp, "generateVideoResponse", None)
        if inner is not None:
            objs.append(inner)
    for obj in objs:
        if obj is None:
            continue
        if isinstance(obj, dict):
            val = obj.get("rai_media_filtered_reasons") or obj.get("raiMediaFilteredReasons")
        else:
            val = getattr(obj, "rai_media_filtered_reasons", None) or getattr(
                obj, "raiMediaFilteredReasons", None
            )
        if not val:
            continue
        text = " ".join(str(x) for x in val) if isinstance(val, (list, tuple)) else str(val)
        if text.strip():
            return text.strip()
    return None

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


# Fashion-reel body language, written for Veo image-to-video.
# Prompt ONLY the motion (the still is the subject). Skip brand names, "filming",
# "voiceover", and body-touch beats — those trip Veo's audio/RAI filters in ~30s.
_ETHNIC_RE = re.compile(
    r"saree|sari|lehenga|anarkali|kurta|kurti|salwar|sharara|gharara|dupatta",
    re.I,
)

_SCENE_MOTION = {
    "sangeet": (
        "A slow joyful twirl so the outfit flares under the warm lights, ending on a smile."
    ),
    "beach": (
        "A slow walk a few steps toward the camera; hair and fabric lift in a light breeze."
    ),
    "date": (
        "A small smile and a slow look toward the camera; candlelight flickers; the outfit shifts naturally."
    ),
    "office": (
        "A slow outfit-check: small smile toward the camera, a gentle turn so the workwear is visible."
    ),
    "vacation": (
        "A relaxed few steps, then a glance back over one shoulder with a smile."
    ),
    "redcarpet": (
        "A short walk, then a pause with weight on one hip and chin slightly lifted."
    ),
}


def _is_ethnic_drape(product_name: str) -> bool:
    return bool(_ETHNIC_RE.search(product_name or ""))


def _identity_guard() -> str:
    return (
        "Keep the same person and the same outfit as the photo. Photorealistic, full body "
        "in frame. Soft room tone and fabric rustle."
    )


def _drape_beat(name: str) -> str:
    if _is_ethnic_drape(name):
        return "The drape of the garment moves naturally with the turn."
    return "Fabric folds move naturally with the body."


def scene_still_prompt(product_name: str, scene: str) -> str:
    """Prompt to relocate the person (from the front try-on) into a scene as a still."""
    name = (product_name or "the outfit").strip() or "the outfit"
    setting = _SCENE_SETTINGS.get(scene, "in a beautiful, elegant setting")
    pose = (
        "Outfit-check pose as if in a mirror: weight on one hip, relaxed shoulders, "
        "soft smile toward the camera."
    )
    if _is_ethnic_drape(name):
        pose = (
            "Natural fashion pose: the drape over one shoulder, weight on one hip, "
            "soft smile, looking slightly off-camera."
        )
    return (
        f"Re-render the SAME person wearing the SAME {name} from the input image, now {setting}. "
        f"{pose} Full body in frame, photorealistic and editorial. "
        f"Keep their face, hair, body and the exact outfit identical to the input. "
        f"No text, no logos, no watermark."
    )


def scene_motion_prompt(product_name: str, scene: str) -> str:
    """Animate the scene still. Motion-only; the still already has the person + setting."""
    name = (product_name or "the outfit").strip() or "the outfit"
    action = _SCENE_MOTION.get(
        scene,
        "A slow graceful turn with a glance over the shoulder.",
    )
    return (
        f"Locked-off vertical camera. {action} {_drape_beat(name)} {_identity_guard()}"
    )


def scene_motion_fallback(product_name: str, scene: str) -> str:
    """Safer second try if Veo RAI-filters the styled motion prompt."""
    name = (product_name or "the outfit").strip() or "the outfit"
    return (
        f"Locked-off vertical camera. Gentle natural motion of the person in the {name}: "
        f"a small smile, hair and fabric moving slightly, the scene quietly alive. "
        f"{_identity_guard()}"
    )


def spin_prompt(product_name: str) -> str:
    """Showcase clip: slow fashion turn from the front try-on still."""
    name = (product_name or "the outfit").strip() or "the outfit"
    if _is_ethnic_drape(name):
        action = (
            "The person slowly turns in place and glances back over one shoulder with a "
            "small smile, so the drape of the garment is visible."
        )
    else:
        action = (
            "The person slowly turns in place, shifting weight onto one hip, then glances "
            "back over one shoulder with a small smile so the outfit is visible front to back."
        )
    return (
        f"Locked-off vertical camera, plain backdrop. The person is wearing the {name}. "
        f"{action} {_drape_beat(name)} {_identity_guard()}"
    )


def spin_fallback(product_name: str) -> str:
    """Safer second try — the motion that used to succeed before styled Reels language."""
    name = (product_name or "the outfit").strip() or "the outfit"
    return (
        f"The person slowly turns in place to show the {name} from the front, side and back. "
        f"Smooth natural motion, hair and fabric moving. {_identity_guard()}"
    )


_LOOK_SLOT_ROLE = {
    "bottoms": "bottoms",
    "shoes": "shoes",
    "bags": "bag they are carrying",
    "tops": "top",
    "accessories": "accessory",
    "outerwear": "outer layer",
    "dresses": "dress",
}


def complete_look_prompt(hero_name: str, pieces: list[dict]) -> str:
    """Image-edit prompt: keep the hero garment, add catalog bottoms/shoes/bag."""
    hero = (hero_name or "the hero piece").strip() or "the hero piece"
    extras = []
    ordinals = ("SECOND", "THIRD", "FOURTH", "FIFTH")
    for i, piece in enumerate(pieces):
        cat = (piece.get("category") or "piece").lower()
        role = _LOOK_SLOT_ROLE.get(cat, cat)
        pname = (piece.get("name") or role).strip() or role
        label = ordinals[i] if i < len(ordinals) else f"IMAGE {i + 2}"
        extras.append(f"The {label} image is the {role}: {pname}.")
    extra_s = " ".join(extras) if extras else "Add coordinating bottoms, shoes and a bag."
    return (
        f"The FIRST image is the person already wearing the {hero}. "
        f"Keep their face, hair, body and that {hero} identical. {extra_s} "
        f"Dress them in a complete full-body outfit-check look using those extra pieces — "
        f"as if they paused in front of a mirror before heading out. "
        f"Photorealistic, natural light. Do not change the {hero}. "
        f"No text, logos, watermark, or extra people."
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


def normalize_user_mime(user_mime: str | None) -> str:
    mime = (user_mime or "image/jpeg").split(";")[0].strip().lower() or "image/jpeg"
    return _MIME_ALIASES.get(mime, mime)


def candidate_image_urls(url: str) -> list[str]:
    """Catalog image URL plus Amazon-size / host / proxy fallbacks.

    Fly IPs often 403 the first ``m.media-amazon.com`` thumb, while the browser
    (and image proxies) can still load the same asset.
    """
    url = (url or "").strip()
    if not url:
        return []
    out: list[str] = []

    def add(candidate: str) -> None:
        if candidate and candidate not in out:
            out.append(candidate)

    add(url)
    match = _AMAZON_IMG_BLOCK.search(url)
    sl800 = None
    if match:
        ext = match.group(1)
        sl800 = _AMAZON_IMG_BLOCK.sub(f"._AC_SL800_.{ext}", url)

    # Image proxies immediately after the original URL. Fly IPs often hang or
    # 403 on Amazon, and waiting through size/host swaps blew the try-on budget
    # before weserv ever ran.
    if "wsrv.nl" not in url and "weserv.nl" not in url:
        proxied = sl800 or url
        add(f"https://wsrv.nl/?url={quote(proxied, safe='')}&output=jpg&n=-1")
        add(f"https://images.weserv.nl/?url={quote(proxied, safe='')}&output=jpg&n=-1")

    if match:
        add(sl800)
        add(_AMAZON_IMG_BLOCK.sub(f"._AC_SL1500_.{ext}", url))
        add(_AMAZON_IMG_BLOCK.sub(f".{ext}", url))

    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if any(h in host for h in ("media-amazon.com", "images-amazon.com", "ssl-images-amazon.com")):
            for alt in _AMAZON_HOSTS:
                if alt == host:
                    continue
                swapped = urlunparse(parsed._replace(netloc=alt))
                add(swapped)
                if match:
                    add(_AMAZON_IMG_BLOCK.sub(f"._AC_SL800_.{ext}", swapped))
    except Exception:
        pass

    return out[:12]


def garment_fetch_urls(product: dict | None) -> list[str]:
    """All fetch candidates for a catalog product (primary + gallery)."""
    if not isinstance(product, dict):
        return []
    seeds: list[str] = []
    for u in [product.get("image_url"), *(product.get("image_urls") or [])]:
        if isinstance(u, str) and u.strip() and u.strip() not in seeds:
            seeds.append(u.strip())
    out: list[str] = []
    for seed in seeds:
        for candidate in candidate_image_urls(seed):
            if candidate not in out:
                out.append(candidate)
    return out[:12]


def is_catalog_image_url(url: str) -> bool:
    """True when `url` is a catalog CDN we are willing to fetch (SSRF guard)."""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().rstrip(".")
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    if not host:
        return False
    if host in {"images.pexels.com", "m.media-amazon.com", "images-amazon.com"}:
        return True
    if host.endswith(".media-amazon.com") or host.endswith(".ssl-images-amazon.com"):
        return True
    if host.endswith(".images-amazon.com"):
        return True
    return False


def is_allowed_image_fetch_url(url: str) -> bool:
    """Catalog CDNs plus the image proxies we use when Amazon 403s Fly IPs."""
    if is_catalog_image_url(url):
        return True
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().rstrip(".")
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    return host in {"wsrv.nl", "images.weserv.nl"}


def decode_inline_image(b64: str, claimed: str | None = None) -> tuple[bytes, str]:
    """Decode a client-supplied garment/person image and sniff its real MIME."""
    if not b64:
        raise ValueError("image too small")
    raw = base64.b64decode(b64)
    return raw, sniff_image_mime(raw, claimed)


def sniff_image_mime(data: bytes, claimed: str | None = None) -> str:
    """Prefer magic bytes so HTML/octet-stream Amazon responses don't reach Gemini."""
    if not data or len(data) < 24:
        raise ValueError("image too small")
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    claimed = (claimed or "").split(";")[0].strip().lower()
    claimed = _MIME_ALIASES.get(claimed, claimed)
    if claimed in ALLOWED_MIMES:
        return claimed
    raise ValueError(f"unrecognized image type ({claimed or 'unknown'})")


def tryon_error_message(exc: BaseException) -> str:
    """User-facing copy for a still try-on failure. Never leak stack traces."""
    s = f"{type(exc).__name__} {exc}".lower()
    if any(tok in s for tok in (
        "429", "resource_exhausted", "resource exhausted", "quota",
        "unavailable", "503", "genbusy", "timeout", "timed out", "deadline",
    )):
        return "Mira's studio is busy right now — please try again in a moment."
    if any(tok in s for tok in (
        "safety", "blocked", "prohibited", "finish_reason", "rai",
    )):
        return "Try-on couldn't be generated for this photo. Try a clear, front-facing full-body shot."
    if any(tok in s for tok in (
        "http error", "urlopen", "403", "404", "fetch",
        "unrecognized image", "image too small",
    )):
        return "Couldn't load this piece's photo. Try another item."
    if any(tok in s for tok in (
        "invalid_argument", "too large", "payload", "7 mb", "maximum",
    )):
        return "That photo is too heavy for try-on. Try a smaller or clearer shot."
    return "Something went wrong generating your try-on. Please try again."


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

    user_mime = normalize_user_mime(user_mime)
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
        f"Outfit-check pose as if standing in front of a bedroom mirror: weight on one hip, "
        f"relaxed shoulders, soft smile toward the camera, natural soft light, clean backdrop. "
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
