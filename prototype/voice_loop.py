"""Phase 1 VOICE loop — scaffold (tasks P1-2 / P1-4 / P1-5 on the board).

This is intentionally a SKELETON. The text loop (text_loop.py) proves the brain
and LLM latency first. This file shows where the streaming voice pieces plug in so
the jump to real-time audio is incremental, not a rewrite.

Plan:
  mic ─▶ VAD ─▶ streaming STT (faster-whisper) ─▶ Stylist.reply_stream (Groq)
       ─▶ streaming TTS (Piper) ─▶ speaker, with barge-in (interruption) support.

Recommended path: use Pipecat to orchestrate the pipeline + LiveKit for WebRTC
transport (see docs/05-tech-stack.md). Pseudocode below outlines the wiring.

To start this task:
    pip install pipecat-ai faster-whisper piper-tts
"""
from __future__ import annotations


def main() -> None:
    raise NotImplementedError(
        "Voice loop is the next board task (P1-2/P1-4/P1-5).\n"
        "Run `python text_loop.py` first to validate the brain + latency.\n\n"
        "Wiring sketch:\n"
        "  1. Capture mic audio + voice-activity detection (VAD).\n"
        "  2. Stream audio to faster-whisper -> partial transcripts.\n"
        "  3. On end-of-utterance, call Stylist.reply_stream(text).\n"
        "  4. Feed token stream into Piper TTS, play audio as it generates.\n"
        "  5. If the user starts talking, stop playback (barge-in).\n"
        "  6. Orchestrate 1-5 with Pipecat; transport via LiveKit WebRTC."
    )


if __name__ == "__main__":
    main()
