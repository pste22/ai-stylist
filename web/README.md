# Mira Web Shell

The browser UI for Mira (P2-3). See `docs/14-ui-strategy.md` for the strategy.

**Monorepo note:** this `web/` app is fully independent from the Python brain in
`prototype/` — its own deps, build, and deploy. They talk over an API (wiring next).

## Stack
- Vite + React (fast dev, shareable build)
- A CSS-animated **placeholder Mira** whose expression is driven by a single
  `avatarState` (idle / thinking / talking / reacting) — the seam where a **Rive**
  state machine drops in later.

## Run (two processes)
```bash
# 1) voice bridge (holds GEMINI_API_KEY, talks to Gemini Live)
.venv/bin/python prototype/live_server.py     # ws://localhost:8765

# 2) web UI
cd web && npm install && npm run dev          # http://localhost:5173
```
Click **Talk to Mira**, allow the mic, and speak. Mira's audio plays back and the
avatar state/mood update from real events. Override the bridge URL with
`VITE_MIRA_WS_URL`.

## What's here (v1)
- `src/avatarState.js` — canonical avatar states + moods (the brain↔UI contract).
- `src/Avatar.jsx` — placeholder face that renders the current state/mood.
- `src/audio.js` — mic capture (→16kHz PCM16) + gapless 24kHz playback.
- `src/useMiraVoice.js` — WebSocket client for the bridge; surfaces state/mood/captions.
- `src/App.jsx` — Talk-to-Mira UI wired to the live voice bridge.
- `public/mic-processor.js` — AudioWorklet that forwards mic frames.

Bridge: `prototype/live_server.py` (Gemini Live ⇆ browser).

## Next steps
1. Swap placeholder for real character art (gated on the P2-1 "look").
2. Upgrade placeholder → Rive state machine (same inputs).
3. Lip-sync the avatar to Mira's audio amplitude.
