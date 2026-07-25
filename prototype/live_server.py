"""Mira voice bridge — browser ⇆ Gemini Live (P2-2 / P2-3 wiring).

A thin WebSocket relay that keeps the GEMINI_API_KEY on the server and bridges the
browser to a Gemini Live session. The browser streams mic audio up; we stream Mira's
audio back down and emit avatar-state events the UI maps onto `avatarState`
(idle / thinking / talking / reacting) — see docs/14-ui-strategy.md.

This promotes the S1 spike (spikes/path_b_gemini_live.py) into a real, reusable
service. Same persona + full-catalog grounding as the brain.

Protocol (one WS connection per session):
  browser → server
    • binary frame      : PCM16 mono @16kHz mic audio (streamed continuously)
    • {"type":"reset"}  : (optional) end the current turn early
  server → browser
    • binary frame                         : PCM16 mono @24kHz Mira audio to play
    • {"type":"state","state":..,"mood":..}: drive the avatar
    • {"type":"transcript","who":..,"text":..}: captions
    • {"type":"interrupted"}               : barge-in — browser flushes playback

Run:  .venv/bin/python live_server.py          # ws://localhost:8765
Needs: GEMINI_API_KEY in prototype/.env  +  websockets, google-genai (already in venv).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time

from dotenv import load_dotenv

# Load THIS package's .env (prototype/.env) regardless of the process CWD, so keys are
# found whether the bridge is launched from the repo root or from prototype/.
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

import websockets
from websockets.asyncio.server import serve

import events  # noqa: E402
import user_store  # noqa: E402
import chat_store  # noqa: E402
from stylist import SYSTEM_PROMPT  # noqa: E402  (the SAME persona + grounding rules)
from product_source import get_source  # noqa: E402
from look_engine import build_looks  # noqa: E402

# Ground the voice on the ACTIVE source (env PRODUCT_SOURCE: local / curated / amazon),
# not just the bundled demo catalog — so curated SiteStripe / PA-API items Mira can
# actually earn on flow straight into the spoken conversation. See docs/10-sourcing.
_SOURCE = get_source()
# Full catalog for "Show 10 more" paging — never put all of this in the AI prompt.
_CATALOG = _SOURCE.search(limit=2000)
# Curated spotlight (≤50 products, ~2 per category) for the grounding prompt so
# Mira has focused, speakable recommendations without a 40k-token product dump.
_SPOTLIGHT_PER_CAT = 5
_SPOTLIGHT: list[dict] = []
_seen_cats: dict = {}
for _p in _CATALOG:
    _cat = _p.get("category", "other")
    if _seen_cats.get(_cat, 0) < _SPOTLIGHT_PER_CAT:
        _SPOTLIGHT.append(_p)
        _seen_cats[_cat] = _seen_cats.get(_cat, 0) + 1
# Index by id so we can match Mira's spoken recommendations.
_BY_ID = {p["id"]: p for p in _CATALOG}


_BUDGET_RANGES = {
    "budget":  (0,   50),
    "mid":     (50,  150),
    "premium": (150, 400),
    "luxury":  (400, 9999),
}
_BUDGET_LABELS = {
    "budget": "under $50", "mid": "$50–$150",
    "premium": "$150–$400", "luxury": "$400+",
}
_FOCUS_CATS = {
    "everyday":   {"tops", "bottoms", "shoes", "activewear"},
    "work":       {"tops", "bottoms", "outerwear", "bags", "accessories"},
    "occasions":  {"dresses", "outerwear", "accessories", "shoes", "bags"},
    "everything": None,
}


def _taste_profile(saved_ids: list) -> str | None:
    """Derive a short taste description from a user's saved products."""
    from collections import Counter
    products = [_BY_ID[pid] for pid in saved_ids if pid in _BY_ID]
    if not products:
        return None
    cats   = Counter(p.get("category") for p in products if p.get("category"))
    colors = Counter(p.get("color")    for p in products if p.get("color"))
    prices = [p["price"] for p in products if p.get("price")]
    parts  = []
    if cats:
        parts.append("loves " + ", ".join(c for c, _ in cats.most_common(3)))
    if colors:
        parts.append("prefers " + "/".join(c for c, _ in colors.most_common(2)) + " tones")
    if prices:
        parts.append(f"avg saved price ${sum(prices)/len(prices):.0f}")
    return "; ".join(parts) if parts else None


def _personalized_top_picks(
    prefs: dict | None,
    exclude_ids: set,
    n: int = 10,
) -> list:
    """Return n spotlight products biased toward the user's budget and focus area."""
    budget_key = (prefs or {}).get("budget")
    focus_key  = (prefs or {}).get("shopping_focus")
    price_range = _BUDGET_RANGES.get(budget_key) if budget_key else None
    focus_cats  = _FOCUS_CATS.get(focus_key)     if focus_key  else None

    scored = []
    for p in _SPOTLIGHT:
        if p["id"] in exclude_ids:
            continue
        score = 0
        price = p.get("price", 0) or 0
        if price_range:
            lo, hi = price_range
            if lo <= price <= hi:
                score += 10
            elif abs(price - (lo + hi) / 2) < 40:
                score += 3
        if focus_cats and p.get("category") in focus_cats:
            score += 5
        scored.append((score, p))

    scored.sort(key=lambda x: -x[0])
    picks = [p for _, p in scored]

    # Fill remainder from spotlight if not enough matched
    if len(picks) < n:
        seen = {p["id"] for p in picks}
        for p in _SPOTLIGHT:
            if p["id"] not in seen and p["id"] not in exclude_ids:
                picks.append(p)
            if len(picks) >= n:
                break

    return picks[:n]


def _resolve_pincode_sync(pin_code: str) -> dict | None:
    """Resolve an Indian PIN code to city/state using India Post API (blocking)."""
    import urllib.request
    try:
        url = f"https://api.postalpincode.in/pincode/{pin_code}"
        with urllib.request.urlopen(url, timeout=4) as resp:
            import json as _json
            data = _json.loads(resp.read())
            if data and data[0].get("Status") == "Success":
                po = (data[0].get("PostOffice") or [{}])[0]
                return {
                    "pin_code": pin_code,
                    "city":     po.get("District", ""),
                    "state":    po.get("State", ""),
                    "division": po.get("Division", ""),
                }
    except Exception:
        pass
    return None


def full_grounding_prompt(memory: str = "", prefs: dict | None = None, taste: str | None = None, event_brief: dict | None = None, location_info: dict | None = None) -> str:
    """Persona + optional user memory + curated product spotlight as grounding."""
    parts = [SYSTEM_PROMPT]

    if prefs:
        profile = []
        if prefs.get("style_vibe"):
            profile.append(f"Style: {prefs['style_vibe']}")
        if prefs.get("shopping_focus"):
            profile.append(f"Shops for: {prefs['shopping_focus']}")
        if prefs.get("top_size"):
            profile.append(f"Top size: {prefs['top_size']}")
        if prefs.get("bottom_size"):
            profile.append(f"Bottom size: {prefs['bottom_size']}")
        if prefs.get("budget"):
            profile.append(f"Budget: {_BUDGET_LABELS.get(prefs['budget'], prefs['budget'])} per piece")
        if taste:
            profile.append(f"Taste from saves: {taste}")
        if location_info:
            profile.append(
                f"Location: {location_info['city']}, {location_info['state']} (PIN {location_info['pin_code']}) — "
                f"prioritise products deliverable here; reference local weather and occasions naturally"
            )
        elif prefs.get("pin_code"):
            profile.append(f"PIN code: {prefs['pin_code']} (location not resolved)")
        if profile:
            parts.append(
                "USER PROFILE (weave this into recommendations naturally — never recite it):\n"
                + "\n".join(profile)
            )

    if memory:
        parts.append(f"SHOPPER CONTEXT (use naturally, never recite as a list):\n{memory}")
    if event_brief and event_brief.get("occasion"):
        fields = [
            f"{label}: {event_brief[key]}"
            for key, label in (
                ("occasion", "occasion"),
                ("date", "date"),
                ("location", "location"),
                ("dress_code", "dress code"),
                ("vibe", "desired vibe"),
                ("budget_max", "total budget"),
                ("constraints", "non-negotiables"),
            )
            if event_brief.get(key)
        ]
        parts.append(
            "EVENT BRIEF (the shopper submitted this before the chat):\n"
            + "\n".join(f"- {field}" for field in fields)
            + "\n\nStart by acknowledging the brief. Ask only one concise question if a "
            "critical detail is missing; otherwise help them decide between the three "
            "grounded look drafts already shown in the interface. Never invent an item."
        )
    parts.append(
        f"PRODUCTS you may recommend (curated spotlight — {len(_CATALOG)} total in catalog):\n"
        f"{_SOURCE.render(_SPOTLIGHT)}\n\n"
        f"RULES:\n"
        f"- The UI automatically shows product cards when you mention items — NEVER list product names in your reply. "
        f"No bullet lists, no numbered lists, no repeating the product title. "
        f"Instead speak about them naturally: 'I love this flowy wrap dress for a wedding — the floral print is perfect for the occasion' "
        f"rather than naming or listing it.\n"
        f"- Mention one distinctive detail per item (color, silhouette, why it fits the occasion) so the shopper can picture it.\n"
        f"- Only recommend up to 3 products per turn — quality over quantity. "
        f"If the user asks to see more than 3 at once, apologise briefly: 'I can only show 3 at a time — let me make sure these are exactly right for you.'\n"
        f"- 3 curated picks are already on screen when the user opens the app — greet them warmly and invite them to ask anything.\n"
        f"- When the shopper wants to browse further, say 'tap Show more to see the next 3'."
    )
    return "\n\n".join(parts)


# Per-product "signature" tokens for spoken-name matching (see _match_products): the
# words in a product's name/color that are UNIQUE to it within the spotlight set. Built
# from _SPOTLIGHT (the curated products Mira knows about) so matches stay reliable.
def _build_distinctive() -> dict[str, set[str]]:
    def toks(s: str) -> set[str]:
        return {w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(w) >= 5}

    name_tokens = {p["id"]: toks(p["name"]) | toks(p.get("color", "")) for p in _SPOTLIGHT}
    df: dict[str, int] = {}
    for t in name_tokens.values():
        for w in t:
            df[w] = df.get(w, 0) + 1
    return {pid: {w for w in t if df[w] == 1} for pid, t in name_tokens.items()}


_DISTINCTIVE = _build_distinctive()

# Generic descriptor words that can appear in product names but ALSO show up in ordinary
# speech ("walking around", "casual day dress"). On their own they must NOT trigger a
# product card — only a brand/model word, or two such descriptors together, counts.
_GENERIC_TOKENS = {
    # footwear
    "sneakers", "shoes", "boots", "heels", "loafers", "pumps", "sandals", "wedges",
    # tops / outerwear
    "shirt", "blouse", "sweater", "hoodie", "jacket", "blazer", "cardigan", "pullover",
    "sweatshirt", "camisole", "bralette",
    # bottoms / dresses
    "dress", "dresses", "skirt", "jeans", "pants", "trousers", "shorts", "leggings",
    # style words Mira uses naturally in speech
    "casual", "classic", "elegant", "chic", "trendy", "stylish", "fitted", "flared",
    "vintage", "floral", "printed", "striped", "solid", "flare", "oversized", "loose",
    "midi", "maxi", "mini", "high", "waist", "neck", "sleeve", "strap", "lace",
    "satin", "velvet", "denim", "knit", "ribbed", "woven", "cotton", "linen",
    # colors
    "black", "white", "gray", "grey", "navy", "blue", "green", "brown", "beige",
    "cream", "camel", "olive", "coral", "blush", "khaki", "ivory", "gold", "silver",
    # generic fashion modifiers
    "women", "womens", "ladies", "girls", "summer", "winter", "spring", "autumn",
    "comfortable", "lightweight", "breathable", "stretchy", "athletic", "sporty",
    "formal", "office", "casual", "everyday", "vacation", "beach", "workout",
    "going", "party", "event", "wear", "style", "fashion", "basic", "simple",
    "pack", "bundle", "sizes", "pockets", "pocket", "collar", "sleeve",
    "short", "long", "regular", "loose", "tight", "baggy", "skinny", "slim",
}

# Affiliate handoff (Phase 3): we NEVER sell or ship — "Buy" deep-links to a retailer
# who fulfils, and we earn a disclosed commission (docs/10-sourcing-strategy.md).
# Until a real affiliate feed is wired (P3-1), synthesize an honest search handoff so
# the buy flow is real and clickable. A real per-item `affiliate_url` overrides this.
from urllib.parse import quote_plus  # noqa: E402


def _affiliate_url(p: dict) -> str:
    if p.get("affiliate_url"):
        return p["affiliate_url"]
    query = quote_plus(f"{p['color']} {p['name']}")
    return f"https://www.google.com/search?tbm=shop&q={query}"

_MODEL = os.environ.get("GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview")
_VOICE = os.environ.get("GEMINI_LIVE_VOICE", "Aoede")
_HOST = os.environ.get("MIRA_WS_HOST", "localhost")
_PORT = int(os.environ.get("MIRA_WS_PORT", "8765"))

# Cost guardrails — both configurable via env so you can tighten as usage grows.
# Idle timeout: close Live session (and stop billing) after N seconds of silence.
_IDLE_TIMEOUT_SEC  = int(os.environ.get("MIRA_IDLE_TIMEOUT",  "180"))   # 3 min default
# Hard cap: close session after N seconds regardless of activity, with a goodbye.
_MAX_SESSION_SEC   = int(os.environ.get("MIRA_MAX_SESSION",   "1200"))  # 20 min default

# Gemini Live blended pricing (mid-2025). Audio dominates so we use audio rates.
# Swap to TEXT rates if/when text-mode REST routing lands (issue #4).
_COST_PER_M_INPUT  = float(os.environ.get("MIRA_COST_INPUT",  "0.70"))  # $/1M tokens
_COST_PER_M_OUTPUT = float(os.environ.get("MIRA_COST_OUTPUT", "1.50"))  # $/1M tokens

# Lightweight mood read off Mira's own words (keeps the UI lively without a model call).
_EXCITED_HINTS = ("!", "love", "perfect", "gorgeous", "amazing", "obsessed", "yes")
_LOW_HINTS = ("sorry", "tough", "okay", "take your time", "no rush", "here for you")


def _mood_of(text: str) -> str:
    low = text.lower()
    if any(h in low for h in _EXCITED_HINTS):
        return "excited"
    if any(h in low for h in _LOW_HINTS):
        return "low"
    return "neutral"


def _match_products(transcript: str) -> list[dict]:
    """Find catalog items Mira named in this turn, so the UI can show cards.

    In speech Mira paraphrases names ("the Reebok ones", "Bruno Marc slip-ons"), so a
    full-name substring match misses almost everything. Instead we match on each
    product's DISTINCTIVE words — tokens (brand/model/color) that appear in only that
    product across the catalog — which keeps it honest (we only surface what she
    actually referenced) without demanding she recite the exact catalog name. Hits are
    returned in spoken order, de-duplicated. Phase 3 swaps this for structured tool calls.
    """
    low = transcript.lower()
    hits: list[dict] = []
    seen: set[str] = set()
    # Order products by where Mira first mentions them in the transcript.
    ordered = []
    for p in _SPOTLIGHT:
        sig = _DISTINCTIVE.get(p["id"], set())
        present = [w for w in sig if w in low]
        strong = [w for w in present if w not in _GENERIC_TOKENS]
        # A brand/model word is enough; generic-only names need two cues to avoid
        # false positives from ordinary speech ("walking around", "casual dress").
        if not (strong or len(present) >= 2):
            continue
        pos = min(low.find(w) for w in present)
        ordered.append((pos, p))
    for _, p in sorted(ordered, key=lambda t: t[0]):
        if p["id"] in seen:
            continue
        if len(hits) >= 3:  # cap: show 3 products per turn — focused, not overwhelming
            break
        seen.add(p["id"])
        hits.append(
            {
                "id": p["id"],
                "name": p["name"],
                "category": p["category"],
                "color": p["color"],
                "price": p["price"],
                "image_url": p.get("image_url"),
                "affiliate_url": _affiliate_url(p),
            }
        )
    return hits


def _build(memory: str = "", prefs: dict | None = None, taste: str | None = None, event_brief: dict | None = None, location_info: dict | None = None, text_mode: bool = False):
    from google import genai
    from google.genai import types

    if text_mode:
        # Silent/typing mode — respond with text directly; no audio pipeline needed.
        config = types.LiveConnectConfig(
            response_modalities=["TEXT"],
            system_instruction=types.Content(parts=[types.Part(text=full_grounding_prompt(memory, prefs, taste, event_brief, location_info))]),
        )
    else:
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(parts=[types.Part(text=full_grounding_prompt(memory, prefs, taste, event_brief, location_info))]),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=_VOICE)
                )
            ),
            # Resumption handles keep conversation context across Gemini-side reconnects.
            session_resumption=types.SessionResumptionConfig(),
            # Sliding-window compression prevents 1008 abort on long voice sessions.
            context_window_compression=types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow(),
            ),
        )
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY missing — add it to prototype/.env")
    client = genai.Client(api_key=api_key)
    return client, config, types


async def _send_json(ws, **payload) -> None:
    try:
        await ws.send(json.dumps(payload))
    except Exception:
        pass  # connection already closed — silently drop


def _log_session_cost(
    session_id: str,
    user_id: str | None,
    prompt_tokens: int,
    response_tokens: int,
    duration_sec: float,
) -> None:
    """Write per-session cost row to Supabase session_costs table (best-effort)."""
    try:
        cost_usd = (
            prompt_tokens   * _COST_PER_M_INPUT  / 1_000_000 +
            response_tokens * _COST_PER_M_OUTPUT / 1_000_000
        )
        from product_store import _db
        _db().table("session_costs").insert({
            "session_id":       session_id,
            "user_id":          user_id,
            "prompt_tokens":    prompt_tokens,
            "response_tokens":  response_tokens,
            "total_tokens":     prompt_tokens + response_tokens,
            "cost_usd":         round(cost_usd, 6),
            "duration_sec":     round(duration_sec, 1),
        }).execute()
        print(f"  💰 session cost: {prompt_tokens+response_tokens:,} tokens "
              f"≈ ${cost_usd:.4f}  ({duration_sec:.0f}s)")
    except Exception as exc:
        print(f"  ! cost log failed (non-fatal): {exc}")


async def handle(ws) -> None:
    """One browser connection ⇆ a Gemini Live session that auto-reconnects on drop.

    Gemini Live closes the socket on its own session limits (e.g. code 1008). We keep
    the SAME browser connection + session_id and transparently reopen a fresh Live
    session, nudging the avatar to `thinking` while we do.
    """
    _ip = _client_ip(ws, ws.request) if hasattr(ws, "request") else (ws.remote_address[0] if ws.remote_address else "unknown")
    print(f"  ▸ browser connected ({_ip})")

    # Wait for the browser's {type:"init", user_id, name} before opening Gemini so the
    # system prompt can be personalised for this shopper.
    user_id: str | None = None
    user_name = "there"
    text_mode: bool = False   # True → use TEXT modality (silent/typing mode)
    style_vibe: str | None = None
    shopping_focus: str | None = None
    top_size: str | None = None
    bottom_size: str | None = None
    budget: str | None = None
    pin_code: str | None = None
    location_info: dict | None = None
    event_brief: dict = {}
    memory = ""
    taste: str | None = None   # derived from saved products
    chat_session_id: str | None = None
    chat_title: str | None = None  # first user message — set once
    # Declared here (before the init block) so restore_loved can populate it,
    # and pump_mic can read/write it without an UnboundLocalError.
    session_saved: dict[str, str] = {}
    # Tracks every product card sent this session so show_more can page forward.
    session_shown_ids: set[str] = set()
    # When True, pump_mira will only surface saved products (not all matched products).
    show_saved_mode: bool = False
    # Cost tracking — accumulated across all turns this session.
    session_prompt_tokens: int = 0
    session_response_tokens: int = 0
    session_start_time: float = 0.0
    # Idle timeout — updated on every user mic packet or text message.
    last_activity_time: float = 0.0
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
        if isinstance(raw, str):
            data = json.loads(raw)
            if data.get("type") == "init":
                user_id = data.get("user_id")
                user_name = data.get("name") or "there"
                style_vibe     = data.get("style_vibe")
                shopping_focus = data.get("shopping_focus")
                top_size       = data.get("top_size")
                bottom_size    = data.get("bottom_size")
                budget         = data.get("budget")
                pin_code       = data.get("pin_code")
                text_mode      = bool(data.get("text_mode"))
                event_brief    = data.get("event_brief") or {}
                if pin_code and len(pin_code) == 6 and pin_code.isdigit():
                    try:
                        location_info = await asyncio.to_thread(_resolve_pincode_sync, pin_code)
                        if location_info:
                            print(f"  📍 location: {location_info['city']}, {location_info['state']}")
                    except Exception:
                        pass
                if user_id:
                    try:
                        memory, is_returning = await asyncio.to_thread(
                            user_store.load_user, user_id, user_name
                        )
                        label = "↩ returning" if is_returning else "✦ new"
                        print(f"  {label} user: {user_name}")
                        if is_returning:
                            loved_ids = await asyncio.to_thread(
                                user_store.get_loved_ids, user_id
                            )
                            if loved_ids:
                                loved_products = [
                                    {
                                        "id": pid,
                                        "name": p["name"],
                                        "category": p.get("category"),
                                        "color": p.get("color"),
                                        "price": p.get("price"),
                                        "image_url": p.get("image_url"),
                                        "affiliate_url": _affiliate_url(p),
                                    }
                                    for pid in loved_ids
                                    if (p := _BY_ID.get(pid))
                                ]
                                # Pre-populate so Mira knows saved items from first message
                                for pid in loved_ids:
                                    if (p := _BY_ID.get(pid)):
                                        session_saved[pid] = p["name"]
                                # Derive taste profile from saved products
                                taste = _taste_profile(loved_ids)
                                await _send_json(
                                    ws, type="restore_loved",
                                    ids=loved_ids, products=loved_products,
                                )
                    except Exception as exc:
                        print(f"  ! user_store.load_user failed: {exc}")
                # Create a chat session row for history tracking
                if user_id:
                    chat_session_id = await asyncio.to_thread(
                        chat_store.create_session, user_id
                    )
    except (asyncio.TimeoutError, Exception):
        pass  # anonymous session — Mira still works fine

    # Push today's top picks immediately, personalised to the user's prefs.
    prefs = {
        "style_vibe":     style_vibe,
        "shopping_focus": shopping_focus,
        "top_size":       top_size,
        "bottom_size":    bottom_size,
        "budget":         budget,
        "pin_code":       pin_code,
    }
    raw_picks = _personalized_top_picks(prefs, exclude_ids=set(session_saved.keys()), n=3)
    top_picks = []
    for p in raw_picks:
        top_picks.append({
            "id": p["id"], "name": p["name"], "category": p["category"],
            "color": p["color"], "price": p["price"],
            "image_url": p.get("image_url"), "affiliate_url": _affiliate_url(p),
        })
        session_shown_ids.add(p["id"])
    if top_picks:
        await _send_json(ws, type="products", items=top_picks, show_more=True)

    client, config, types = _build(memory, prefs=prefs, taste=taste, event_brief=event_brief, location_info=location_info, text_mode=text_mode)
    session_id = events.new_session_id()
    if event_brief.get("occasion"):
        await asyncio.to_thread(user_store.save_event_brief, user_id, session_id, event_brief)
    current = {"session": None}  # the live session pump_mic forwards audio into
    resume = {"handle": None}    # latest Gemini resumption handle (preserves context)
    stop = asyncio.Event()       # set when the browser disconnects
    # Suppress the echo of the kick-off message from appearing in the "you:" caption.
    suppress_input_transcript = {"once": False}

    async def pump_mic() -> None:
        """Browser mic PCM → whatever Live session is currently open."""
        nonlocal chat_title, session_shown_ids, show_saved_mode
        nonlocal last_activity_time, location_info, prefs
        try:
            async for msg in ws:
                if isinstance(msg, bytes):
                    last_activity_time = asyncio.get_event_loop().time()
                    sess = current["session"]
                    if sess is not None:
                        try:
                            await sess.send_realtime_input(
                                audio=types.Blob(data=msg, mime_type="audio/pcm;rate=16000")
                            )
                        except Exception:
                            pass  # mid-reconnect — drop this frame, mic keeps flowing
                else:
                    last_activity_time = asyncio.get_event_loop().time()
                    data = json.loads(msg)
                    if data.get("type") == "reset":
                        sess = current["session"]
                        if sess is not None:
                            await sess.send_client_content(turns=None, turn_complete=True)
                    elif data.get("type") == "would_buy":
                        pid = data.get("product_id", "")
                        prod = _BY_ID.get(pid, {})
                        events.log_would_buy(
                            pid, session_id=session_id,
                            product_name=prod.get("name"),
                        )
                        if user_id:
                            await asyncio.to_thread(
                                user_store.log_product_event,
                                user_id, pid, prod.get("name", ""), "would_buy",
                            )
                        # Update session memory so Mira knows which items are saved
                        session_saved[pid] = prod.get("name", pid)
                        # Inject silent context into the Gemini session for voice mode
                        # (turn_complete=False queues it without triggering a response)
                        sess = current["session"]
                        if sess is not None and session_saved:
                            names = ", ".join(f'"{n}"' for n in session_saved.values())
                            try:
                                await sess.send_client_content(
                                    turns=[types.Content(
                                        role="user",
                                        parts=[types.Part(
                                            text=f"[CONTEXT: User's saved/wishlist items: {names}]"
                                        )],
                                    )],
                                    turn_complete=False,
                                )
                            except Exception:
                                pass
                        print(f"  ♥ would-buy: {prod.get('name', pid)}")
                    elif data.get("type") == "unlike":
                        pid = data.get("product_id", "")
                        prod = _BY_ID.get(pid, {})
                        if user_id:
                            await asyncio.to_thread(
                                user_store.unlike_product, user_id, pid,
                            )
                        session_saved.pop(pid, None)
                        print(f"  ♡ unlike: {prod.get('name', pid)}")
                    elif data.get("type") == "text_input":
                        text = (data.get("text") or "").strip()
                        if text:
                            # Detect "show my saved/liked/wishlist" intent — push saved
                            # cards directly so _match_products can't mix in unsaved items.
                            _tl = text.lower()
                            _show_saved_intent = (
                                session_saved and
                                any(w in _tl for w in ("saved", "liked", "wishlist", "heart", "favourites", "favorites")) and
                                any(w in _tl for w in ("show", "see", "view", "list", "what", "display", "bring", "tell"))
                            )
                            if _show_saved_intent:
                                show_saved_mode = True
                                saved_items = [_BY_ID[pid] for pid in session_saved if pid in _BY_ID]
                                if saved_items:
                                    await _send_json(ws, type="products",
                                                     items=[{
                                                         "id": p["id"], "name": p["name"],
                                                         "category": p["category"], "color": p["color"],
                                                         "price": p["price"],
                                                         "image_url": p.get("image_url"),
                                                         "affiliate_url": _affiliate_url(p),
                                                     } for p in saved_items],
                                                     show_more=False)
                            else:
                                show_saved_mode = False
                            sess = current["session"]
                            if sess is not None:
                                # Always prepend saved items context so Mira knows
                                # which products the user has saved this session
                                if session_saved:
                                    names = ", ".join(
                                        f'"{n}"' for n in session_saved.values()
                                    )
                                    ctx_prefix = (
                                        f"[CONTEXT: User's saved/wishlist items: {names}]\n"
                                    )
                                else:
                                    ctx_prefix = ""
                                await sess.send_client_content(
                                    turns=[types.Content(
                                        role="user",
                                        parts=[types.Part(text=f"{ctx_prefix}{text}")],
                                    )],
                                    turn_complete=True,
                                )
                            # Echo back as a transcript so the caption shows what was typed
                            await _send_json(ws, type="transcript", who="you", text=text)
                            # Persist to chat history
                            if user_id and chat_session_id:
                                if not chat_title:
                                    chat_title = text[:120]
                                await asyncio.to_thread(
                                    chat_store.save_message,
                                    chat_session_id, user_id, "user", text,
                                )
                    elif data.get("type") == "buy_click":
                        pid = data.get("product_id", "")
                        prod = _BY_ID.get(pid, {})
                        events.log_event(
                            "buy_click", session_id=session_id,
                            product_id=pid, product_name=prod.get("name"),
                        )
                        if user_id and prod:
                            await asyncio.to_thread(
                                user_store.log_product_event,
                                user_id, pid, prod.get("name", ""), "buy_click",
                            )
                        print(f"  buy-click -> retailer: {prod.get('name', pid)}")
                    elif data.get("type") == "update_location":
                        new_pin = (data.get("pin_code") or "").strip()
                        if new_pin and len(new_pin) == 6 and new_pin.isdigit():
                            try:
                                new_loc = await asyncio.to_thread(_resolve_pincode_sync, new_pin)
                                if new_loc:
                                    location_info = new_loc
                                    prefs["pin_code"] = new_pin
                                    city_label = f"{new_loc['city']}, {new_loc['state']}"
                                    print(f"  📍 location updated: {city_label} ({new_pin})")
                                    # Inject silently so Mira knows for the NEXT turn
                                    sess = current["session"]
                                    if sess is not None:
                                        try:
                                            await sess.send_client_content(
                                                turns=[types.Content(
                                                    role="user",
                                                    parts=[types.Part(
                                                        text=f"[CONTEXT: User has updated their delivery location to {city_label} (PIN {new_pin}). "
                                                             f"For any new recommendations, consider products deliverable here and relevant local climate and occasions.]"
                                                    )],
                                                )],
                                                turn_complete=False,
                                            )
                                        except Exception:
                                            pass
                            except Exception as exc:
                                print(f"  ! pin resolve failed: {exc}")
                    elif data.get("type") == "show_more":
                        # Silent page-forward: push next 3 unseen products.
                        cat_filter = data.get("category")  # optional category hint
                        batch = []
                        for p in _CATALOG:
                            if p["id"] in session_shown_ids:
                                continue
                            if cat_filter and p.get("category") != cat_filter:
                                continue
                            batch.append({
                                "id": p["id"],
                                "name": p["name"],
                                "category": p["category"],
                                "color": p["color"],
                                "price": p["price"],
                                "image_url": p.get("image_url"),
                                "affiliate_url": _affiliate_url(p),
                            })
                            if len(batch) >= 3:
                                break
                        if batch:
                            for p in batch:
                                session_shown_ids.add(p["id"])
                            has_more = any(
                                p["id"] not in session_shown_ids
                                for p in _CATALOG
                                if not cat_filter or p.get("category") == cat_filter
                            )
                            await _send_json(ws, type="products", items=batch,
                                             show_more=has_more)
                            print(f"  show_more → pushed {len(batch)} products")
        finally:
            stop.set()  # browser closed → tear the whole conversation down
            if user_id and chat_session_id:
                await asyncio.to_thread(
                    chat_store.end_session, chat_session_id, chat_title
                )

    async def pump_mira(session) -> None:
        """Gemini audio + transcripts → browser, ACROSS many turns on ONE session.

        Critical: `session.receive()` yields one turn's worth of messages and then ends.
        We must loop and call it again on the SAME open session for the next turn — if
        we let the session close after a turn and reopen a fresh one, Gemini loses all
        context and the shopper has to repeat themselves. We only return (→ reconnect)
        when receive() ends WITHOUT a turn_complete, i.e. the session genuinely closed.
        """
        nonlocal show_saved_mode
        nonlocal session_prompt_tokens, session_response_tokens
        mood = "neutral"
        while not stop.is_set():
            talking = False
            said: list[str] = []
            sent_ids: set[str] = set()  # product cards already pushed THIS turn
            turn_ended = False
            async for resp in session.receive():
                # Accumulate token usage for cost tracking.
                if resp.usage_metadata:
                    session_prompt_tokens   += resp.usage_metadata.prompt_token_count   or 0
                    session_response_tokens += resp.usage_metadata.response_token_count or 0
                # Stash the newest resumption handle so a reconnect keeps the conversation.
                update = resp.session_resumption_update
                if update and update.resumable and update.new_handle:
                    resume["handle"] = update.new_handle
                sc = resp.server_content
                # barge-in: server VAD heard the user over Mira.
                if sc and sc.interrupted:
                    talking = False
                    said.clear()
                    sent_ids.clear()
                    await _send_json(ws, type="interrupted")
                    await _send_json(ws, type="state", state="thinking", mood=mood)
                    continue
                # user started speaking → Mira is listening/thinking.
                if sc and sc.input_transcription and sc.input_transcription.text:
                    if suppress_input_transcript["once"]:
                        suppress_input_transcript["once"] = False  # eat the kick-off echo
                    else:
                        await _send_json(
                            ws, type="transcript", who="you",
                            text=sc.input_transcription.text,
                        )
                    if not talking:
                        await _send_json(ws, type="state", state="thinking", mood=mood)
                # Forward Gemini audio bytes directly to the browser so PcmPlayer
                # can play them without needing HeyGen credentials.
                if resp.data:
                    try:
                        await ws.send(bytes(resp.data))
                    except Exception:
                        pass
                # Mira's words → caption + mood read (read off output transcription).
                chunk = ""
                if resp.text:
                    chunk = resp.text
                elif sc and sc.output_transcription and sc.output_transcription.text:
                    chunk = sc.output_transcription.text
                if chunk:
                    if not talking:
                        talking = True
                        await _send_json(ws, type="state", state="talking", mood=mood)
                    said.append(chunk)
                    mood = _mood_of("".join(said))
                    await _send_json(ws, type="transcript", who="mira", text=chunk)
                    # Push each product card the MOMENT she names it, so the screen keeps
                    # pace with her voice instead of all options appearing at the end.
                    # In show_saved_mode we already pushed exact saved cards — skip matching.
                    if not show_saved_mode:
                        fresh = [p for p in _match_products("".join(said)) if p["id"] not in sent_ids]
                        if fresh:
                            for p in fresh:
                                sent_ids.add(p["id"])
                                session_shown_ids.add(p["id"])
                                if user_id:
                                    await asyncio.to_thread(
                                        user_store.log_product_event,
                                        user_id, p["id"], p["name"], "shown",
                                    )
                            await _send_json(ws, type="products", items=fresh, show_more=True)
                # turn done → brief react, then back to idle. Break to await the NEXT
                # turn on this same session (keeps context alive).
                if sc and sc.turn_complete:
                    _was_saved_mode = show_saved_mode
                    show_saved_mode = False  # reset after each turn
                    if not _was_saved_mode:
                        fresh = [p for p in _match_products("".join(said)) if p["id"] not in sent_ids]
                        if fresh:
                            for p in fresh:
                                session_shown_ids.add(p["id"])
                            await _send_json(ws, type="products", items=fresh, show_more=True)
                    # Full turn text → browser tells LiveAvatar to speak it.
                    full = "".join(said).strip()
                    if full:
                        await _send_json(ws, type="mira_text", text=full)
                        # Persist Mira's complete turn to chat history
                        if user_id and chat_session_id:
                            await asyncio.to_thread(
                                chat_store.save_message,
                                chat_session_id, user_id, "mira", full,
                            )
                    await _send_json(ws, type="state", state="reacting", mood=mood)
                    await asyncio.sleep(0.9)
                    await _send_json(ws, type="state", state="idle", mood="neutral")
                    mood = "neutral"
                    turn_ended = True
                    break
            if not turn_ended:
                return  # receive() ended without a turn → session really closed; reconnect

    async def _watchdog(session) -> None:
        """Close idle or over-time sessions to prevent runaway Gemini billing."""
        nonlocal last_activity_time, session_start_time
        while not stop.is_set():
            await asyncio.sleep(30)
            now = asyncio.get_event_loop().time()
            idle_sec  = now - last_activity_time
            total_sec = now - session_start_time
            if idle_sec >= _IDLE_TIMEOUT_SEC:
                print(f"  ⏱ idle {idle_sec:.0f}s — closing session to save cost")
                try:
                    await session.send_client_content(
                        turns=[types.Content(role="user", parts=[types.Part(
                            text="[SYSTEM] Session timed out due to inactivity. "
                                 "Say a brief, warm goodbye (one sentence) and end the session."
                        )])],
                        turn_complete=True,
                    )
                    await asyncio.sleep(4)
                except Exception:
                    pass
                stop.set()
                return
            if total_sec >= _MAX_SESSION_SEC:
                print(f"  ⏱ max session length {total_sec:.0f}s reached — closing")
                try:
                    await session.send_client_content(
                        turns=[types.Content(role="user", parts=[types.Part(
                            text="[SYSTEM] Maximum session length reached. "
                                 "Tell the user warmly that you've reached today's chat limit "
                                 "and they can start a new session anytime. One sentence."
                        )])],
                        turn_complete=True,
                    )
                    await asyncio.sleep(4)
                except Exception:
                    pass
                stop.set()
                return

    async def run_live() -> None:
        """Open Live sessions, reconnecting with backoff until the browser leaves."""
        nonlocal session_start_time, last_activity_time
        backoff = 0.5
        first = True
        while not stop.is_set():
            try:
                # Replay the latest handle so the reopened session resumes context.
                config.session_resumption = types.SessionResumptionConfig(
                    handle=resume["handle"]
                )
                t0 = asyncio.get_event_loop().time()
                async with client.aio.live.connect(model=_MODEL, config=config) as session:
                    current["session"] = session
                    backoff = 0.5
                    if not first:
                        print("  ↻ Live session reconnected")
                    else:
                        session_start_time  = t0
                        last_activity_time  = t0
                        if event_brief.get("occasion"):
                            looks = build_looks(
                                _CATALOG,
                                occasion=event_brief["occasion"],
                                vibe=event_brief.get("vibe", ""),
                                budget_max=event_brief.get("budget_max"),
                            )
                            if looks:
                                await _send_json(ws, type="looks", items=looks)
                        # Kick off Mira's opening greeting on first connect.
                        # We suppress the input transcription echo so "hi" doesn't
                        # appear in the "you:" caption.
                        suppress_input_transcript["once"] = True
                        # Build a rich profile summary for Mira's context
                        has_prefs = any([style_vibe, shopping_focus, top_size, budget])
                        profile_parts = []
                        if style_vibe:     profile_parts.append(f"style: {style_vibe}")
                        if shopping_focus: profile_parts.append(f"shops for: {shopping_focus}")
                        if top_size:       profile_parts.append(f"top size: {top_size}")
                        if bottom_size:    profile_parts.append(f"bottom size: {bottom_size}")
                        if budget:         profile_parts.append(f"budget: {budget}")
                        profile_str = ", ".join(profile_parts)

                        if event_brief.get("occasion"):
                            greeting_instruction = (
                                f"[START SESSION] Greet {user_name} warmly by name and acknowledge "
                                f"their {event_brief['occasion']} event brief. Three grounded look "
                                f"drafts are already visible. Ask ONE concise question only if needed "
                                f"to refine the looks; otherwise invite them to compare the drafts. "
                                f"Keep it to 2 sentences. Do NOT say you are great."
                            )
                        elif has_prefs:
                            greeting_instruction = (
                                f"[START SESSION] Greet {user_name} warmly by name. "
                                f"Their saved style profile is: {profile_str}. "
                                f"In your greeting: say hi, briefly confirm their profile in a natural "
                                f"way (e.g. 'Still going for that minimal everyday look?'), "
                                f"and ask if they want to keep it or try something different today. "
                                f"Keep it to 2–3 sentences. Sound like a friend, not a form. "
                                f"Do NOT say 'I'm great' or respond as if they greeted you."
                            )
                        else:
                            greeting_instruction = (
                                f"[START SESSION] Greet {user_name} warmly by name. "
                                f"You don't know their style preferences yet. "
                                f"Say hi, then ask ONE natural question to understand what they're "
                                f"looking for — their style, an occasion, or what they need. "
                                f"Keep it to 2 sentences max. Sound curious and friendly. "
                                f"Do NOT say 'I'm great' or respond as if they greeted you."
                            )
                        await session.send_client_content(
                            turns=[types.Content(
                                role="user",
                                parts=[types.Part(text=greeting_instruction)],
                            )],
                            turn_complete=True,
                        )
                    first = False
                    await _send_json(ws, type="state", state="idle", mood="neutral")
                    await asyncio.gather(
                        pump_mira(session),
                        _watchdog(session),
                    )
                # Clean end: log cost, then decide whether to reconnect or stop.
                dur = asyncio.get_event_loop().time() - t0
                print(f"  · Live session ended cleanly after {dur:.1f}s")
                await asyncio.to_thread(
                    _log_session_cost,
                    session_id, user_id,
                    session_prompt_tokens, session_response_tokens, dur,
                )
            except websockets.ConnectionClosed:
                break  # browser gone
            except Exception as exc:
                dur = asyncio.get_event_loop().time() - t0
                print(f"  ! Live session dropped after {dur:.1f}s ({exc}) — reconnecting")
                await asyncio.to_thread(
                    _log_session_cost,
                    session_id, user_id,
                    session_prompt_tokens, session_response_tokens, dur,
                )
            finally:
                current["session"] = None
            if stop.is_set():
                break
            try:  # reassure the UI while we reopen
                await _send_json(ws, type="state", state="thinking", mood="neutral")
            except Exception:
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 4.0)

    try:
        await asyncio.gather(pump_mic(), run_live())
    except websockets.ConnectionClosed:
        pass
    finally:
        await _rl_release(_ip)
        print(f"  ▸ browser disconnected ({_ip})")


def _mint_avatar_token() -> dict:
    """Server-side mint a LiveAvatar LITE session token so the API key never reaches
    the browser. LITE mode = we bring the brain (Gemini) and just tell the avatar what
    to say (session.repeat(text)); LiveAvatar renders the synchronized video.
    The browser fetches this via /avatar-token (Vite-proxied)."""
    import urllib.request

    key = os.environ.get("HEYGEN_API_KEY") or os.environ.get("LIVEAVATAR_API_KEY")
    if not key:
        raise RuntimeError("LiveAvatar API key missing — add HEYGEN_API_KEY to prototype/.env")
    # Sandbox lets you test the full pipeline WITHOUT consuming credits (sessions auto-end
    # after ~1 min). Only the Wayne avatar is allowed in sandbox. Set LIVEAVATAR_SANDBOX=1.
    sandbox = os.environ.get("LIVEAVATAR_SANDBOX", "").lower() in ("1", "true", "yes")
    avatar_id = os.environ.get(
        "LIVEAVATAR_AVATAR_ID",
        "dd73ea75-1218-4ef3-92ce-606d5f7fbc0a" if sandbox else "513fd1b7-7ef9-466d-9af2-344e51eeb833",
    )
    body = json.dumps({"mode": "LITE", "avatar_id": avatar_id, "is_sandbox": sandbox}).encode()
    req = urllib.request.Request(
        "https://api.liveavatar.com/v1/sessions/token",
        method="POST",
        headers={
            "X-API-KEY": key,
            "content-type": "application/json",
            # Some edges (Cloudflare) 403 the default python-urllib UA.
            "User-Agent": "mira-bridge/1.0",
            "Accept": "application/json",
        },
        data=body,
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read()).get("data", {})
    return {"token": data.get("session_token"), "session_id": data.get("session_id")}


# ── Per-IP rate limiting ──────────────────────────────────────────────────────
_RL_MAX_CONCURRENT = int(os.environ.get("MIRA_MAX_CONCURRENT_PER_IP", "3"))
_RL_MAX_PER_HOUR   = int(os.environ.get("MIRA_MAX_STARTS_PER_HOUR",   "10"))

_rl_active: dict[str, int]        = {}   # ip → active session count
_rl_starts: dict[str, list[float]] = {}  # ip → list of start timestamps this hour
_rl_lock = asyncio.Lock()


def _client_ip(connection, request) -> str:
    """Real client IP — reads X-Real-IP forwarded by nginx, falls back to TCP address."""
    forwarded = request.headers.get("X-Real-IP") or request.headers.get("X-Forwarded-For", "")
    ip = forwarded.split(",")[0].strip()
    return ip or (connection.remote_address[0] if connection.remote_address else "unknown")


async def _rl_acquire(ip: str) -> str | None:
    """Return None if request is allowed; error message string if rate-limited."""
    async with _rl_lock:
        now = time.monotonic()
        cutoff = now - 3600
        starts = [t for t in _rl_starts.get(ip, []) if t > cutoff]
        _rl_starts[ip] = starts
        active = _rl_active.get(ip, 0)
        if active >= _RL_MAX_CONCURRENT:
            return "Too many active sessions from your device — close another tab and try again."
        if len(starts) >= _RL_MAX_PER_HOUR:
            return "Too many sessions this hour — take a break and try again shortly."
        _rl_active[ip] = active + 1
        _rl_starts[ip].append(now)
        return None


async def _rl_release(ip: str) -> None:
    async with _rl_lock:
        _rl_active[ip] = max(0, _rl_active.get(ip, 1) - 1)


async def process_request(connection, request):
    """Serve the LiveAvatar session token over plain HTTP; everything else upgrades to WS."""
    if request.path.rstrip("/") == "/avatar-token":
        try:
            payload = await asyncio.to_thread(_mint_avatar_token)
            resp = connection.respond(200, json.dumps(payload))
            resp.headers["Content-Type"] = "application/json"
            resp.headers["Access-Control-Allow-Origin"] = "*"
            return resp
        except Exception as exc:
            return connection.respond(500, json.dumps({"error": str(exc)}))
    # Return 200 for plain HTTP health checks (no WebSocket upgrade headers).
    if request.headers.get("Upgrade", "").lower() != "websocket":
        return connection.respond(200, "OK")

    # Rate-limit WebSocket upgrades.
    ip = _client_ip(connection, request)
    err = await _rl_acquire(ip)
    if err:
        print(f"  ⛔ rate limit [{ip}]: {err}")
        resp = connection.respond(429, json.dumps({"type": "error", "message": err}))
        resp.headers["Content-Type"] = "application/json"
        return resp

    return None


async def main() -> None:
    print(f"  Mira voice bridge → ws://{_HOST}:{_PORT}")
    print(f"  model={_MODEL}  (LiveAvatar renders Mira)")
    async with serve(handle, _HOST, _PORT, max_size=None, process_request=process_request):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  bye 👋")
