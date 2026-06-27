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
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import websockets
from websockets.asyncio.server import serve

# Reuse the SAME persona + full-catalog grounding the spike validated.
sys.path.insert(0, str(Path(__file__).resolve().parent / "spikes"))
from common import full_grounding_prompt  # noqa: E402

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
    """One browser connection ⇆ one Gemini Live session."""
    print(f"  ▸ browser connected ({ws.remote_address})")
    client, config, types = _build()

    try:
        async with client.aio.live.connect(model=_MODEL, config=config) as session:
            await _send_json(ws, type="state", state="idle", mood="neutral")

            async def pump_mic() -> None:
                """Browser mic PCM → Gemini realtime input."""
                async for msg in ws:
                    if isinstance(msg, bytes):
                        await session.send_realtime_input(
                            audio=types.Blob(data=msg, mime_type="audio/pcm;rate=16000")
                        )
                    else:
                        data = json.loads(msg)
                        if data.get("type") == "reset":
                            await session.send_client_content(turns=None, turn_complete=True)

            async def pump_mira() -> None:
                """Gemini audio + transcripts → browser, with avatar-state events."""
                talking = False
                mood = "neutral"
                said: list[str] = []
                while True:
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
                            await _send_json(ws, type="state", state="reacting", mood=mood)
                            await asyncio.sleep(0.9)
                            await _send_json(ws, type="state", state="idle", mood="neutral")
                            talking = False
                            said.clear()
                            mood = "neutral"

            await asyncio.gather(pump_mic(), pump_mira())
    except websockets.ConnectionClosed:
        print("  ▸ browser disconnected")
    except Exception as exc:  # keep the server alive across session errors
        print(f"  ! session error: {exc}")
        try:
            await _send_json(ws, type="error", message=str(exc))
        except Exception:
            pass


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
