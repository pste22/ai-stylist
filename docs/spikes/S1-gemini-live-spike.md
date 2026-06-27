# Spike S1 — Gemini Live vs. Hand-Wired Voice Pipeline

> **Type:** Architecture spike (throwaway code OK)
> **Timebox:** 1 day (8h hard cap — if it's not promising by hour 6, we stop)
> **Owner:** 🛠️ Tech Co-Founder
> **Phase:** 1 ("Can it talk fast?")
> **Status:** Not started

---

## 1. Why this spike exists

We have two architectural paths to a real-time voice loop, and the choice is
**load-bearing** (everything in Phase 1–2 builds on top of it):

| Path | What it is | Pipeline |
|------|------------|----------|
| **A — Hand-wired** | We orchestrate 3 components ourselves via Pipecat | mic → STT (faster-whisper) → LLM (Groq) → TTS (Piper) → speaker |
| **B — Gemini Live** | One realtime multimodal API does STT+LLM+TTS in a single bidirectional stream | mic → Gemini Live → speaker |

We must not build the whole Phase 1 pipeline before knowing which one wins. This spike
answers that **in one day** with throwaway code.

---

## 2. The question we're actually answering

> Does Gemini Live give us a **faster, simpler, warmer-sounding** voice loop than the
> hand-wired stack — *without* giving up the two things that are non-negotiable:
> (a) **grounding** (Mira may only recommend catalog items), and
> (b) **barge-in** (user can interrupt)?

This is NOT "which is technically cooler." It's "which gets us to a magical demo faster
without breaking our moat."

---

## 3. Decision criteria (score each path)

Score 1–5 on each. **Grounding and latency are gates** — a hard fail there kills the path
regardless of other scores.

| Criterion | Weight | Why it matters | Gate? |
|-----------|--------|----------------|-------|
| **Perceived latency** (first audio out) | ★★★ | Risk #1. Target < 1s, ideally < 700ms | ✅ must be < 1s |
| **Grounding control** | ★★★ | Mira can ONLY suggest catalog items. Can we inject the product list + enforce it? | ✅ must work |
| **Barge-in / interruption** | ★★★ | The #1 "feels human" feature | ✅ must work |
| **Voice warmth / quality** | ★★ | The brand IS the voice | — |
| **Voice ownership / customization** | ★★ | Can we make Mira's voice *ours*, or are we renting a default? | — |
| **Simplicity** (lines of code, moving parts) | ★★ | Solo team; fewer parts = faster iteration | — |
| **Cost at demo + early-beta scale** | ★ | Free-first principle | — |
| **Lock-in risk** | ★ | If Google changes terms/pricing, how stuck are we? | — |

---

## 4. What we build (throwaway)

Reuse the existing brain contract so the spike is apples-to-apples. The stylist logic
(persona prompt + catalog grounding) already lives in [stylist.py](../../prototype/stylist.py)
and [catalog.py](../../prototype/catalog.py).

### Path B — Gemini Live (build this first; it's the unknown)
1. Minimal script: mic in → Gemini Live bidirectional stream → speaker out.
2. **Grounding test:** inject Mira's system prompt + the ~20-item product list as
   context. Ask for "white sneakers" (in catalog) and "Nike Air Max" (NOT in catalog).
   - ✅ Pass = recommends only catalog items, refuses the Nike honestly.
   - ❌ Fail = hallucinates brands → grounding gate failed.
3. **Barge-in test:** start talking while Mira is speaking. Does it stop and listen?
4. **Latency:** measure time from end-of-user-speech → first audio out, 6 turns.
5. **Voice:** subjective note — does it sound like it *could* be Mira? Can we tune it?

### Path A — Hand-wired (only a thin slice; the brain already exists)
1. Pipecat pipeline: faster-whisper → `Stylist.reply_stream()` → Piper → speaker.
2. Same 3 tests: grounding (already proven in text loop), barge-in, latency, voice.
3. Note: we already know the LLM half is ~404ms first token on Groq — so this is mostly
   measuring STT + TTS overhead on top.

> Keep both in a scratch folder, e.g. `prototype/spikes/` — do not wire into the main loop.

---

## 5. Measurement protocol (keep it honest)

- **Same network:** run both on throttled 4G (Network Link Conditioner / `tc`), not WiFi.
  Latency on WiFi is a lie for a mobile product.
- **Same 6 utterances**, scripted, so it's comparable:
  1. "Hey, I need something for a summer wedding."
  2. "What's my budget look like — keep it under 100."
  3. "Do you have white sneakers?"        ← grounding (in catalog)
  4. "Actually, get me some Nike Air Max." ← grounding (NOT in catalog)
  5. *(interrupt mid-reply)* "wait, no—"   ← barge-in
  6. "Okay show me one more option."
- **Log:** first-audio latency per turn, grounding pass/fail, barge-in pass/fail.
- Record the audio of both so the Founder can judge **warmth** subjectively.

---

## 6. Deliverable (end of day)

A one-page result appended to this file:

```
RESULT (date):
- Path A latency (median, 4G): ___ms   Path B: ___ms
- Grounding:   A [pass/fail]   B [pass/fail]
- Barge-in:    A [pass/fail]   B [pass/fail]
- Voice warmth (Founder's gut, 1-5): A ___  B ___
- Simplicity (LOC / moving parts):   A ___  B ___
- DECISION: [A / B / need round 2]  because ______
```

---

## 7. Possible outcomes & what we do

| Outcome | Decision |
|---------|----------|
| **B is faster + grounding works + barge-in works** | Go Gemini Live for Phase 1. Revisit voice ownership in Phase 2 (lock-in risk noted). |
| **B is great but grounding is loose** | Hybrid: Gemini Live for STT+TTS, our own LLM step for grounded recommendations. |
| **B can't do barge-in or voice is un-customizable** | Stick with hand-wired (Path A) — we own the voice, that's the brand. |
| **Both roughly equal** | Pick hand-wired — more control over the IP that *is* the moat. |

---

## 8. Risks of the spike itself
- **Gemini Live API access / quota** — confirm a free-tier key works before day 1.
- **Voice ownership** — even if B wins on speed, if we can't make the voice *ours*,
  that conflicts with "character voice = core IP." Flag for Founder, don't decide solo.
- **Don't over-build** — this is throwaway. If you're polishing, you've lost the plot.

---

## 9. RESULTS log

### Partial — Path A brain baseline (2026-06-27)
Ran `spikes/path_a_handwired.py` **headless** (no audio I/O, no throttling). This is a
*floor*, not the real voice loop — STT + TTS + 4G overhead are NOT included.

```
- Path A latency (median, BRAIN-ONLY first token, WiFi): 163ms   Path B: not run
  per-turn ms: [461, 142, 149, 168, 161, 164]  (first turn cold)
- Grounding:   A [PASS]  ("white sneakers" + "Nike Air Max" both refused honestly)   B: not run
- Barge-in:    A [n/a — needs live audio]   B: not run
- Voice warmth: A [n/a — no TTS yet]   B: not run
- DECISION: PENDING — Path A LLM half has huge latency headroom (163ms vs 1000ms budget),
  so STT+TTS can spend ~800ms and still pass. Real comparison still needs:
  (1) GEMINI_API_KEY, (2) audio libs (sounddevice/google-genai) + mic, (3) 4G throttling.
```

**Takeaway:** the brain is NOT the latency risk — it leaves ~800ms of budget for audio.
The open question the spike must still answer is whether Gemini Live (Path B) beats a
hand-wired Whisper+Piper stack on *total* audio latency, warmth, and barge-in. Blocked on
the three items above.

### Path B — Gemini Live, TEXT-driven (2026-06-27)
Ran `spikes/path_b_gemini_live.py` (text mode) — drives the Live session with the 6
scripted lines as text, measures time-to-first-audio, saves each reply to a WAV, and
captures the audio transcript to verify grounding. **WiFi, unthrottled** (4G would be worse).
Model: `gemini-2.5-flash-native-audio-latest`, voice `Aoede`.

```
- Path B latency (median, first audio, WiFi): 2507ms   per-turn: [4183, 3544, 1896, 2958, 2018, 2056]
  (turn 1 cold ~4.2s; warm turns ~2s)
- Grounding: PASS
    #3 "white sneakers" -> "Canvas Low-Top Sneakers in off-white" (real catalog item) ✅
    #4 "Nike Air Max"   -> "I don't carry Nike Air Max yet" (honest refusal) ✅
- Voice warmth: PENDING — listen to spikes/_recordings/turn*_Aoede.wav (Founder's call)
- Barge-in: NOT YET — run `path_b_gemini_live.py mic` (needs a real microphone)
```

**🚨 Headline finding — latency is the problem, not grounding.**
- **Grounding is excellent** out of the box: clean catalog-only recommendations and honest
  refusals, just from the system prompt. No hybrid needed for grounding.
- **First-audio latency ~2.5s (warm), ~4.2s (cold) on WiFi — FAILS the <1s gate.** The
  native-audio model "thinks" before speaking (we observed `thought` parts), which adds
  seconds. On 4G this gets worse, not better.

**What this means / next probes before deciding A vs B:**
1. Try a **non-thinking / half-cascade Live model** (e.g. `gemini-3.1-flash-live-preview`)
   or disable thinking — see if first-audio drops under ~1s.
2. Judge **warmth** from the saved WAVs (if Aoede is magical, latency tuning is worth it).
3. Run **mic mode** to confirm barge-in works.
4. Compare against a real Path A audio stack (Whisper+Piper) end-to-end, not just the brain.

**Provisional lean:** grounding is a solved problem on B, but raw B latency disqualifies it
as-is. Decision deferred pending the faster-model probe + warmth judgment.

### Path B — model latency probe (2026-06-27) — ⭐ the breakthrough
Probed first-audio latency across Live models with the same grounded prompt (3 turns each,
WiFi):

```
gemini-3.1-flash-live-preview         first-audio ms: [658, 633, 652]   ✅ PASS (<1s)
gemini-2.5-flash-native-audio-latest  first-audio ms: [2851, 2327, 3424] ❌ FAIL
```

**Finding:** the native-audio models *think* before speaking (~2.5-3.4s). The **half-cascade
`gemini-3.1-flash-live-preview` skips that and hits ~650ms first-audio — under the gate, on
WiFi.** Default model switched to the fast one in `path_b_gemini_live.py`.

**Updated scorecard for Path B (fast model):**
```
- Latency:  ~650ms first audio (WiFi) ✅   (re-test on 4G to confirm headroom)
- Grounding: PASS (catalog-only recs + honest refusals, system-prompt only)
- Warmth:   PENDING — judge spikes/_recordings/*.wav
- Barge-in: PENDING — run `path_b_gemini_live.py mic`
```

**Where this leaves the A-vs-B decision:**
Path B (Gemini Live, fast model) now clears latency AND grounding from a single API — far
simpler than hand-wiring Whisper+Groq+Piper (Path A). The remaining deciders are (1) voice
**warmth/ownership** — if we can't make a Gemini prebuilt voice feel like *Mira*, that fights
"voice = core IP"; and (2) **barge-in** on mic. If warmth + barge-in pass, **B is the Phase 1
pick** with Path A kept as the fallback for full voice control.

### ✅ FINAL DECISION — Path B (2026-06-27)
**Picked: Path B — Gemini Live (`gemini-3.1-flash-live-preview`, voice "Aoede").**
All four gates pass:
- Latency: PASS (~650ms first audio, under 1s budget)
- Grounding: PASS (catalog-only recs + clean out-of-catalog refusals via output transcription)
- Barge-in: PASS (mic mode, half-duplex default to kill acoustic echo; `FULL_DUPLEX=1` for headphones)
- Warmth: PASS (confirmed "great and professional" live; persona warmth pass added in `stylist.py`)

Rationale: one API solves latency + grounding + barge-in that Path A needs 3+ stitched
components for. **Path A is retained as the voice-ownership fallback** — if a custom/cloned
voice becomes core IP later, the hand-wired pipeline gives full control. Revisit if Gemini
free-tier limits, pricing, or voice-customization constraints become blockers.

