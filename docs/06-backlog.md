# 06 — Backlog (The Board)

Simple Kanban. Move cards between sections. Keep **Doing** to 1–2 items (solo founder).

> Tip: When you push to GitHub, these can become GitHub Issues + a Projects board.
> For now, this file *is* the board.

---

## 📥 To Do

### Phase 1 — Latency spike
- [x] P1-1: Set up project skeleton (Python) — `prototype/`
- [ ] P1-2: Wire streaming STT (faster-whisper or Deepgram free)
- [x] P1-3: Wire LLM (Groq free tier) with a basic stylist prompt — `stylist.py`
- [ ] P1-4: Wire streaming TTS (Kokoro/Piper)
- [ ] P1-5: Connect LiveKit WebRTC audio (mic in / speaker out)
- [x] P1-6: Hardcoded product list of ~20 items — `data/products.json`
- [ ] P1-7: Add barge-in / interruption handling
- [ ] P1-8: Measure perceived latency; test on throttled 3G/4G
- [ ] P1-9: **Decision gate:** is latency < ~1s acceptable?
- [x] P1-12: Catalog behind a `ProductSource` adapter (swap-ready) — `product_source.py` (`LocalJsonSource`), `Stylist` wired; strategy in `docs/10-sourcing-strategy.md`. (Note: `affiliate_url` field populated in Phase 3 / P3-2)

### Spikes
- [ ] S1: Gemini Live vs hand-wired pipeline — scope `docs/spikes/S1-gemini-live-spike.md`, scaffold `prototype/spikes/` (blocked on: confirm Gemini Live free-tier key + 4G throttling)

### Phase 2 — Persona + taste (investor demo)
- [x] P2-1: Design the original character (look, name, personality bible) — `docs/13-character-bible.md`
- [ ] P2-2: Craft signature voice (XTTS clone or ElevenLabs)
- [ ] P2-3: Build 2D avatar with idle/thinking/reacting states (Rive/Live2D)
- [ ] P2-4: Latency-masking: thinking animations + backchannels ("mm-hmm")
- [x] P2-5: Tune LLM for styling POV (asks questions, recommends ≤3 with reasons, gentle next step) — `stylist.py`: warmth + TASK-vs-SOCIAL mode sensing + mood/occasion-aware styling + STYLING POV structure; smoke-tested
- [ ] P2-6: Graceful text fallback on poor network
- [ ] P2-7: Test with 5–10 real users; capture "would use again?"
- [x] P2-8: "Would buy" signal logging primitive — `events.py` (`log_would_buy` → `data/events.jsonl`, anon session id); UI Buy button wires to this later
- [x] P2-9: Price-aware recommendations — `stylist.py` `_parse_price_intent` ("under $X", "cheapest", "budget") filters/sorts by price; smoke-tested
- [x] P2-10: Instrument cost-per-session \u2014 `costs.py` (`SessionCost`, token\u2192$ pricing table, audio hooks) wired into `Stylist`; flushes `session_cost` event to `data/events.jsonl`. Early finding: input tokens dominate ~22:1 (history+grounding resent each turn) \u2192 prompt-caching/lean-context is the key cost lever (see `docs/12-pricing-strategy.md`)

### Phase 3 — Real products + buyable (sourcing & checkout handoff)
- [ ] P3-1: Swap fake catalog for real items via 1 affiliate source (Amazon PA-API / LTK / Rakuten)
- [ ] P3-2: Populate `affiliate_url` on real items; "Buy" taps deep-link to the retailer (they ship — we do NOT)
- [ ] P3-3: FTC affiliate disclosure ("Mira earns a small commission") in the buy flow
- [ ] P3-4: Preference memory persisted (body, budget, vibe, past likes) on top of `UserProfile`

### Phase 4 — Retention (accounts, memory, comms)
- [ ] P4-1: Lightweight accounts + email capture (privacy-first, consented)
- [ ] P4-2: Mira re-engagement notifications/email ("how did the wedding outfit go?") — retention mechanic
- [ ] P4-3: Cross-session memory ("remember last time")
- [ ] P4-4: Measure 7-day return rate

### Phase 5 — Premium "wow" layer (post-PMF)
- [ ] P5-1: Virtual try-on as an orchestrated tool — Mira invokes a `TryOnSource` adapter (off-the-shelf VTO API or open model e.g. IDM-VTON/OOTDiffusion), then reacts with styling judgment. **Flagship premium feature**: free taste (1–2 try-ons) → gated behind Plus/credits (see `docs/12-pricing-strategy.md`). **Requires VTO privacy/consent guardrails** (`docs/09-...`): explicit consent, no default retention, no try-on on others' photos.

---

## 🔨 Doing
- [ ] P2-5: Tune LLM for styling POV — warmth pass shipped; next: "recommend 3 with reasons" structure

---

## ✅ Done
- [x] Vision agreed
- [x] Risks mapped & ordered
- [x] Roadmap + decision gates drafted
- [x] MVP ballpark estimate
- [x] Free-first tech stack chosen
- [x] Planning board created in repo
- [x] P1-1/P1-3/P1-6 prototype scaffold runs
- [x] P1-8 (text baseline): latency ~404ms first token / ~560ms total — **gate PASS**
- [x] Co-founder discussion (PM + CTO) — `docs/07-cofounder-discussion.md`
- [x] S1 spike scoped + throwaway scripts scaffolded — `docs/spikes/S1-gemini-live-spike.md`, `prototype/spikes/`
- [x] S1: Gemini Live vs hand-wired — **DECISION: Path B (Gemini Live, `gemini-3.1-flash-live-preview`)**. Latency PASS (~650ms), grounding PASS (catalog-only), barge-in PASS (half-duplex), warmth confirmed great. Path A kept as voice-ownership fallback.
- [x] Sales/GTM discussion — `docs/08-sales-gtm-discussion.md`
- [x] Legal + Trust/Safety discussion — `docs/09-legal-trust-safety-discussion.md`
- [x] P1-10: Prompt hardened vs hallucination + T&S care guardrails (body-positive, no manipulation, anti-overconsumption, honest-AI) — `stylist.py`, smoke-tested
- [x] P1-11: Privacy-first `UserProfile` (minimal fields, `forget()`, no raw audio) wired into the brain — `profile.py`, smoke-tested
- [x] P1-13: Fix grounding pre-filter to map everyday words → categories (`sneakers`→shoes, `jeans`→bottoms, etc.) — `stylist.py`, smoke-tested
- [x] P2-5 (partial): Warmth/rapport persona pass — Mira opens like a friend, reacts emotionally, stays grounded — `stylist.py`, smoke-tested

---

## 🧊 Icebox (NOT in v1)
- In-app payments / checkout
- **Being a retailer** — holding inventory, packing, shipping (we use affiliate handoff; the retailer ships)
- 3D avatar
- Multi-language
- AR / virtual try-on — see **P5-1** (parked as a future premium feature, not icebox-dead)
- Accounts/login (until Phase 4)
- Infra scaling/optimization
