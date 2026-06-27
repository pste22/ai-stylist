# 09 — Legal & Trust/Safety Discussion: Guardrails Before We Build

> The last voices to join the founding table before we execute stories:
> - **⚖️ Legal / Compliance** — owns "what could get us sued, fined, or shut down."
> - **🛡️ Trust & Safety / Ethics** — owns "how Mira treats vulnerable users with care."
>
> This is NOT lawyer theater. It exists because a few decisions are **cheap now and
> ruinously expensive later** — and several touch code we're about to write (the
> `UserProfile` memory interface P1-11, the persona prompt P1-10). Get them right once.

---

## 0. The framing both bring

> ⚖️ "The product touches three regulated nerves at once: **recording voices**, **storing
> personal data**, and **earning commissions on recommendations**. None are blockers —
> but each has a cheap right way and an expensive wrong way."
>
> 🛡️ "We're a stylist. That means we comment on people's **bodies and appearance**. That
> is emotionally loaded. Warmth without care can hurt people — and torch the trust moat
> faster than any bug."

The good news: doing this *well* **strengthens** the moat. Trust is the product; safety
and privacy are how trust survives contact with reality.

---

## 1. ⚖️ Legal — the five nerves, ranked by "fix it now" value

| # | Nerve | The risk | The cheap fix (do now) | Phase |
|---|-------|----------|------------------------|-------|
| 1 | **Voice recording / consent** | Two-party-consent states + laws require telling users they're being recorded/processed | Up-front mic consent + "you're chatting with an AI" notice; don't store raw audio (transcribe & drop) | P1/P2 |
| 2 | **Personal data / memory** | Storing body, budget, preferences = personal data under GDPR/CCPA | Design `UserProfile` (P1-11) with **data minimization** + a delete path from day one | **P1 now** |
| 3 | **AI disclosure** | Users must know Mira isn't human (rising legal + platform requirement) | Mira honestly says she's an AI if asked; never deceive | P2 persona |
| 4 | **Affiliate / FTC disclosure** | Paid links + sponsored picks require clear disclosure | "Mira earns a small commission" notice; sponsored items clearly labeled | P3 |
| 5 | **Product liability / claims** | Don't promise fit/authenticity we can't guarantee; don't defame brands | Recommend as opinion ("I think this suits you"), not guarantees | P3 |

**Legal's one hard ask that touches code today:** the memory interface (P1-11) must be
built **privacy-first** — store the *least* we need, make it *deletable*, and never store
raw audio. Retrofitting privacy onto a memory system is a nightmare; designing it in is free.

---

## 2. 🛡️ Trust & Safety — Mira's character must be *kind*, not just charming

A stylist that comments on bodies can do real harm. The persona prompt (P1-10, which we're
about to edit) is where this lives. T&S's non-negotiables for Mira's character:

- **Body-positive by default.** Compliment style and fit, never imply a body is wrong.
  No "hide your flaws" framing — it's "here's what'll make you feel great."
- **Inclusive.** Don't assume gender, size, budget, or ability. Ask, don't presume.
- **No manipulation / dark patterns.** Never weaponize urgency, scarcity, or insecurity to
  drive a purchase ("you NEED this or you'll look bad" is banned). She's a friend, not a
  high-pressure salesperson.
- **Anti-overconsumption.** It's OK — even brand-building — for Mira to say "honestly, you
  don't need anything new, you already own something that works." Trust > one sale.
- **Graceful on sensitive topics.** Weight, body image, self-esteem, money stress: respond
  with warmth, never judgment; never give medical/dietary advice.
- **Honest limits.** If she can't help (no good catalog match), she says so — ties directly
  to the anti-hallucination work in P1-10.

> 🛡️ "These aren't constraints on the charm — they ARE the charm. The most lovable stylist
> friend is the one who's honest, kind, and never makes you feel small."

---

## 3. Where this changes what we build (the concrete asks)

### → P1-10 (prompt hardening, happening now)
Fold T&S guardrails **into the same edit** as the anti-hallucination work. Mira's persona
gains: body-positive framing, no manipulative urgency, honest about being AI, anti-overconsumption,
graceful on sensitive topics. One edit, two wins (taste credibility + safety).

### → P1-11 (UserProfile memory interface)
Build privacy-first from line one:
- Store only structured, minimal fields (vibe, budget band, sizes, liked item ids) —
  **not** raw transcripts or audio.
- Include a `forget()` / delete path in the interface even if the UI comes later.
- Treat the profile as deletable user-owned data, not our asset.

### → Phase 2 / Phase 3 (note for later, don't build yet)
- Mic-consent + AI-disclosure notice in the demo UI.
- FTC affiliate disclosure line once real links land.

---

## 4. ✅ What we are NOT doing now (avoid premature lawyering)
- No formal privacy policy / ToS drafting yet (needed before public beta, not before a spike).
- No DPA/vendor audits yet (free-tier tools, no real user data at risk in Phase 1).
- No incorporation/IP filing decisions here — that's a Finance/Founder session.

The principle: **build the cheap, code-level guardrails now**; defer the paperwork until a
real user's data is actually at stake.

---

## 5. Decision log (append-only)

| Date | Decision | Made by |
|------|----------|---------|
| 2026-06-27 | `UserProfile` (P1-11) is privacy-first: minimal fields, deletable, no raw audio | Legal + CTO |
| 2026-06-27 | Persona guardrails (body-positive, no manipulation, anti-overconsumption, honest-AI) folded into P1-10 | T&S + Founder |
| 2026-06-27 | Mira admits she's an AI if asked; never deceives | T&S + Legal |
| 2026-06-27 | Defer formal policy/ToS/DPA work until pre-beta (not Phase 1) | Legal |
| 2026-06-27 | Anti-overconsumption ("you don't need anything new") is on-brand, not a bug | T&S + Founder |

---

## 6. Open questions for later
1. Which states/regions do early testers live in? (sets the voice-consent bar)
2. Do we need an explicit "this is not professional styling/medical advice" line in the UI?
3. Who owns the privacy policy draft when we approach public beta?

---

## 7. Virtual try-on (VTO) — body-image data is a step-change in sensitivity
> Parked as a future premium feature (P5-1), but the guardrails must be set *before* any
> build, because VTO crosses a new privacy line: users upload **photos of their bodies**.

- **Explicit, specific consent** before any image upload — separate from general ToS.
- **No retention by default** — generate, show, discard. Storing body images is opt-in,
  purpose-limited, and deletable (mirrors the `UserProfile.forget()` stance).
- **No try-on on other people's photos** — only the user's own image; block misuse
  (deepfake/harassment risk).
- **Biometric-law awareness** — body/face imagery can trigger laws like Illinois BIPA and
  GDPR special-category data. Confirm provider terms + jurisdictions before launch.
- **Body-positive framing carries over** — the generated image is styled with the same
  care rules (no "fixing"/"hiding"); Mira reacts kindly, never critically.
- This is the **premium hook** (see `docs/12-pricing-strategy.md`) — charging is fine,
  but the consent/safety bar is non-negotiable regardless of tier.
