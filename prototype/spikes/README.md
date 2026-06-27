# Spike S1 — throwaway scripts

Scratch code for [docs/spikes/S1-gemini-live-spike.md](../../docs/spikes/S1-gemini-live-spike.md).
**This is throwaway.** Do not import any of it into the main loop. If you're polishing it,
you've lost the plot.

## Files
- `common.py` — shared grounding prompt, the 6 scripted utterances, a latency timer,
  and the scorecard printer. Both paths use this so the comparison is apples-to-apples.
- `path_a_handwired.py` — mic → faster-whisper (STT) → `Stylist` brain (Groq) → Piper (TTS).
- `path_b_gemini_live.py` — mic → Gemini Live (STT+LLM+TTS in one stream) → speaker.

## Run

```bash
# from prototype/
pip install -r spikes/requirements-spike.txt

# Path A (hand-wired)
python spikes/path_a_handwired.py

# Path B (Gemini Live) — needs GEMINI_API_KEY in .env
python spikes/path_b_gemini_live.py
```

## Protocol (keep it honest)
1. Run **on throttled 4G**, not WiFi (use Network Link Conditioner on macOS).
2. Speak the 6 scripted utterances from `common.py` (printed at startup).
3. Utterances #3 and #4 are grounding traps: "white sneakers" (in catalog) must work,
   "Nike Air Max" (not in catalog) must be refused honestly.
4. Utterance #5 is the barge-in test — start talking mid-reply.
5. Record the audio of both so the Founder can judge **warmth**.
6. Fill in the RESULT block at the bottom of the spike doc.

The `TODO(spike)` markers are the only parts you hand-wire live. Everything measurable
(latency timing, grounding prompt, scorecard) is already here.
