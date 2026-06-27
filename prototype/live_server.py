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

from dotenv import load_dotenv

load_dotenv()

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

    Name-substring match keeps it honest: we only surface what she actually said,
    in spoken order, de-duplicated. Phase 3 swaps this for structured tool calls.
    """
    low = transcript.lower()
    hits: list[dict] = []
    seen: set[str] = set()
    for p in _CATALOG:
        if p["name"].lower() in low and p["id"] not in seen:
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
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part(text=full_grounding_prompt())]),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=_VOICE)
            )
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
        """Gemini audio + transcripts → browser. Returns/raises when the session ends."""
        talking = False
        mood = "neutral"
        said: list[str] = []
        async for resp in session.receive():
            sc = resp.server_content
            # barge-in: server VAD heard the user over Mira.
            if sc and sc.interrupted:
                talking = False
                said.clear()
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
            # first audio chunk of a reply → talking.
            if resp.data:
                if not talking:
                    talking = True
                    await _send_json(ws, type="state", state="talking", mood=mood)
                await ws.send(resp.data)
            # Mira's words → caption + mood read.
            if sc and sc.output_transcription and sc.output_transcription.text:
                chunk = sc.output_transcription.text
                said.append(chunk)
                mood = _mood_of("".join(said))
                await _send_json(ws, type="transcript", who="mira", text=chunk)
            # turn done → brief react, then back to idle.
            if sc and sc.turn_complete:
                full = "".join(said)
                products = _match_products(full)
                if products:
                    await _send_json(ws, type="products", items=products)
                await _send_json(ws, type="state", state="reacting", mood=mood)
                await asyncio.sleep(0.9)
                await _send_json(ws, type="state", state="idle", mood="neutral")
                talking = False
                said.clear()
                mood = "neutral"

    async def run_live() -> None:
        """Open Live sessions, reconnecting with backoff until the browser leaves."""
        backoff = 0.5
        first = True
        while not stop.is_set():
            try:
                async with client.aio.live.connect(model=_MODEL, config=config) as session:
                    current["session"] = session
                    backoff = 0.5
                    if not first:
                        print("  ↻ Live session reconnected")
                    first = False
                    await _send_json(ws, type="state", state="idle", mood="neutral")
                    await pump_mira(session)  # runs until the session ends/drops
            except websockets.ConnectionClosed:
                break  # browser gone
            except Exception as exc:
                print(f"  ! Live session dropped ({exc}) — reconnecting")
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


async def main() -> None:
    print(f"  Mira voice bridge → ws://{_HOST}:{_PORT}")
    print(f"  model={_MODEL}  voice={_VOICE}")
    async with serve(handle, _HOST, _PORT, max_size=None):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  bye 👋")
