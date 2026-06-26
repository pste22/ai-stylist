# Phase 1 — Latency Spike Prototype

> Goal: prove a **sub-1s, interruptible** voice loop. Voice in → stylist reply out,
> recommending from a **hardcoded** product list. No avatar, no real products yet.
> This exists to **kill the latency risk** before any feature work.

## Architecture (Phase 1)
```
mic → STT (streaming) → LLM (Groq, streaming) → TTS (streaming) → speaker
                              │
                              └─ hardcoded product catalog (data/products.json)
```

## Quick start

### 1. Python env + deps
```bash
cd prototype
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Set your free API key
Groq has a generous free tier and is *fast* (great for latency).
Get a key at https://console.groq.com → then:
```bash
cp .env.example .env
# edit .env and paste your GROQ_API_KEY
```

### 3. Run the text-loop first (no audio, validates the brain + latency)
```bash
python text_loop.py
```
Type what a shopper would say; the stylist replies and recommends from the catalog.
This measures **LLM round-trip latency** in isolation before adding voice.

### 4. (Next) Voice loop
`voice_loop.py` is a Pipecat + local STT/TTS scaffold (see file header for the
remaining wiring — that's task **P1-2 / P1-4 / P1-5** on the board).

## Latency targets
- LLM text round-trip: **< 500ms** to first token (Groq usually hits this).
- Full perceived voice response: **< 1s**.
- Test on throttled 3G/4G, **not** WiFi (board task P1-8).

## Files
| File | Purpose |
|------|---------|
| `stylist.py` | The stylist brain: prompt + Groq call + catalog grounding |
| `catalog.py` | Loads + searches the hardcoded product list |
| `data/products.json` | ~20 sample clothing items |
| `text_loop.py` | Terminal chat loop + latency measurement (run this first) |
| `voice_loop.py` | Pipecat voice scaffold (STT→LLM→TTS) — to be completed |
| `requirements.txt` | Python deps |
