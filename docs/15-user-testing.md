# 15 — User Testing (P2-7)

Goal: put Mira in front of **5–10 real people** and learn two things fast:

1. **Does the magic land?** — does talking to Mira feel like a stylist who *gets* them
   (warm, tasteful, alive), not a chatbot reading a catalog?
2. **Is there pull?** — would they use it again, and would they actually buy?

Small-n qualitative. We're hunting for strong signals and quotes, not statistics.

---

## Before each session (setup)
- [ ] Both processes running: `.venv/bin/python prototype/live_server.py` + `cd web && npm run dev`.
- [ ] Headphones for the tester (clean mic, no echo / self-barge-in).
- [ ] Quiet room. Mic permission granted in the browser.
- [ ] Fresh capture: each tester is a new browser session (new `session_id`).
- [ ] You take notes; don't coach. Let them struggle a little — that's data.

## Recruiting (who)
- 5–10 people who **shop for clothes online** and are comfortable talking out loud.
- Mix: a couple who love fashion, a couple who find shopping a chore. The chore-finders
  are the real test — Mira should make it *easier*, not more work.
- Avoid close friends if you can (they're too kind). Acquaintances > family.

---

## The session (~12–15 min)

### 1. Warm-up (1 min) — set them at ease
> "This is an early prototype of a voice stylist named Mira. Talk to her like a person —
> out loud, normally. There are no wrong answers; if something feels off, say so. I'll
> mostly stay quiet and watch."

Do **not** explain features. Discovery is part of the test.

### 2. First impression (1 min)
- Have them press **Talk to Mira** and just say hi.
- 👀 Watch their face on first hearing her voice. Note the reaction *before* they speak.
- Q: "First impression — who does she feel like?"

### 3. A real task (5–7 min) — pick ONE that's true for them
Use a scenario the tester actually has coming up (more honest than a fake one):
- "You've got an event soon — ask Mira to help you dress for it."
- "Find something you'd genuinely wear this week, under your normal budget."
- Let it wander. The point is a *real* styling conversation, not a script.

Watch for the moments that matter:
- Does she **ask a clarifying question** before recommending? (styling POV)
- Does she **read their mode** — efficient when they're brisk, warm when they open up?
- When picks appear as cards, do they **look** at them? Tap **Love it** unprompted?
- Any **"oh nice"** or smile? Any confusion or talking over her (barge-in)?

### 4. The pull questions (3 min) — ask verbatim, then shut up
1. "On a scale of 1–5, how likely are you to **use this again**? Why that number?"
2. "Would you have **bought** anything she showed you? Which, and what stopped you?"
3. "What did she get **right** about your taste? What did she get **wrong**?"
4. "If Mira disappeared tomorrow, would you **miss** her? (Sean Ellis must-have signal.)"
5. "What's the **one thing** you'd change?"

### 5. Wrap (30 sec)
- Thank them. Ask if you can follow up. Note anything they say *after* "we're done" —
  the unguarded line is often the truest.

---

## What to capture (per tester)
Keep it to one row each — a lightweight tally:

| Tester | Use-again (1–5) | Would-buy? | "Miss her?" (Y/N) | Best quote | Biggest friction |
|--------|-----------------|------------|-------------------|------------|------------------|
|        |                 |            |                   |            |                  |

Plus the automatic signal capture (no extra work): every **Love it** tap and session
cost lands in `data/events.jsonl`. After the round, run:

```bash
.venv/bin/python prototype/signals.py
```

→ sessions, would-buy taps per session, most-loved items, avg cost/session.

---

## Success bar (what "good" looks like for this round)
This is directional, not a launch gate:
- **≥ 40%** say they'd be **disappointed** without Mira ("would miss her") — the
  must-have threshold worth chasing.
- **≥ 1 would-buy tap per session** on average, *and* they can name what stopped them
  (tells us the Phase 3 checkout gap is the blocker, not taste).
- At least a few **unprompted** smiles / "oh nice" moments at her voice or a pick.

## Red flags to watch for
- They treat her like a search box (no conversation) → persona/voice isn't landing.
- They never look at the cards → recommendations feel disconnected from the talk.
- "It's cool but I wouldn't use it" with no buy intent → novelty, not need.

## After the round — turn notes into decisions
- Tag every friction by phase: persona (P2), recommendations (P2/P3), checkout (P3).
- The **#1 friction** becomes the next card in `docs/06-backlog.md` → Doing.
- Pull 2–3 verbatim quotes into the deck — quotes sell better than charts at this stage.

---

### Decision log
- 2026-06-27 — Script drafted. Pairs qualitative pull questions (use-again, would-buy,
  "would you miss her") with the automatic `would_buy` + `session_cost` capture, so each
  test produces both a story and a number. Signals reviewed via `prototype/signals.py`.
