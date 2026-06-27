# 12 — Pricing Strategy

**Status:** Direction set, pricing deferred until PMF (2026-06-27) · **Owner:** Founder

---

## The cost shape (why this is different from normal SaaS)
Cost is **variable and usage-driven**: Gemini Live audio in/out + reasoning tokens cost
real money every session. Heavy users cost more. A naive "free & unlimited" plan means we
**subsidize our heaviest users** — token cost can spike faster than revenue.

Pricing job: **(1) cap downside on heavy users, (2) capture upside from users who get value.**

---

## Two revenue engines (ours is unusual)
Unlike most AI apps, we have **affiliate commission** alongside any subscription:

```
            ┌── 💰 Affiliate commission ── cost happens WHEN revenue happens (aligned)
 User ──────┤
            └── 💳 Subscription ────────── covers token cost of users who chat but don't buy
```

Key insight: **a buying user can be profitable even on the free tier** — their commission
can exceed their token cost. The risk case is the **high-engagement, low-purchase** user.
Pricing must protect against exactly that one.

---

## Recommended model: freemium with a usage meter

| Tier | What they get | Why it works |
|---|---|---|
| **Free** | ~5–10 styling sessions / month, full Mira | Lets people fall in love; affiliate covers buyers; cap limits token bleed |
| **Plus (subscription)** | High/unlimited sessions, cross-time memory, always-on Mira | Power users + non-buyers pay for the cost they create |
| **Affiliate (all tiers)** | Buy links always work | Revenue aligned: we earn when they shop, on any tier |

Meter in **human units** (sessions / outfits / conversations), NOT tokens. Users
understand "5 styling chats a month"; they don't understand "200K tokens." We absorb the
token complexity.

---

## Cost levers (cut the curve before raising prices)
- **Lean context** — keep grounding to ~8 curated products + compact prompt lines; never
  dump the whole catalog every turn.
- **Tiered models** — cheap/fast model for chit-chat + mode-sensing; premium model only
  for real styling reasoning.
- **Graceful session caps** — Mira warmly wraps up ("save this and pick up later?")
  instead of infinite open mic.
- **Prompt caching** — the persona system prompt is identical every call; cache it where
  the provider supports it.

---

## Sequence (what we actually do)
1. **Don't price yet.** Pre-PMF, pricing is a distraction. Stay free.
2. **Instrument cost-per-session NOW** (backlog card) so we know real unit economics
   before charging. Pair *cost* data with *intent* data (P2-8 would-buy signal).
3. **If purchase-rate is high enough** → affiliate alone may fund it; possibly never need
   a subscription (dream: free for users, paid by retailers).
4. **If engagement >> purchase** → introduce free session cap + Plus tier to stop
   subsidizing chatters.

---

## Virtual try-on (VTO) — the premium hook
Voice chat is the core loop and is hard to gate (gating it hurts the relationship). VTO is
the opposite: high perceived value, real per-image compute cost, and clearly *optional* —
the ideal thing to charge for (cost and revenue move together).

- **Lean: make VTO the flagship reason to buy Plus** — a concrete "I want that" upgrade
  hook, stronger than "unlimited chats."
- **Free taste (1–2 try-ons)** so everyone feels the magic, then cap → convert. Never gate
  before they've felt it; the free taste is the conversion engine.
- Alternative structure: **credits / pay-per-use** if usage is spiky and price should
  track compute exactly.
- Two clean, non-overlapping engines: **affiliate funds free users; VTO funds Plus.**
- See P5-1 in `docs/06-backlog.md`; privacy/consent guardrails in `docs/09-...` §7.

---

## North-star call
**"Free for the user, paid by the retailer" (affiliate-funded)** is the strongest position
and matches our trust-first brand ("I'm not charging you to shop"). The **subscription is
the safety net** for when token cost outruns commission — not the primary engine. Decide
which leads only after measuring real cost-per-user vs. purchase-rate.

---

## Decision log
| Date | Decision | Rationale |
|---|---|---|
| 2026-06-27 | Defer pricing until PMF | Pre-PMF pricing is a distraction; need real cost + intent data first |
| 2026-06-27 | North-star = affiliate-funded, free to user | Strongest position; matches trust-first brand |
| 2026-06-27 | Subscription = safety net, metered in human units | Protects against high-engagement / low-purchase users |
| 2026-06-27 | Instrument cost-per-session before charging | Can't price without unit economics |
| 2026-06-27 | VTO = flagship premium hook (Plus or credits), with free taste | Optional + high-value + real compute cost = ideal paid feature; gating it doesn't hurt the core loop |
