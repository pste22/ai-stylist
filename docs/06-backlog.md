# 06 — Backlog (The Board)

Simple Kanban. Move cards between sections. Keep **Doing** to 1–2 items (solo founder).

> Tip: When you push to GitHub, these can become GitHub Issues + a Projects board.
> For now, this file *is* the board.

---

## 📥 To Do

### Phase 1 — Latency spike
- [ ] P1-1: Set up Pipecat project skeleton (Python)
- [ ] P1-2: Wire streaming STT (faster-whisper or Deepgram free)
- [ ] P1-3: Wire LLM (Groq free tier) with a basic stylist prompt
- [ ] P1-4: Wire streaming TTS (Kokoro/Piper)
- [ ] P1-5: Connect LiveKit WebRTC audio (mic in / speaker out)
- [ ] P1-6: Hardcoded product list of ~20 items the agent can recommend
- [ ] P1-7: Add barge-in / interruption handling
- [ ] P1-8: Measure perceived latency; test on throttled 3G/4G
- [ ] P1-9: **Decision gate:** is latency < ~1s acceptable?

### Phase 2 — Persona + taste (investor demo)
- [ ] P2-1: Design the original character (look, name, personality bible)
- [ ] P2-2: Craft signature voice (XTTS clone or ElevenLabs)
- [ ] P2-3: Build 2D avatar with idle/thinking/reacting states (Rive/Live2D)
- [ ] P2-4: Latency-masking: thinking animations + backchannels ("mm-hmm")
- [ ] P2-5: Tune LLM for styling POV (asks questions, recommends 3 with reasons)
- [ ] P2-6: Graceful text fallback on poor network
- [ ] P2-7: Test with 5–10 real users; capture "would use again?"

---

## 🔨 Doing
- [ ] (nothing yet — start with P1-1)

---

## ✅ Done
- [x] Vision agreed
- [x] Risks mapped & ordered
- [x] Roadmap + decision gates drafted
- [x] MVP ballpark estimate
- [x] Free-first tech stack chosen
- [x] Planning board created in repo

---

## 🧊 Icebox (NOT in v1)
- In-app payments / checkout
- 3D avatar
- Multi-language
- AR / virtual try-on
- Accounts/login (until Phase 4)
- Infra scaling/optimization
