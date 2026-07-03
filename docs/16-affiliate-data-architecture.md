# 16 — Affiliate Data Architecture

> **TL;DR** All product catalog and event data lives in Supabase (Postgres).
> Reads are served from a full in-memory cache (sub-millisecond, zero DB hits at scale).
> Writes are async, batched, and non-blocking. At 10K users/day the total Supabase
> cost is **$0/month** — well within the free tier — and the design scales cleanly
> to 1M users/day with one infrastructure upgrade (external Redis, read replicas).

---

## 1. Problem Statement

| Constraint | Detail |
|---|---|
| Target scale | 10K users/day (~0.12 req/s average, ~1–2 req/s peak) |
| Read SLO | < 5 ms per product search (voice pipeline, latency-critical) |
| Write SLO | < 30 s eventual consistency (events/analytics — slow is fine) |
| Budget | $0/month until revenue (Supabase free tier) |
| Data types | Product catalog (small, slow-changing) + analytics events (high-write) |

---

## 2. Architecture Overview

```
┌───────────────────────────────────────────────────────────────────────┐
│                        Voice Pipeline (Gemini Live)                   │
│                        Stylist Brain (Groq LLM)                       │
└───────────────────────┬───────────────────────────┬───────────────────┘
                        │ search()                  │ log_event()
                        ▼                           ▼
          ┌─────────────────────┐       ┌─────────────────────┐
          │   PRODUCT STORE     │       │   EVENT STORE       │
          │                     │       │                     │
          │  ┌───────────────┐  │       │  ┌───────────────┐  │
          │  │ In-memory     │  │       │  │ In-process    │  │
          │  │ Catalog Cache │  │       │  │ deque queue   │  │
          │  │ (TTL 5 min)   │  │       │  └──────┬────────┘  │
          │  └──────┬────────┘  │       │         │ async     │
          │  miss / │ expired   │       │         │ flush     │
          │         ▼           │       │         ▼           │
          │  ┌───────────────┐  │       │  ┌───────────────┐  │
          │  │  Supabase     │  │       │  │  Supabase     │  │
          │  │  products     │  │       │  │  events       │  │
          │  │  table        │  │       │  │  table        │  │
          │  └───────────────┘  │       │  └───────┬───────┘  │
          └─────────────────────┘       │          │ fallback │
                                        │  ┌───────▼───────┐  │
                                        │  │ events.jsonl  │  │
                                        │  └───────────────┘  │
                                        └─────────────────────┘
```

---

## 3. Product Catalog — Fast Fetch Design

### 3.1 Why in-memory?

The product catalog is:
- **Small**: 9–2,000 items (even at 2K items, the full catalog fits in ~2 MB of RAM)
- **Slow-changing**: updated at most a few times per day (new affiliate items, price updates)
- **Read-heavy**: every product search (5–10 per session × 10K sessions) hits the catalog

The fastest possible read is a Python `for` loop over a list already in RAM.
No network, no serialisation, no connection pool — sub-millisecond at 2K items.

### 3.2 Cache strategy

```
                      ┌─────────────────────────────┐
Startup               │  Cold-start: load from DB   │  ~ 200ms once
                      └──────────────┬──────────────┘
                                     │
                      ┌──────────────▼──────────────┐
All requests          │  Serve from in-memory list  │  < 1ms always
                      └──────────────┬──────────────┘
                                     │ every 4 min (background thread)
                      ┌──────────────▼──────────────┐
                      │  Refresh from Supabase       │  ~ 200ms, non-blocking
                      └─────────────────────────────┘
```

- TTL: **5 minutes** (products change at most a few times a day; 5 min is safe)
- Refresh ratio: **0.8** (refresh at 4 min, before the TTL expires → no cache miss for users)
- Background thread: daemon thread, never blocks a request
- Fallback: if Supabase is unreachable at startup, load from `affiliate_products.json`

### 3.3 In-memory search

Filtering is done in pure Python — no SQL, no network:

```python
for product in catalog:        # O(n) but n ≤ 2000, cost ~ 1 µs/item
    if category and product["category"] != category: continue
    if gender and ...: continue
    if max_price and ...: continue
    if style_set and not overlap: continue
    results.append(product)
```

At 2,000 products the full scan takes ~2 ms.  At 10K products ~10 ms.  Still
within the 5 ms voice-pipeline budget for realistic catalog sizes.

**When to switch to DB-side search**: when catalog grows beyond ~50K items.
At that point, add `pg_trgm` + full-text search on the Supabase `products` table.

### 3.4 Supabase query cost at 10K users/day

| Event | Supabase calls |
|---|---|
| Server startup | 1 read (full catalog load) |
| Background refresh | 288 reads/day (1 every 5 min) |
| Per-user product search | **0** (served from cache) |
| Product admin update | 1 write per item changed |
| **Total** | **~290 reads/day** |

Supabase free tier: no hard limit on reads. This is effectively zero cost.

---

## 4. Event Analytics — Async Write Design

### 4.1 Why async?

The voice pipeline has a strict latency budget.  A synchronous Supabase HTTP
write (~100–300 ms) would add audible lag to every "Would Buy" tap.  The
solution: enqueue the event in a Python `deque` (GIL-protected, < 1 µs) and
let a background thread flush to Supabase every 30 seconds.

### 4.2 Flush strategy

```
User taps "Would Buy"
        │
        ▼
  deque.append(record)    ← non-blocking, < 1 µs
        │
        │  if len(queue) >= 100 → trigger early flush
        │
  Background thread (every 30 s)
        │
        ▼
  _flush(): drain up to 100 events → Supabase batch INSERT
        │
        │  on Supabase error
        ▼
  JSONL append (synchronous, local disk)   ← never lose an event
```

### 4.3 Cost analysis at 10K users/day

```
10,000 sessions × 5 events/session = 50,000 events/day
Batch size = 100
Supabase INSERT calls = 50,000 / 100 = 500 calls/day

At Supabase free tier (no explicit rate limit):
  500 calls/day × 200 ms/call = 100 s of total network time spread across 24 h
  → negligible
```

### 4.4 Durability guarantee

Events are **never lost**:
1. Supabase insert succeeds → done.
2. Supabase insert fails → written to `data/events.jsonl` (local disk).
3. JSONL can be re-ingested later via `event_store.migrate_jsonl_to_supabase()`.

---

## 5. Database Schema

### products

| Column | Type | Notes |
|---|---|---|
| `id` | text PK | ASIN for Amazon items, slug for others |
| `source` | text | `curated` / `amazon` / `ltk` / `local` |
| `asin` | text | Amazon ASIN (may equal `id`) |
| `name` | text | Display name |
| `category` | text | dresses / bottoms / tops / outerwear / accessories / shoes |
| `color` | text | |
| `price` | numeric(10,2) | USD |
| `style` | text[] | e.g. `{casual,chic,everyday}` |
| `gender` | text | women / men / unisex |
| `image_url` | text | |
| `affiliate_url` | text | SiteStripe / PA-API link |
| `partner_tag` | text | Amazon Associates tag used when link was built |
| `is_active` | boolean | Soft-delete (never hard-delete, preserves FK integrity) |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | auto-updated by trigger |

**Indexes** (all `WHERE is_active`):
- `(category, gender)` — most common filter combo
- `GIN(style)` — array overlap queries `style && '{casual}'`
- `(price)` — price-range scans
- `(source)` — admin / refresh jobs

### events

| Column | Type | Notes |
|---|---|---|
| `id` | bigserial PK | |
| `ts` | timestamptz | event timestamp |
| `session_id` | text | anonymous 32-char hex UUID |
| `user_id` | uuid FK → users | nullable (anonymous sessions) |
| `event` | text | `would_buy` / `buy_click` / `session_cost` |
| `product_id` | text FK → products | nullable |
| `product_name` | text | denormalised for analytics convenience |
| `input_tokens` | integer | session_cost events only |
| `output_tokens` | integer | session_cost events only |
| `cost_usd` | numeric(10,6) | session_cost events only |
| `meta` | jsonb | catch-all for future event types |

**Indexes**:
- `(session_id, ts DESC)` — hot: all events for a session
- `(user_id, ts DESC)` — per-user history
- `(event, ts DESC)` — analytics roll-ups by type

---

## 6. Security

All tables have **Row-Level Security (RLS)** enabled:

| Table | Anon read | Anon write | Service-role |
|---|---|---|---|
| `products` | ✅ active only | ✗ | ✅ all |
| `events` | ✗ | ✗ | ✅ all |
| `users` | ✗ | ✗ | ✅ all |
| `user_preferences` | ✗ | ✗ | ✅ all |
| `user_history` | ✗ | ✗ | ✅ all |

The **service-role key** (`SUPABASE_SECRET_KEY`) lives only in the Python
backend — never in browser JS or the `.env.example`.  The browser only ever
sees the anon/public key (not yet exposed; no browser Supabase calls today).

---

## 7. ProductSource Hierarchy

```
PRODUCT_SOURCE= env var
    │
    ├── supabase  →  SupabaseProductSource   ← RECOMMENDED for production
    │                  (Supabase DB + in-memory cache)
    │                  fallback → CuratedAmazonSource → LocalJsonSource
    │
    ├── curated   →  CuratedAmazonSource
    │                  (data/affiliate_products.json)
    │                  fallback → LocalJsonSource
    │
    ├── amazon    →  AmazonSource
    │                  (PA-API live — requires 3 sales + API keys)
    │                  fallback → LocalJsonSource
    │
    └── local     →  LocalJsonSource
                       (data/products.json, demo/offline)
```

---

## 8. Scaling Roadmap

| Users/day | Architecture | Cost |
|---|---|---|
| < 10K (now) | In-memory cache + Supabase free | **$0/month** |
| 10K–100K | Add Redis (Upstash free 10K req/day or $10/mo paid) for shared cache across server instances | $0–10/mo |
| 100K–1M | Supabase Pro ($25/mo), read replica, connection pooler (PgBouncer built-in) | $25–50/mo |
| 1M+ | Dedicated Postgres + CDN for product images, event firehose (Kinesis/PubSub) | $200+/mo |

**Key insight**: the bottleneck at 10K–100K users is NOT the database — it's the
Python GIL (single-threaded async server) and the Gemini Live API quota.
The data layer is over-engineered for this scale by design, so it's never the
constraint.

---

## 9. Architectural Decision Records (ADRs)

### ADR-1: Full catalog in memory, not per-request DB queries

**Decision**: Load the entire active product catalog into a Python list at startup;
refresh in the background every 5 minutes.

**Rationale**: At < 50K products, an in-memory scan is faster than any database
query (no network, no parse, no connection pool overhead).  The catalog is small
and slow-changing — a 5-minute TTL is indistinguishable from real-time to users.

**Rejected alternative**: Per-request Supabase query with PostgREST.
Cost: 1 HTTP round-trip per search × 10 searches/session × 10K sessions = 100K
extra network calls/day.  Latency: +100–300 ms per search vs < 1 ms in-memory.

---

### ADR-2: Async fire-and-forget event writes, never blocking the voice pipeline

**Decision**: Events are enqueued to an in-process `deque`; a background thread
flushes to Supabase every 30 s or when the queue hits 100 events.

**Rationale**: The voice pipeline has a strict latency budget (~650 ms total).
A 200 ms synchronous Supabase write on every "Would Buy" tap would be noticeable
and degrade the experience.  Analytics events have no real-time requirement.

**Tradeoff accepted**: Up to 30 s of event lag before data appears in Supabase.
This is fine for analytics — we don't have real-time dashboards at this scale.

---

### ADR-3: JSONL fallback for event durability

**Decision**: If Supabase is unreachable during a flush, events are written
synchronously to `data/events.jsonl`.

**Rationale**: Events must never be silently dropped.  The JSONL file is the same
format we used before Supabase, and `migrate_jsonl_to_supabase()` can re-ingest
it at any time.

---

### ADR-4: Soft-delete products (`is_active=false`) instead of hard DELETE

**Decision**: Deactivating a product sets `is_active = false`; the row is never
deleted.

**Rationale**: The `events` table has a FK reference to `products.id`.
Hard-deleting a product would either cascade-delete historical events (data loss)
or orphan them with `ON DELETE SET NULL` (broken analytics).  Soft-delete
preserves full history at zero cost.

---

### ADR-5: Denormalise `product_name` into the events table

**Decision**: Every event stores `product_name` as a plain text column in addition
to `product_id`.

**Rationale**: Product names change (price corrections, title updates).  Analytics
queries like "most loved items" should reflect the name *at the time of the event*,
not today's name.  Denormalising avoids a JOIN and makes the `signals.py` queries
trivially simple.

---

## 10. Operations Runbook

### First-time setup

```bash
# 1. Run schema.sql in Supabase SQL Editor
# 2. Set env vars
export SUPABASE_URL=https://your-project.supabase.co
export SUPABASE_SECRET_KEY=your-service-role-key

# 3. Migrate existing data
cd prototype/
python migrate_products.py --dry-run          # preview
python migrate_products.py --migrate-events   # migrate products + events.jsonl

# 4. Switch to Supabase source
echo "PRODUCT_SOURCE=supabase" >> .env

# 5. Restart the server
python live_server.py
```

### Adding a new product

```python
from product_store import upsert_product
upsert_product({
    "id": "B0XYZ123",
    "source": "curated",
    "asin": "B0XYZ123",
    "name": "...",
    "category": "tops",
    "price": 29.99,
    "style": ["casual", "minimal"],
    "gender": "women",
    "affiliate_url": "https://amzn.to/...",
})
```

The catalog cache is invalidated immediately; the next request gets fresh data.

### Deactivating a product

```python
from product_store import deactivate_product
deactivate_product("B0XYZ123")   # soft-delete; historical events preserved
```

### Re-ingesting JSONL events after a Supabase outage

```python
from event_store import migrate_jsonl_to_supabase
n = migrate_jsonl_to_supabase()
print(f"Migrated {n} events")
```
