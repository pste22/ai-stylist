# Mira — Launch & Ops Runbook

Account/ops steps that need YOUR logins (code is done; these can't be automated).
See `BACKLOG.md` → "Launch gate" for the full checklist.

## 1. Gemini billing (stop the mid-session "credits depleted" wall)
The generation features (try-on images + Veo videos) run on the Google Gemini API.
Prepaid credits deplete fast because **video is the expensive part** (see costs below).

- **Switch to pay-as-you-go / auto top-up** (not a one-off prepay balance):
  Google AI Studio → your project → **Billing** → enable a linked Cloud Billing
  account so it charges as you go instead of draining a fixed prepay.
- **Set a Google Cloud budget alert** (Cloud Console → Billing → **Budgets & alerts**):
  e.g. alert at 50% / 90% / 100% of a monthly cap so you're warned, never walled.
- **Own the key:** create your own `AIza…` key with billing you control (the current
  `AQ.…` gateway token's billing isn't yours to cap). Put it in Codespaces secrets /
  `.env` as `GEMINI_API_KEY`. The server prints its key source at startup (`🔑`).

### What generation costs (verify at ai.google.dev/pricing)
| Action | Generates | ~Cost |
|---|---|---|
| Try-on, front only | 1 image | ~€0.04 |
| Try-on, 3 angles | 3 images | ~€0.12 |
| Spin / scene video — **Lite** (default) | 1 clip (~8s) | **~€0.30–0.40** |
| Spin / scene video — Fast | 1 clip (~8s) | ~€1.20 |
| Spin / scene video — Quality | 1 clip (~8s) | ~€1.60–3.20 |

### Cost controls already in the app (env-tunable)
- `GEMINI_VEO_MODEL` — default `veo-3.1-lite-generate-preview` (cheapest). Bump to
  `veo-3.1-fast-generate-preview` / `veo-3.1-generate-preview` for a premium tier.
- `MIRA_GEN_DAILY_USER_USD` (default 1.5) / `MIRA_GEN_DAILY_GLOBAL_USD` (default 15) —
  enforced daily spend caps. Demo / founder emails in `MIRA_DEMO_EMAILS`
  (default `pste22@gmail.com`) skip the per-user cap so a live walkthrough
  isn't killed after ~3 videos; they still count toward the studio-wide ceiling.
- `MIRA_GEN_DISABLED=1` — kill switch: pause ALL generation instantly.
- Content-hash cache: identical photo+item+view/scene never re-bills.
- Video is opt-in only (user taps ✨ Spin), gated behind sign-in.
- Watch live spend at `GET /health` (`spend_today_usd`, `cache_*`, `gen_circuit_open`).

## 2. Supabase — apply RLS (data-security launch blocker)
Apply `prototype/migrate_rls_policies.sql` in Supabase → SQL editor.
**Verify:** sign in as account B, try to read account A's rows without a filter → 0 rows.
Also add redirect URL for OAuth: Auth → URL Configuration → Redirect URLs →
`https://*.app.github.dev/**` (covers the Codespace domain).

## 3. Analytics — turn PostHog on
Create a free PostHog project (EU region), then set in the build env:
`VITE_POSTHOG_KEY=phc_…` (and optional `VITE_POSTHOG_HOST`). Events are already wired
(activation, try-on completion, click-out, share). No key = safe no-op.

## 4. Observability — alerting
Point UptimeRobot / BetterStack at `/health` (alert on non-200 + when
`spend_today_usd` nears the cap). The Cloud budget alert (step 1) is the money backstop.

## 5. Share card image
Add `web/public/og-cover.jpg` (1200×630) so shared links render a rich preview
(OG tags already in `index.html`).

## 6. Before real traffic (fly.toml)
Set `min_machines_running = 1` (kills cold starts / stable voice) — small always-on cost.
