# 05 — Tech Stack (free-first)

🟢 free · 🟡 free tier / cheap · 🔴 likely paid eventually

## Architecture
```
[Mobile/Web App]
   │  WebRTC audio
   ▼
[Voice Orchestrator]  ← wires STT → LLM → TTS, handles interruptions
   ├─ STT (speech→text, streaming)
   ├─ LLM (understands + recommends)
   ├─ TTS (text→voice, streaming)
   ├─ Product Search (multi-source)
   └─ Avatar (hand-drawn character)
```

## Recommended "$0 to start" combo

| Layer | Pick | Cost |
|-------|------|------|
| Pipeline | **Pipecat** (open source) | 🟢 |
| Transport | **LiveKit** (self-host WebRTC) | 🟢 |
| STT | **faster-whisper** (local) / Deepgram credits | 🟢 / 🟡 |
| LLM | **Groq free tier** (fast!) / **Ollama** local | 🟡 / 🟢 |
| TTS | **Kokoro / Piper** local; **XTTS** for custom voice | 🟢 |
| Avatar | **Rive** or **Live2D** (2D, lightweight) | 🟢 |
| Products | **FakeStoreAPI/DummyJSON** now → affiliate APIs later | 🟢 |
| App | **Expo (React Native)** | 🟢 |
| Hosting | **Fly.io / Railway / Render** (edge, free tiers) | 🟢 |

## Notes
- **Don't build WebRTC yourself** — Pipecat/LiveKit give realtime transport for free.
- **Character voice = core IP** — craft it free with XTTS, upgrade to 🔴 ElevenLabs only
  if quality gates the demo.
- **Groq** is a big latency win on the free tier — good fit for voice.
- **Gemini Live** could collapse STT+LLM+TTS into one realtime box (🟡 free tier) — worth a spike.
- **Product sourcing:** use official/affiliate APIs, **never scrape** (legal + brittle).
