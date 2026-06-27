# 14 — UI Strategy

**Status:** Decided (2026-06-27) · **Phase:** 2 (P2-3) · **Owner:** Founder

How Mira shows up to users — chosen for **maximum "alive" feeling per unit of build
effort** (solo founder, pre-PMF, free-first).

---

## Decision 1 — App shell: **Web app (Vite + React)**
A shareable URL beats an installable app pre-PMF:
- ✅ Fastest to build and demo; "send a link" = our P2-7 user testing.
- ✅ Runs everywhere; Gemini Live + WebRTC work in-browser.
- ✅ No app-store friction.
- ⚠️ Mic permissions / mobile polish need care — acceptable tradeoff.

Native mobile (Swift/Kotlin/RN/Flutter) is a **Phase 4+** concern, not now.

---

## Decision 2 — Avatar: static Mira now, **Rive** as the target (P2-3)
"Efficient enough" matters most here. Options cheapest → richest:

| Approach | Effort | Alive factor | Verdict |
|---|---|---|---|
| Static image + talking pulse | Tiny | Low–Med | **v1 — ship this first** |
| Lottie / sprite states | Low | Medium | Fine interim |
| **Rive** ⭐ | Low–Med | High | **Target** — state machine, tiny, free, web-native |
| Live2D | Med–High | Very high | Later; heavier rig + licensing |
| 3D / video | High | Highest | Icebox |

**The magic is voice + personality (already built). The avatar's only job is to not break
the spell.** A beautiful, responsive static image gets ~80% of the feeling for ~10% of the
effort. Rive is the natural step-up once the loop works.

---

## The key idea — brain states drive avatar states
We already have the signals; the avatar just renders them:

```
Brain state                         Avatar state
-----------------------------------  -----------------
idle / waiting for input        ──▶  idle (gentle breathing)
backchannel() emitted (P2-4)    ──▶  thinking (eyes up, slight tilt)
reply_stream() streaming        ──▶  talking (mouth/pulse animates)
mood = excited / low (P2-5)     ──▶  reacting (smile / soft concern)
```

This mapping is why Rive fits: its state machine takes exactly these inputs. The web shell
exposes a single `avatarState` that the voice/brain layer sets.

---

## Sequencing (don't boil the ocean)
1. **Web shell + state-driven placeholder Mira** (this commit).
2. Wire Gemini Live voice in-browser → drive `avatarState` from real events.
3. Replace placeholder with real character art (gated on the P2-1 "look").
4. Upgrade placeholder → Rive state machine.
5. Polish per user feedback.

---

## Open dependency
Mira's **visual identity** (the "look" half of P2-1) gates everything visual. We can demo
the *interaction* with a placeholder, but real character art is what makes people fall in
love — that's a design/illustration task to commission next.

---

## Decision log
| Date | Decision | Rationale |
|---|---|---|
| 2026-06-27 | Web app (Vite+React) shell | Shareable link, fastest demo, browser voice works |
| 2026-06-27 | Avatar: static→Rive, defer Live2D/3D | Best alive-feeling per effort; Rive state machine maps to brain states |
| 2026-06-27 | Brain states drive a single `avatarState` | Clean seam between brain and visuals; future-proofs the Rive upgrade |
