# 03 — Roadmap

Each phase = **one runnable, demo-able thing**. Never a 3-month dark tunnel.
Every phase ends in a **decision gate**.

---

## 🔹 Phase 1 — "Can it talk fast?" (Latency spike)
**Goal:** Prove a sub-1s, interruptible voice loop on a real mobile network.
- Pipecat + Groq + local STT/TTS, minimal UI, **hardcoded product list**.
- Test on throttled 3G/4G — **not** WiFi.
- **Success metric:** < 1s perceived response; survives a 5-min chat without feeling broken.
- **Decision gate:** If latency can't get acceptable → rethink before investing further.

## 🔹 Phase 2 — "Does it feel magical?" (Persona + taste)  ⭐ Investor demo
**Goal:** A character people *want* to talk to, giving opinionated style advice.
- Avatar (Rive/Live2D), signature voice, thinking animations, personality.
- LLM tuned for styling POV (asks good questions, recommends 3 with reasons).
- **Success metric:** 5–10 testers say "I'd talk to this again" / show emotional reaction.

## 🔹 Phase 3 — "Real products" (Sourcing)
**Goal:** Replace fake catalog with real, multi-source clothing via affiliate APIs.
- Start with 1 affiliate source, then add a second.
- Preference memory: body, budget, vibe, past likes.
- **Success metric:** Recommends real, buyable, relevant items; checkout handoff works.

## 🔹 Phase 4 — "Do they come back?" (Retention)
**Goal:** Turn a demo into a habit.
- Cross-session memory, "remember last time," re-engagement, accounts.
- **Success metric:** % returning within 7 days; conversations per user.

---

## ❌ Explicitly NOT in v1 (the power of "not yet")
- Payments/checkout in-app (use affiliate handoff)
- 3D avatar (2D is cheaper and on-brand)
- Multiple languages
- AR / virtual try-on
- Scaling/infra optimization
- Accounts/login (until Phase 4)

---

## 🗓️ Cadence (solo founder)
- **Weekly:** one measurable outcome, not a task list.
- **Bi-weekly:** something demo-able to show a real person.
- **Track 3 numbers only:** latency, "would use again" %, 7-day return rate.

---

## 📈 Success metrics ladder (what investors ask)
1. Latency < 1s ✅ (technical credibility)
2. 70%+ testers say "I'd use again" (emotional pull)
3. Real recommendations converting to clicks (commercial signal)
4. 7-day return rate climbing (retention = the real story)
