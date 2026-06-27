# 07 — Co-Founder Discussion: Bringing Mira to Life

> A working session between three voices:
> - **🧭 You (Founder / Vision)** — owns the "why" and the emotional bet.
> - **📋 PM (Product)** — owns scope, sequencing, and "what do we actually ship and measure."
> - **🛠️ Tech Co-Founder (CTO)** — owns architecture and early, hard-to-reverse tech bets.
>
> Goal of this doc: decide *what is required to bring the idea to life*, and lock the
> **early decisions** that are expensive to change later.

---

## 0. The shared belief (alignment first)

We all agree on the core bet:

> The moat is **emotional design + character + voice curation**, not "AI that shops."
> Anyone can wire an LLM to a product API. Almost nobody can make you *feel* like
> you're talking to a stylish friend who remembers you.

Everything below serves that bet. If a decision doesn't make Mira feel more **fast, warm,
or trustworthy**, it's not a Phase 1–2 decision.

---

## 1. 📋 PM: What does "bring it to life" actually mean?

The trap for a solo/early team is building everything at once. PM reframes "alive" as a
**ladder of proof**, each rung de-risking one assumption:

| Rung | The question we're answering | "Alive" looks like | Owner |
|------|------------------------------|--------------------|-------|
| R1 | Can it talk fast enough to feel human? | Voice loop < 1s on mobile | CTO |
| R2 | Does the character create an emotional pull? | 7/10 testers say "I'd talk to her again" | Founder |
| R3 | Are the recommendations actually good? | Picks feel curated, not random; no hallucinated items | PM + CTO |
| R4 | Will people come back? | 7-day return rate trending up | PM |

**PM's hard rule:** we do not advance a rung until the previous one passes its gate.
R3 (taste) and R2 (persona) are the real product. R1 (latency) is just the ticket to play.

**PM's immediate call:** the current hallucination bug (Mira recommending Converse/Vans
not in catalog) is an **R3 credibility leak** showing up early. Fix the prompt now, but
log it as the #1 reason Phase 3 (real sourcing) exists.

---

## 2. 🛠️ Tech Co-Founder: Early decisions we must get right

The CTO's job is to separate **reversible** decisions (try, swap later) from
**load-bearing** ones (expensive to change after we build on them).

### 🔒 Load-bearing decisions (decide now, hard to undo)

| Decision | Call | Why it's load-bearing |
|----------|------|------------------------|
| **Realtime transport** | Pipecat + LiveKit (self-host WebRTC) | Everything streams through it; rewriting later = full rework |
| **Streaming-first contract** | STT, LLM, TTS all stream tokens/audio chunks | Latency budget depends on it; batch APIs can't be retrofitted into <1s |
| **State model** | Conversation state + user memory as a clean interface from day 1 | Memory (Phase 4) is the retention moat; bolting it on later corrupts everything |
| **Character voice ownership** | Treat the voice as owned IP (XTTS/custom), not a vendor default | If the voice *is* the brand, renting it from one vendor is existential risk |
| **Product source = adapter interface** | All catalogs (fake now, affiliate later) behind one `ProductSource` interface | Lets us swap FakeStore → Amazon/eBay without touching the brain |

### 🔁 Reversible decisions (pick the free/fast one, swap freely)

| Decision | Start with | Swap to if needed |
|----------|-----------|-------------------|
| LLM | Groq free tier (fast) | Ollama local / Gemini Live / hosted |
| STT | faster-whisper local | Deepgram |
| TTS | Kokoro / Piper local | XTTS custom → ElevenLabs (only if quality gates demo) |
| Avatar | Rive (2D) | Live2D |
| App shell | Expo (React Native) | — |
| Hosting | Fly.io / Railway free tier | paid tier on scale |

### 🧪 Spikes worth a half-day each (cheap experiments)
- **Gemini Live spike:** could collapse STT+LLM+TTS into one realtime box. If latency +
  voice quality are good, it simplifies the whole pipeline. Worth knowing before we
  hand-wire three components.
- **Barge-in / interruption** on Pipecat — the single biggest "feels human" feature.

### 🚫 CTO's hard no's
- **No scraping** product data — affiliate/official APIs only (legal + brittle).
- **No 3D avatar** — 2D is cheaper and on-brand.
- **No accounts/auth** until Phase 4 — premature and slows iteration.
- **Don't build WebRTC ourselves** — Pipecat/LiveKit give it free.

---

## 3. The thing we're under-investing in (CTO + PM agree)

**User memory is the retention moat, and it's currently a Phase 4 afterthought.**

Decision: even though we *ship* memory in Phase 4, we **design the interface in Phase 1**.
A tiny `UserProfile` (body, budget, vibe, liked items, last conversation summary) passed
into the stylist brain. In Phase 1 it can be in-memory/JSON. The point is the brain is
*written as if memory exists* from the start, so retention isn't a rewrite later.

---

## 4. 📋 PM: What's required to bring it to life (the checklist)

### Right now (still Phase 1 — "Can it talk fast?")
- [ ] **P1-10** Harden prompt against hallucination (R3 leak) — *quick, do first*
- [ ] Introduce a `UserProfile` interface into the brain (memory-ready, even if empty)
- [ ] Put the catalog behind a `ProductSource` interface (swap-ready)
- [ ] **P1-2/4/5** Wire voice loop: STT → LLM → TTS via Pipecat
- [ ] **P1-7** Barge-in / interruption handling
- [ ] **P1-8** Test on throttled 3G/4G (not WiFi)
- [ ] **Spike:** Gemini Live as a single realtime box (timebox: half a day)
- [ ] **P1-9** Latency gate decision → go/no-go to Phase 2

### Then (Phase 2 — "Does it feel magical?") — the investor demo
- [ ] Character design + Rive avatar with thinking animations
- [ ] Signature voice (XTTS custom)
- [ ] LLM tuned for styling POV: asks 1–2 good questions, recommends 3 with reasons
- [ ] User test with 5–10 people → measure "would talk again" %

---

## 5. Roles & ownership (so nothing falls between chairs)

| Area | Primary owner | Success measure |
|------|---------------|-----------------|
| Emotional design / character / voice | 🧭 Founder | "I'd use again" % |
| Scope, sequencing, user testing | 📋 PM | Right rung shipped, gates honored |
| Architecture, latency, integrations | 🛠️ CTO | < 1s loop, clean swappable interfaces |
| Taste / curation quality | 📋 PM + 🛠️ CTO | No hallucinated items; picks feel chosen |

---

## 6. Open questions to resolve next session

1. **Gemini Live vs. hand-wired pipeline** — run the spike, then commit. This affects the
   whole Phase 1 architecture.
2. **Voice identity** — do we cast/design Mira's voice *before* the persona LLM tuning, or
   after? (Founder's call — but it gates the Phase 2 demo.)
3. **What's the smallest "memory" that creates a wow moment?** ("Last time you wanted
   something for a wedding — how'd it go?") — PM to define the minimal lovable memory.
4. **Distribution** — not a build question, but: where do the first 10 testers come from?

---

## 7. Decision log (append-only)

| Date | Decision | Made by |
|------|----------|---------|
| 2026-06-26 | Memory interface designed in Phase 1, shipped in Phase 4 | CTO + PM |
| 2026-06-26 | All product catalogs behind one `ProductSource` adapter | CTO |
| 2026-06-26 | Character voice treated as owned IP, not vendor default | Founder + CTO |
| 2026-06-26 | Streaming-first is non-negotiable across STT/LLM/TTS | CTO |
| 2026-06-26 | Gemini Live spike before committing to hand-wired pipeline | CTO |
