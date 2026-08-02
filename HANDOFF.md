# Mira — Handoff (2026-08-02)

Snapshot for continuing work in **Cursor** (a VS Code fork — this repo runs there
identically). All code is pushed to `main` (`87fe3a9`). Working tree clean.

For the full picture see [BACKLOG.md](BACKLOG.md) (open items by priority) and
[LAUNCH.md](LAUNCH.md) (account/ops runbook).

---

## ⛔ #1 blocker — Gemini credits not reaching the app

Try-on/video generation is **currently down**: a live probe of the exact try-on
model (`gemini-2.5-flash-image`) returns `429 RESOURCE_EXHAUSTED — "prepayment
credits are depleted."** The €10 top-up is **not visible to the configured key**.

**Cause:** the app uses the `AQ.…` *gateway token* in `prototype/.env`. That
token's billing isn't the project you topped up. Credits added to your own Google
project don't reach it.

**Fix (account-side, ~5 min):**
1. [AI Studio → projects](https://ai.studio/projects) — find the project holding the €10.
2. In that project, create an API key (starts with `AIza…`).
3. Set `GEMINI_API_KEY=AIza…` in `prototype/.env` (replace the `AQ.…` value), restart server.
4. Verify with a cheap one-call probe (see "Verify credits" below) before spending more.
5. Then enable pay-as-you-go + a Cloud budget alert so you never hit the wall mid-session
   ([LAUNCH.md](LAUNCH.md) §1).

> Note: `prototype/.env` is gitignored — it is **not** in this repo. Recreate it in
> Cursor from your saved copy. Keys never travel via git.

### Verify credits
```bash
cd prototype && python - <<'PY'
import os; from dotenv import load_dotenv; load_dotenv(".env")
from google import genai; from google.genai import types
c = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
r = c.models.generate_content(model="gemini-2.5-flash-image",
    contents=["A plain flat-lay of a folded white t-shirt on a neutral background."],
    config=types.GenerateContentConfig(response_modalities=["IMAGE"]))
print("OK ✅" if r.candidates else "no image")
PY
```
`OK ✅` = credits work. `429 RESOURCE_EXHAUSTED` = wrong key/project.

---

## Recently shipped (latest first)
- **HD/Lite video toggle** (`87fe3a9`) — Veo defaults to **Lite** (`veo-3.1-lite`,
  ~€0.40/clip); HD (`veo-3.1-fast`, ~€1.20/clip) is opt-in per scene via a toggle in
  the try-on modal. Cost, cache key, and spend caps are all quality-aware.
- Veo cost economics corrected + spend caps tightened + Veo audio disabled.
- Try-on circular-JSON crash fixed (`onClick={start}` was passing the click event).
- Editorial full-bleed product grid (A2); Zara-style monochrome UI refresh.
- Fitting Room add-to-cart + compare columns.
- PostHog analytics + funnel events + sign-in gate for paid try-on.

## Open launch-gate items (not code — your logins; from BACKLOG.md / LAUNCH.md)
1. **Gemini key fix** (above) + pay-as-you-go + budget alert.
2. **Apply Supabase RLS** — run `prototype/migrate_rls_policies.sql` in the SQL editor,
   then verify cross-account isolation (sign in as B, can't read A's rows). Also add
   `https://*.app.github.dev/**` (and `http://localhost:5173/**` for local Cursor dev)
   to Supabase → Auth → Redirect URLs.
3. **PostHog key** — set `VITE_POSTHOG_KEY=phc_…` (no key = safe no-op).
4. **Uptime + spend alerting** on `/health` (UptimeRobot/BetterStack).
5. **`web/public/og-cover.jpg`** (1200×630) for rich share previews.
6. **`min_machines_running = 1`** in `fly.toml` before real traffic.

## Run locally
```bash
# backend
cd prototype && pip install -r requirements.txt && python live_server.py   # ws :8765, /health
# frontend
cd web && npm install && npm run dev                                        # :5173 (proxies /mira-ws,/api → :8765)
```
Health check: `curl localhost:8765/health` → `spend_today_usd`, `gen_disabled`, cache stats.

## Two wallets — don't confuse them
- **Cursor credits (~$460):** pay Cursor's coding assistant (writes code for you).
- **Google Gemini credits:** pay the app's *runtime* (try-on images + Veo video).
Cursor credits do **not** fund app generation.
