# Mira — Backlog

Open items, grouped by priority. Newest context at time of writing: 2026-08-02.
Shipped recently (for reference): multi-angle try-on, spin + curated scene videos,
share card, reusable photo, Size Advisor, My Fitting Room (memory + gallery +
compare), Stage 0 hardening, content-hash cache, enforced spend caps, `/health`.

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
