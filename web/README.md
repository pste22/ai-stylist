# Mira Web Shell

The browser UI for Mira (P2-3). See `docs/14-ui-strategy.md` for the strategy.

**Monorepo note:** this `web/` app is fully independent from the Python brain in
`prototype/` — its own deps, build, and deploy. They talk over an API (wiring next).

## Stack
- Vite + React (fast dev, shareable build)
- A CSS-animated **placeholder Mira** whose expression is driven by a single
  `avatarState` (idle / thinking / talking / reacting) — the seam where a **Rive**
  state machine drops in later.

## Run
```bash
cd web
npm install
npm run dev      # opens http://localhost:5173
```

## What's here (v1)
- `src/avatarState.js` — canonical avatar states + moods (the brain↔UI contract).
- `src/Avatar.jsx` — placeholder face that renders the current state/mood.
- `src/App.jsx` — demo harness to drive states by hand (real Gemini Live voice
  events replace the buttons next).

## Next steps
1. Wire Gemini Live voice in-browser → set `state`/`mood` from real events.
2. Swap placeholder for real character art (gated on the P2-1 "look").
3. Upgrade placeholder → Rive state machine (same inputs).
