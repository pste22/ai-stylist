"""S1 Path B — Gemini Live (single bidirectional STT+LLM+TTS stream).

THROWAWAY spike code. Answers THREE things fast:
  1. Latency  — time from sending an utterance to the FIRST audio chunk back (< 1s gate).
  2. Grounding— can the system prompt force Mira to ONLY recommend catalog items?
                #3 ("white sneakers") should work; #4 ("Nike Air Max") must be refused.
  3. Warmth   — does Mira's voice feel like it could be the brand? (judge the WAVs).

Two modes:
  * text  (DEFAULT) — drives the Live session with the 6 scripted lines as TEXT input.
                      Deterministic + reproducible: clean latency numbers, saves each
                      reply to a .wav, and captures the transcript to check grounding.
                      No mic needed. Run this for latency + grounding + warmth.
  * mic            — live microphone, for the ONE thing text can't test: barge-in.
                      Speak the lines; interrupt Mira mid-reply on #5.

Same persona + full catalog (common.full_grounding_prompt) as Path A — only the
pipeline differs.

Run:  python spikes/path_b_gemini_live.py            # text mode (default)
      python spikes/path_b_gemini_live.py mic        # barge-in test
Needs: pip install -r spikes/requirements-spike.txt  +  GEMINI_API_KEY in .env
"""
from __future__ import annotations

import asyncio
import os
import sys
import wave
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from common import SCRIPT, full_grounding_prompt, print_script, scorecard  # noqa: E402

# Native-audio realtime model. Override via GEMINI_LIVE_MODEL.
# (Run models.list() and look for bidiGenerateContent support to see current options.)
# NOTE (spike S1): the native-audio models "think" before speaking (~2.5s to first audio,
# fails the <1s gate). The half-cascade flash-live models skip that and hit ~650ms. Default
# to the fast one; switch back to native-audio only if its voice warmth is worth the latency.
_MODEL = os.environ.get("GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview")
_VOICE = os.environ.get("GEMINI_LIVE_VOICE", "Aoede")

_IN_RATE = 16_000   # mic input
_OUT_RATE = 24_000  # model audio output
_CHUNK = 512
_OUT_DIR = Path(__file__).parent / "_recordings"


def _build(api_key: str):
    from google import genai
    from google.genai import types

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(
            parts=[types.Part(text=full_grounding_prompt())]  # grounding lives here
        ),
        # Ask for a text transcript of Mira's audio so we can VERIFY grounding.
        output_audio_transcription=types.AudioTranscriptionConfig(),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=_VOICE)
            )
        ),
    )
    client = genai.Client(api_key=api_key)
    return client, config, types


def _save_wav(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # int16
        w.setframerate(_OUT_RATE)
        w.writeframes(pcm)


# ---------------------------------------------------------------------------
# TEXT MODE — deterministic latency + grounding + warmth (no mic)
# ---------------------------------------------------------------------------
async def run_text(api_key: str) -> None:
    client, config, _ = _build(api_key)
    _OUT_DIR.mkdir(exist_ok=True)

    with scorecard(f"B — Gemini Live · TEXT drive · voice={_VOICE}") as sw:
        async with client.aio.live.connect(model=_MODEL, config=config) as session:
            print("\n  🤖 Connected. Driving with the 6 scripted lines as text.\n")
            for i, line in enumerate(SCRIPT, 1):
                print(f"  you ▸ {line}")
                sw.start_turn()
                await session.send_client_content(
                    turns={"role": "user", "parts": [{"text": line}]},
                    turn_complete=True,
                )
                pcm = bytearray()
                transcript: list[str] = []
                first = True
                async for resp in session.receive():
                    if resp.data:
                        if first:
                            sw.first_audio()
                            first = False
                        pcm.extend(resp.data)
                    sc = resp.server_content
                    if sc and sc.output_transcription and sc.output_transcription.text:
                        transcript.append(sc.output_transcription.text)
                    if sc and sc.turn_complete:
                        break
                said = "".join(transcript).strip()
                if said:
                    print(f"  mira ▸ {said}")
                if pcm:
                    out = _OUT_DIR / f"turn{i}_{_VOICE}.wav"
                    _save_wav(out, bytes(pcm))
                    print(f"        🔊 saved {out.name} ({len(pcm) // 2 / _OUT_RATE:.1f}s)")
                print()
        print(f"  Recordings in: {_OUT_DIR}  (listen to judge warmth)")


# ---------------------------------------------------------------------------
# MIC MODE — the one thing text can't test: barge-in
# ---------------------------------------------------------------------------
async def run_mic(api_key: str) -> None:
    import numpy as np
    import sounddevice as sd

    # Full-duplex (true barge-in) only works with HEADPHONES — otherwise Mira's
    # voice echoes into the mic and the server VAD interrupts her endlessly.
    # Default is HALF-DUPLEX: mute the mic while Mira speaks -> clean turn-taking
    # on open speakers. Set FULL_DUPLEX=1 (with headphones) to test real barge-in.
    full_duplex = os.environ.get("FULL_DUPLEX") == "1"

    client, config, types = _build(api_key)
    loop = asyncio.get_running_loop()
    mic_q: asyncio.Queue[bytes] = asyncio.Queue()
    play_q: asyncio.Queue[bytes] = asyncio.Queue()
    mira_speaking = asyncio.Event()  # set while Mira's audio is playing

    def on_mic(indata, frames, t, status) -> None:
        # Half-duplex: drop mic audio while Mira talks so her echo can't self-interrupt.
        if not full_duplex and mira_speaking.is_set():
            return
        loop.call_soon_threadsafe(mic_q.put_nowait, bytes(indata))

    mic = sd.RawInputStream(samplerate=_IN_RATE, channels=1, dtype="int16",
                            blocksize=_CHUNK, callback=on_mic)
    speaker = sd.RawOutputStream(samplerate=_OUT_RATE, channels=1, dtype="int16")

    print_script()
    mode = "FULL-DUPLEX (barge-in on)" if full_duplex else "HALF-DUPLEX (turn-taking)"
    print(f"\n  🎙️  MIC mode — {mode}. Speak the lines. Ctrl-C to stop.")
    if full_duplex:
        print("  ⚠️  Full-duplex needs HEADPHONES or Mira will interrupt herself.\n")
    else:
        print("  ℹ️  Mic mutes while Mira speaks (no echo). For real barge-in:")
        print("      put headphones on and run with FULL_DUPLEX=1.\n")

    async with client.aio.live.connect(model=_MODEL, config=config) as session:
        mic.start()
        speaker.start()

        async def send_mic() -> None:
            while True:
                chunk = await mic_q.get()
                await session.send_realtime_input(
                    audio=types.Blob(data=chunk, mime_type="audio/pcm;rate=16000")
                )

        async def player() -> None:
            while True:
                chunk = await play_q.get()
                mira_speaking.set()
                await loop.run_in_executor(None, speaker.write,
                                           np.frombuffer(chunk, dtype="int16"))
                if play_q.empty():
                    mira_speaking.clear()  # Mira finished -> mic reopens

        async def recv() -> None:
            while True:
                async for resp in session.receive():
                    sc = resp.server_content
                    if sc and sc.interrupted:
                        print("  ⏸  barge-in (server VAD) — flushing playback")
                        while not play_q.empty():
                            play_q.get_nowait()
                        mira_speaking.clear()
                        continue
                    if resp.data:
                        play_q.put_nowait(resp.data)

        try:
            await asyncio.gather(send_mic(), player(), recv())
        finally:
            mic.stop()
            speaker.stop()


def main() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit(
            "GEMINI_API_KEY is not set. Add it to .env (do NOT paste it in chat)."
        )
    try:
        import google.genai  # noqa: F401
    except ImportError:
        raise SystemExit("Run: pip install -r spikes/requirements-spike.txt")

    mode = sys.argv[1] if len(sys.argv) > 1 else "text"
    try:
        if mode == "mic":
            asyncio.run(run_mic(api_key))
        else:
            asyncio.run(run_text(api_key))
    except KeyboardInterrupt:
        print("\n  stopped.", file=sys.stderr)


if __name__ == "__main__":
    main()
