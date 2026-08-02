# Mira — Backlog

Open items, grouped by priority. Newest context at time of writing: 2026-08-02.
Shipped recently (for reference): multi-angle try-on, spin + curated scene videos,
share card, reusable photo, Size Advisor, My Fitting Room (memory + gallery +
compare), Stage 0 hardening, content-hash cache, enforced spend caps, `/health`.

---

## 🚦 Launch gate (panel review 2026-08-02: GTM · presales · architect)

**Verdict: NO-GO today → CONDITIONAL GO after the non-negotiables (~2–3 focused days).**
Product magic is real and (over-)built; the *launch* isn't ready — flying blind
(no analytics/alerting) with a confirmed data hole. Lead all messaging with the
**virtual try-on** ("see it on you before you buy"), not "AI stylist."

**3 technical non-negotiables (architect — must fix before real strangers):**
- [x] **Supabase RLS policies** — RLS was on with NO policies → data exposure/breakage
      via the public anon key. Fix written: `prototype/migrate_rls_policies.sql`
      (owner-scoped `auth.uid()` policies for all user + chat tables).
      **→ ACTION: apply it in Supabase SQL editor, then verify cross-account isolation.**
- [ ] **Observability + alerting** — put an external uptime monitor + spend alert on
      `/health` (UptimeRobot/BetterStack) + a Google Cloud billing budget alert.
      Can't launch blind with real money.
- [ ] **Rotate Gemini key → your own billed secret** (also de-risks demos; the `AQ.…`
      token's billing isn't yours to hard-cap).

**GTM P0 (before public flip-on):**
- [x] **OG/Twitter meta tags** on `index.html` — done. **→ ACTION: add a real
      `web/public/og-cover.jpg` (1200×630)**; per-try-on dynamic OG later.
- [ ] **Product analytics + 5 funnel events** (activation, try-on completion,
      click-out/affiliate CTR, share rate, referral-visit) — PostHog/Plausible.
      Can't learn from launch without it.
- [ ] **Affiliate click-out tracking/attribution** — count every retailer click-out
      (proves intent to networks, measures CTR, needed for Amazon's 3-sale unlock).
- [ ] **Gate first PAID generation behind sign-in** + near-cap alert — anonymous
      guest video gen is a cost-DoS vector.
- [ ] **Manual catalog freshness sweep** of surfaced products; confirm the "AI
      preview, not exact fit" label is on every output + the share card.

**Demo prep (presales — before any live demo):** pre-generate the demo look (cache
hits = instant), record a full-flow fallback video, set `min_machines_running=1`
for demo week (or warm via `/health`+one try-on), lock one photo+product combo that
renders cleanly, raise spend-cap env for rehearsal.

**Do NOT block launch on:** broader affiliate networks, Amazon PA-API, men's catalog,
automated availability cron (manual sweep ok), Stage-1 scale, dynamic OG images,
voice-mode polish.

---

## 🔴 Before real launch (security / ops)

- [ ] **Rotate `GEMINI_API_KEY` → Codespaces secret.** Current key is an `AQ.…`
      OAuth/gateway token (not a normal `AIza…` key). Create your own key at
      aistudio.google.com/apikey with billing you control, add it as a Codespaces
      secret, remove it from `prototype/.env`. The server's startup `🔑` diagnostic
      confirms the source. (Claude can swap + verify once you paste a new key.)
- [ ] **Verify Supabase RLS is enforced.** The anon key is public by design (it's
      in the client bundle / fly.toml build args) — Row-Level Security is the only
      guard on user data. Confirm RLS policies exist on all user tables.
- [ ] **`fly.toml`: `min_machines_running = 0 → 1`.** Kills cold starts and gives
      voice sessions a stable home. Tradeoff: one always-on machine (cost).

## 🟠 Scale (when traffic grows — chief-architect Stage 1/2)

- [ ] **Media → object storage + CDN.** Stop sending generated images/videos as
      base64 over the WebSocket; write to Supabase Storage / S3 / R2, return signed
      URLs, let the browser fetch from CDN. Removes the biggest per-job memory spike
      + offloads bandwidth. (Biggest single scale win.)
- [ ] **Job queue + worker pool for generation.** Decouple try-on/video from the
      WS lifecycle (enqueue → workers → notify with URL). Survives client
      disconnects, enables retry/resume, scales gen independently.
- [ ] **Split the stateful voice service from stateless gen/API** (opposite scaling
      shapes; so gen deploys/restarts don't drop voice sessions).
- [ ] **Move catalog out of per-process memory** to a shared store (Supabase/Redis)
      so machines don't each hold ~5000 items and updates don't need a redeploy.
- [ ] **Per-project Google quota management / request governor** as Veo volume grows.
- Done already (not backlog): content-hash cache, enforced per-user/global spend
  caps + kill switch, isolated generation pool, retry/backoff/circuit-breaker.

## 🚀 Pre-live blockers (data/sourcing)

- [ ] **Daily product availability re-sync cron.**
- [ ] **Amazon PA API** integration (unlocks after 3 qualifying sales).
- [ ] **INR price re-seeding.**

## 👗 Product / features

- [ ] **Size Advisor precision** — parse brand/product size charts where available;
      later a measurement-from-photo sizing API (3DLOOK / Bold Metrics) for real
      accuracy. (MVP heuristic already shipped.)
- [ ] **Fit tip on product grid cards** (currently only in try-on + quick-view).
- [ ] **Try-on reveal polish** — anticipation states instead of a plain spinner;
      cross-fade angle transitions (specialist quick wins).
- [ ] **Men's catalog seeding** (only ~2 men's products currently).
- [ ] **pgvector semantic search** — `generate_embeddings.py` +
      `migrate_vector_search.sql` are ready; run embeddings, then wire
      `vector_search()` for "similar to X" queries.
- [ ] **Fitting Room cloud sync** (opt-in, cross-device) — deferred; breaks the
      "on this device only" privacy line, needs auth. Only if users ask.

## 💼 Business / affiliate

- [ ] **VCommission** — awaiting publisher-access reply; if no/poor fit, evaluate
      **Cuelinks** (publisher-side aggregator: Myntra/Ajio/Nykaa/Tata CLiQ).

## 🧪 Testing

- [ ] **Network test mode** — low-data auto-switch was built earlier but never
      tested end-to-end by the user.
