# 02 — Risks (ordered by danger)

We sequence work by **risk**, not by what's easy. Kill the scariest assumptions first.

| # | Risk | If false, the product… | Tested in | Status |
|---|------|------------------------|-----------|--------|
| 1 | **Latency** — voice feels laggy on mobile | …is unusable | Phase 1 | � De-risked (text) |
| 2 | **Persona magic** — people don't emotionally connect | …has no moat | Phase 2 | 🔴 Open |
| 3 | **Taste/curation** — recommendations feel generic | …is no better than Amazon | Phase 2 | 🟠 Issue found |
| 4 | **Product sourcing** — can't legally/reliably get products | …can't sell anything | Phase 3 | 🔴 Open |
| 5 | **Retention** — people try once, don't return | …has no business | Phase 4 | 🔴 Open |

---

## Risk 1 — Latency (the #1 technical killer)
- Voice feels magical only if **< ~800ms** perceived response; > 1.2s feels broken.
- Mobile networks have **high latency variance + packet loss**, not just low bandwidth.
- **Mitigations:**
  - Stream everything (streaming STT → LLM → TTS).
  - WebRTC transport (LiveKit/Pipecat), not request/response.
  - Edge/regional inference; fast LLM (Groq/Gemini Live).
  - **Latency masking via persona** — thinking animations, "mm-hmm", instant visual reactions.
  - **Graceful degradation** → fall back to text on poor signal to protect the relationship.
- ✅ **Text-loop baseline (2026-06-26):** Groq free tier, avg first token ~404ms,
  total ~560ms over 6 turns — clears the <1s gate. Voice overhead still to test (P1-8).

## Risk 2 — Persona magic
- The character must make people *feel something* in 60 seconds.
- Mitigation: signature voice (XTTS/ElevenLabs), expressive 2D avatar, personality-tuned LLM.

## Risk 3 — Taste / curation
- Opinionated, consistent style POV. "Here are 3, and here's why these are *you*."
- Mitigation: prompt-engineered styling logic; later, fine-tuning on style data.

### 🧪 Finding (2026-06-26, text-loop test)
First real conversation exposed **hallucination**, the most reputation-damaging failure:
- Recommended brands NOT in catalog (Converse, Vans, Adidas, "ON shoes").
- **Invented stores as fact** (Brown Thomas, Samui, The Edge Sports, On-Running.com).
- Forced irrelevant items (offered shirts/tees for a *shoe* request).
- Root cause: tiny fixed catalog + no "can't fulfil" escape hatch → model lies confidently.
- **Fix (now):** harden prompt to refuse out-of-catalog requests honestly and never
  invent brands/stores/URLs. **Real fix:** Phase 3 multi-source sourcing.

## Risk 4 — Product sourcing (legal)
- ⚠️ **Avoid scraping** retailer sites — legally risky, brittle.
- Use **official / affiliate APIs** (Amazon PA-API, eBay, Rakuten, Shopify Storefront).
- They're free *and* pay commissions.

## Risk 5 — Retention
- Cross-session memory, re-engagement, "remember last time."
- Metric: 7-day return rate.

---

## Non-technical risks
- **Solo-founder bandwidth** — mitigate by ruthless scope cuts (see roadmap "NOT in v1").
- **Co-founder gap** — design/animation + fashion-domain credibility needed before raising.
- **Cost creep** — stay free-first; pay only where quality gates the demo.
