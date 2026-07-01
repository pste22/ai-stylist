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

from dotenv import load_dotenv

# Load THIS package's .env (prototype/.env) regardless of the process CWD, so keys are
# found whether the bridge is launched from the repo root or from prototype/.
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

import websockets
from websockets.asyncio.server import serve

import events  # noqa: E402
from stylist import SYSTEM_PROMPT  # noqa: E402  (the SAME persona + grounding rules)
from product_source import get_source  # noqa: E402

# Ground the voice on the ACTIVE source (env PRODUCT_SOURCE: local / curated / amazon),
# not just the bundled demo catalog — so curated SiteStripe / PA-API items Mira can
# actually earn on flow straight into the spoken conversation. See docs/10-sourcing.
_SOURCE = get_source()
_CATALOG = _SOURCE.search(limit=50)
# Index by id so we can match Mira's spoken recommendations.
_BY_ID = {p["id"]: p for p in _CATALOG}


def full_grounding_prompt() -> str:
    """Persona + the active source's catalog as one grounding block."""
    return f"{SYSTEM_PROMPT}\n\nPRODUCTS you may recommend:\n{_SOURCE.render(_CATALOG)}"


# Per-product "signature" tokens for spoken-name matching (see _match_products): the
# words in a product's name/color that are UNIQUE to it across the catalog. Generic
# fashion words shared by several items (e.g. "sneakers", "slip-on") are dropped so they
# can't cause false matches; brand/model/color words (e.g. "reebok", "bruno") remain.
def _build_distinctive() -> dict[str, set[str]]:
    def toks(s: str) -> set[str]:
        return {w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(w) > 2}

    name_tokens = {p["id"]: toks(p["name"]) | toks(p.get("color", "")) for p in _CATALOG}
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
    "sneakers", "shoes", "shoe", "slip", "slipon", "casual", "walking", "running",
    "lightweight", "comfort", "athletic", "sporty", "minimal", "everyday", "dress",
    "top", "tops", "jacket", "coat", "jeans", "pants", "boots", "black", "white",
    "gray", "grey", "navy", "blue", "red", "green", "brown", "tan", "beige",
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
    for p in _CATALOG:
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


def _build():
    from google import genai
    from google.genai import types

    config = types.LiveConnectConfig(
        # This model is audio-only (TEXT modality → 1007). We keep AUDIO out but DON'T
        # play it — instead we read Mira's words off output_transcription and forward the
        # full turn text to the browser, which tells LiveAvatar to speak it (LITE mode,
        # session.repeat(text)). LiveAvatar's avatar voice does the TTS + lip-sync.
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part(text=full_grounding_prompt())]),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=_VOICE)
            )
        ),
        # Ask the server to emit resumption handles so we can reopen a DROPPED Live
        # session with its conversation context intact (Gemini closes sessions on its
        # own limits, e.g. 1008). Without this, every reconnect = amnesia — Mira forgets
        # what the shopper just said (e.g. "sneakers"). The handle is replayed in run_live.
        session_resumption=types.SessionResumptionConfig(),
        # Keep long voice chats alive. A continuous audio session fills the context
        # window fast; once it's full Gemini aborts the socket (1008 "operation was
        # aborted") — the frequent mid-conversation drops we saw. A sliding-window
        # compression lets the session run indefinitely instead of being cut off.
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
    await ws.send(json.dumps(payload))


async def handle(ws) -> None:
    """One browser connection ⇆ a Gemini Live session that auto-reconnects on drop.

    Gemini Live closes the socket on its own session limits (e.g. code 1008). We keep
    the SAME browser connection + session_id and transparently reopen a fresh Live
    session, nudging the avatar to `thinking` while we do. (Note: Live context resets
    on reconnect — the shopper just keeps talking; cross-turn memory lands in Phase 4.)
    """
    print(f"  ▸ browser connected ({ws.remote_address})")
    client, config, types = _build()
    session_id = events.new_session_id()
    current = {"session": None}  # the live session pump_mic forwards audio into
    resume = {"handle": None}    # latest Gemini resumption handle (preserves context)
    stop = asyncio.Event()       # set when the browser disconnects

    async def pump_mic() -> None:
        """Browser mic PCM → whatever Live session is currently open."""
        try:
            async for msg in ws:
                if isinstance(msg, bytes):
                    sess = current["session"]
                    if sess is not None:
                        try:
                            await sess.send_realtime_input(
                                audio=types.Blob(data=msg, mime_type="audio/pcm;rate=16000")
                            )
                        except Exception:
                            pass  # mid-reconnect — drop this frame, mic keeps flowing
                else:
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
                        print(f"  ♥ would-buy: {prod.get('name', pid)}")
                    elif data.get("type") == "buy_click":
                        pid = data.get("product_id", "")
                        prod = _BY_ID.get(pid, {})
                        events.log_event(
                            "buy_click", session_id=session_id,
                            product_id=pid, product_name=prod.get("name"),
                        )
                        print(f"  buy-click -> retailer: {prod.get('name', pid)}")
        finally:
            stop.set()  # browser closed → tear the whole conversation down

    async def pump_mira(session) -> None:
        """Gemini audio + transcripts → browser, ACROSS many turns on ONE session.

        Critical: `session.receive()` yields one turn's worth of messages and then ends.
        We must loop and call it again on the SAME open session for the next turn — if
        we let the session close after a turn and reopen a fresh one, Gemini loses all
        context and the shopper has to repeat themselves. We only return (→ reconnect)
        when receive() ends WITHOUT a turn_complete, i.e. the session genuinely closed.
        """
        mood = "neutral"
        while not stop.is_set():
            talking = False
            said: list[str] = []
            sent_ids: set[str] = set()  # product cards already pushed THIS turn
            turn_ended = False
            async for resp in session.receive():
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
                    fresh = [p for p in _match_products("".join(said)) if p["id"] not in sent_ids]
                    if fresh:
                        for p in fresh:
                            sent_ids.add(p["id"])
                        await _send_json(ws, type="products", items=fresh)
                # turn done → brief react, then back to idle. Break to await the NEXT
                # turn on this same session (keeps context alive).
                if sc and sc.turn_complete:
                    fresh = [p for p in _match_products("".join(said)) if p["id"] not in sent_ids]
                    if fresh:
                        await _send_json(ws, type="products", items=fresh)
                    # Full turn text → browser tells LiveAvatar to speak it.
                    full = "".join(said).strip()
                    if full:
                        await _send_json(ws, type="mira_text", text=full)
                    await _send_json(ws, type="state", state="reacting", mood=mood)
                    await asyncio.sleep(0.9)
                    await _send_json(ws, type="state", state="idle", mood="neutral")
                    mood = "neutral"
                    turn_ended = True
                    break
            if not turn_ended:
                return  # receive() ended without a turn → session really closed; reconnect

    async def run_live() -> None:
        """Open Live sessions, reconnecting with backoff until the browser leaves."""
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
                    first = False
                    await _send_json(ws, type="state", state="idle", mood="neutral")
                    await pump_mira(session)  # runs until the session ends/drops
                # Clean end (no exception): the server closed the stream itself.
                print(f"  · Live session ended cleanly after {asyncio.get_event_loop().time() - t0:.1f}s")
            except websockets.ConnectionClosed:
                break  # browser gone
            except Exception as exc:
                dur = asyncio.get_event_loop().time() - t0
                print(f"  ! Live session dropped after {dur:.1f}s ({exc}) — reconnecting")
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
        print("  ▸ browser disconnected")


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
