# 08 — Sales & GTM Discussion: How We Accelerate Mira

> A working session adding two voices to the founding table:
> - **💼 Head of Sales / GTM** — owns "who pays, why, and how we reach them."
> - **📣 Growth / Marketing** — owns "how strangers discover Mira and become fans."
>
> The Founder, PM, and CTO are in the room too (see
> [07-cofounder-discussion.md](07-cofounder-discussion.md)). This doc answers:
> **what matters most commercially, and what sales can start doing NOW** — even
> before the product is fully built.

---

## 0. The uncomfortable truth sales says out loud

> "A magical demo is not a business. We need to know **who pays, what they pay for,
> and whether we can reach them for less than they're worth** — *before* we fall in
> love with the avatar."

So the GTM team's job in the early phase isn't to sell (there's nothing to sell yet).
It's to **de-risk the commercial assumptions in parallel** with the tech spike, so when
Phase 2 produces a demo, we already know who to put it in front of and how money flows.

---

## 1. 💼 What matters MOST (sales' ranking)

Sales reframes the whole idea around one question: *"What is the thing someone would
miss if we took it away?"* Their ranked answer:

| Rank | What matters | Why it's #1-worthy | Whose job |
|------|--------------|--------------------|-----------|
| 1 | **Emotional trust** ("she gets my taste") | It's the only reason someone returns AND tells a friend. No trust → no retention → no revenue | Founder + PM |
| 2 | **A buyable outcome** (real click → real purchase) | Without a checkout handoff, there's no transaction to monetize, ever | CTO (Phase 3) |
| 3 | **A repeatable reason to come back** | Habit = LTV. One-time delight doesn't pay | PM (Phase 4) |
| 4 | **A reachable audience** (cheap to find) | If CAC > LTV, the business is dead even if the product is loved | Growth |

**Sales' headline:** the moat (emotional character) and the money (affiliate conversion +
retention) are the **same thing** — people buy from someone they trust. That alignment is
rare and is the strongest part of this idea. Don't dilute it.

---

## 2. 💰 How Mira actually makes money (so sales knows what they're selling)

The team aligns on a **layered revenue model**, sequenced to match the roadmap:

| Stage | Model | When | Sales motion |
|-------|-------|------|--------------|
| **V1** | **Affiliate commission** (Amazon PA-API, eBay, Rakuten, LTK) | Phase 3 | Zero-friction: user buys, we earn % — no selling required |
| **V2** | **Brand placement / sponsored curation** (clearly labeled, taste-first) | Post-retention | B2B sales motion to DTC fashion brands |
| **V3** | **Premium subscription** (deeper memory, early access, unlimited styling) | After habit proven | Consumer upgrade, low-touch |
| **❌ Not now** | Taking inventory / payments / being a retailer | — | Capital-heavy, off-strategy |

**Critical guardrail (Founder + Sales agree):** sponsored placement must NEVER override
taste. The moment Mira recommends something because she was *paid* to, not because it
*suits you*, the trust moat dies and so does the business. Monetization rides on trust,
never ahead of it.

---

## 3. 💼 What sales can START doing NOW (pre-product)

This is the "guiding how sales accelerates" the Founder asked for. None of it needs a
finished product — it de-risks commercial assumptions in parallel with the S1 spike.

### A. Define the beachhead customer (Week 1–2)
Don't sell to "everyone who wears clothes." Pick ONE wedge where the pain is sharp:
- **Candidate wedges:** "I have an event and nothing to wear" panic-shoppers ·
  style-anxious 20–35s · busy professionals who hate scrolling · gifting.
- **Deliverable:** a one-paragraph ICP (ideal customer profile) + where they hang out.

### B. Run 15–20 problem interviews (Week 2–4) — *highest-leverage sales activity*
Talk to real target users. NOT "would you use an AI stylist?" (everyone lies politely).
Instead: *"Tell me about the last time you struggled to find something to wear."*
- **Goal:** confirm the pain is real, frequent, and worth paying to remove.
- **Bonus:** these 15–20 people become your **first testers** for the Phase 2 demo and
  your first word-of-mouth engine. Sales is building the pipeline before the product exists.

### C. Pre-validate the money path (Week 3–4)
- Confirm affiliate program acceptance + commission rates (Amazon PA-API, LTK, Rakuten).
- Sanity-check unit economics: *avg basket × commission % = revenue per converting chat.*
  Is that bigger than what it'll cost to acquire + serve that user?
- **Deliverable:** a back-of-envelope LTV:CAC guess. If it can't plausibly clear ~3:1,
  flag it loudly now.

### D. Build a tiny waitlist / design-partner list (ongoing)
- A one-line landing page: "Meet Mira, the stylist who actually gets you. Join the list."
- Measures real pull (signup rate) for ~$0 and seeds launch demand.
- **3 numbers sales tracks:** signups, interview-confirmed pain %, affiliate-approved sources.

---

## 4. 📣 Growth: how strangers discover Mira

The product IS the marketing — a charming character is inherently shareable. Lean in:
- **Show, don't tell:** short clips of Mira giving a genuinely good, warm recommendation.
  The "wow, she's actually charming" reaction is the ad.
- **Founder-led / character-led content** on TikTok/Reels before any paid spend.
- **Defer paid acquisition** until the demo earns "I'd use again" — paying to send strangers
  to a product that doesn't yet retain is lighting money on fire.

---

## 5. The one metric sales adds to the board

The roadmap already tracks 3 numbers (latency, "would use again" %, 7-day return). Sales
adds a **commercial signal** so we don't build a beloved toy that can't pay rent:

> **Recommendation → click-through → (eventually) purchase conversion.**
> Even a fake "Buy" button in the Phase 2 demo that just logs the click tells us whether
> Mira's taste creates *purchase intent*, not just delight.

---

## 6. Where this changes the build (sales → CTO/PM asks)

Two small, cheap asks that protect the commercial path early:
1. **Log a "would buy" signal** in the Phase 2 demo (fake Buy button → event). Costs
   almost nothing, gives the #1 commercial proof point. → PM
2. Keep the `ProductSource` adapter (P1-12) **affiliate-shaped** — i.e. each item can carry
   an `affiliate_url` field from day one, even if it's null now. Avoids a refactor when
   real monetization lands. → CTO

---

## 7. Decision log (append-only)

| Date | Decision | Made by |
|------|----------|---------|
| 2026-06-26 | Primary revenue = affiliate commission first; sponsorship/subscription later | Sales + Founder |
| 2026-06-26 | Sponsored placement may NEVER override taste — trust is the moat | Founder + Sales |
| 2026-06-26 | Sales runs problem interviews + waitlist NOW, in parallel with S1 spike | Sales + PM |
| 2026-06-26 | Add a "would buy" click signal to the Phase 2 demo | Sales + PM |
| 2026-06-26 | `ProductSource` items carry an `affiliate_url` field from day one (nullable) | Sales + CTO |

---

## 8. Open questions for next session
1. **Which beachhead wedge** do we commit to first? (event-panic vs. style-anxiety vs. gifting)
2. **What's the smallest believable "Buy" experience** in the demo that yields a real signal?
3. **Who are the first 15–20 interviewees**, and who owns booking them this week?
