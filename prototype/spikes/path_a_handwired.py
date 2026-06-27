"""S1 Path A — hand-wired voice loop: mic -> faster-whisper -> Groq -> Piper.

THROWAWAY spike code. We already know the LLM half is ~404ms first token on Groq
(see docs/02-risks.md), so this run mostly measures the STT + TTS overhead on top,
plus whether we can do barge-in ourselves.

The brain (persona + grounded recommendations) is the REAL Stylist from stylist.py,
so grounding here is whatever we already ship. Only the audio I/O is hand-wired.

Run:  python spikes/path_a_handwired.py
Needs: pip install -r spikes/requirements-spike.txt  +  GROQ_API_KEY in .env
"""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from common import scorecard  # noqa: E402
from stylist import Stylist  # noqa: E402  (real brain: persona + catalog grounding)


def main() -> None:
    brain = Stylist()  # raises clearly if GROQ_API_KEY is missing

    with scorecard("A — hand-wired (Whisper + Groq + Piper)") as sw:
        # ── The three pieces you hand-wire live for the spike ──
        #
        # 1. STT  — faster-whisper streaming:
        #      from faster_whisper import WhisperModel
        #      stt = WhisperModel("base.en", device="cpu", compute_type="int8")
        #      Capture mic via sounddevice, run VAD, transcribe on end-of-utterance.
        #
        # 2. BRAIN — already done, just stream tokens into the TTS:
        #      for token in brain.reply_stream(user_text): ...
        #
        # 3. TTS  — Piper streaming; play audio as chunks arrive:
        #      from piper import PiperVoice  (synthesize per sentence, stream to speaker)
        #
        # Barge-in: run mic VAD on a background thread; if speech detected while Piper
        # is playing, stop playback immediately and start a new STT turn.
        #
        # Timing per turn:
        #      sw.start_turn()     # the moment the user stops speaking
        #      ... STT -> brain -> first TTS audio sample ...
        #      sw.first_audio()    # the moment the first audio plays
        #
        # TODO(spike): wire the mic/STT/TTS above. Until then, run the brain headless
        # so the latency harness is exercised end-to-end with the real model:
        for user_text in __import__("common").SCRIPT:
            print(f"\n  you ▸ {user_text}")
            sw.start_turn()
            print("  mira ▸ ", end="", flush=True)
            first = True
            for token in brain.reply_stream(user_text):
                if first:
                    sw.first_audio()  # stand-in: first TOKEN ~= first audio (no TTS yet)
                    first = False
                print(token, end="", flush=True)
            print()


if __name__ == "__main__":
    main()
