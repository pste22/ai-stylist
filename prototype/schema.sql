-- ============================================================
--  Mira AI Stylist — Supabase Schema
--  Run once in: Supabase Dashboard → SQL Editor → New query → Run
--
--  Tables
--    users             identity + last-seen
--    user_preferences  style/budget preferences per user
--    user_history      per-user product interaction log
--    products          affiliate product catalog (replaces affiliate_products.json)
--    events            anonymous analytics events (replaces data/events.jsonl)
-- ============================================================

-- ------------------------------------------------------------
-- 1. USER IDENTITY
-- ------------------------------------------------------------
create table if not exists users (
  user_id    uuid        primary key,
  name       text        not null,
  first_seen timestamptz default now(),
  last_seen  timestamptz default now()
);

-- ------------------------------------------------------------
-- 2. USER PREFERENCES
-- ------------------------------------------------------------
create table if not exists user_preferences (
  user_id    uuid        primary key references users(user_id) on delete cascade,
  budget_min integer,
  budget_max integer,
  vibes      text[],
  body_notes text,
  -- Compatibility fields used by the existing web onboarding flow.
  style_vibe     text,
  shopping_focus text,
  top_size       text,
  bottom_size    text,
  budget         text,
  updated_at timestamptz default now()
);

-- Existing deployments may have been created before the web onboarding fields
-- existed. These are intentionally idempotent so this file remains safe to rerun.
alter table user_preferences add column if not exists style_vibe text;
alter table user_preferences add column if not exists shopping_focus text;
alter table user_preferences add column if not exists top_size text;
alter table user_preferences add column if not exists bottom_size text;
alter table user_preferences add column if not exists budget text;

-- ------------------------------------------------------------
-- 3. USER HISTORY (per-user product interaction log)
-- ------------------------------------------------------------
create table if not exists user_history (
  id           bigserial   primary key,
  user_id      uuid        references users(user_id) on delete cascade,
  product_id   text,
  product_name text,
  action       text,        -- 'shown' | 'would_buy' | 'buy_click' | 'wishlist'
  ts           timestamptz  default now()
);

create index if not exists idx_user_history_uid_ts
  on user_history(user_id, ts desc);

-- ------------------------------------------------------------
-- 4. PRODUCT CATALOG
--    source: 'curated' (manual SiteStripe) | 'amazon' (PA-API) | 'ltk' | 'local'
--    All monetary values in USD.
-- ------------------------------------------------------------
create table if not exists products (
  id            text        primary key,        -- ASIN for Amazon items, else slug
  source        text        not null default 'curated',
  asin          text,                           -- Amazon ASIN (may equal id)
  name          text        not null,
  category      text        not null,           -- dresses | bottoms | tops | outerwear | accessories | shoes
  color         text,
  price         numeric(10,2),
  style         text[]      default '{}',       -- e.g. {"casual","chic","everyday"}
  gender        text        not null default 'unisex',  -- women | men | unisex
  image_url     text,
  affiliate_url text,
  partner_tag   text,                           -- Amazon associate tag used when url was built
  is_active     boolean     not null default true,
  created_at    timestamptz default now(),
  updated_at    timestamptz default now()
);

-- Composite index: the most common filter is (category, gender) + price sort
create index if not exists idx_products_cat_gender
  on products(category, gender)
  where is_active;

-- GIN index for style array overlap queries (style && '{casual,chic}')
create index if not exists idx_products_style
  on products using gin(style)
  where is_active;

-- Price range scans
create index if not exists idx_products_price
  on products(price)
  where is_active;

-- Source-level listing (admin / refresh jobs)
create index if not exists idx_products_source
  on products(source)
  where is_active;

-- ------------------------------------------------------------
-- 5. EVENTS (anonymous analytics — replaces data/events.jsonl)
--    session_id is an ephemeral hex UUID minted per session (no PII).
--    user_id is optional — anonymous sessions have no user_id.
--
--    event types:
--      would_buy      shopper tapped "Would Buy" on a card
--      buy_click      shopper tapped "Buy →" (affiliate handoff)
--      session_cost   end-of-session LLM token/cost summary
-- ------------------------------------------------------------
create table if not exists events (
  id           bigserial   primary key,
  ts           timestamptz default now(),
  session_id   text        not null,
  user_id      uuid        references users(user_id) on delete set null,
  event        text        not null,
  product_id   text        references products(id) on delete set null,
  product_name text,
  -- session_cost fields (nullable; only set when event = 'session_cost')
  input_tokens  integer,
  output_tokens integer,
  cost_usd      numeric(10,6),
  -- catch-all for future event types without a schema migration
  meta          jsonb
);

-- Hot query: all events for a session (used by signals.py)
create index if not exists idx_events_session_ts
  on events(session_id, ts desc);

-- Hot query: per-user event history
create index if not exists idx_events_user_ts
  on events(user_id, ts desc)
  where user_id is not null;

-- Analytics: roll-up by event type + time
create index if not exists idx_events_type_ts
  on events(event, ts desc);

-- ------------------------------------------------------------
-- 6. EVENT EDITS + COMPLETE LOOKS
--    An event brief captures the shopper's practical constraints before Mira
--    recommends a complete outfit. Looks only reference products in our catalog,
--    preserving the affiliate-grounding guarantee.
-- ------------------------------------------------------------
create table if not exists event_briefs (
  id           uuid        primary key default gen_random_uuid(),
  user_id      uuid        references users(user_id) on delete set null,
  session_id   text,
  occasion     text        not null,
  event_date   date,
  location     text,
  dress_code   text,
  vibe         text,
  budget_max   numeric(10,2),
  constraints  text,
  status       text        not null default 'ready',
  created_at   timestamptz default now()
);

create index if not exists idx_event_briefs_user_created
  on event_briefs(user_id, created_at desc)
  where user_id is not null;

create table if not exists looks (
  id             uuid        primary key default gen_random_uuid(),
  event_brief_id uuid        references event_briefs(id) on delete cascade,
  user_id        uuid        references users(user_id) on delete set null,
  name           text        not null,
  rationale      text        not null,
  total_price    numeric(10,2),
  -- Snapshot keeps an Event Edit recoverable even when a merchant later removes
  -- a product from its active feed.
  items          jsonb       not null default '[]'::jsonb,
  is_saved       boolean     not null default true,
  created_at     timestamptz default now()
);

alter table looks add column if not exists items jsonb not null default '[]'::jsonb;
alter table looks add column if not exists is_saved boolean not null default true;

create table if not exists look_items (
  look_id     uuid        references looks(id) on delete cascade,
  product_id  text        references products(id) on delete restrict,
  category    text        not null,
  sort_order  integer     not null,
  primary key (look_id, product_id)
);

-- ============================================================
--  ROW-LEVEL SECURITY
--  products + events are read-only from the browser (anon key).
--  Writes come only from the backend (service-role key).
-- ============================================================
alter table products enable row level security;
alter table events   enable row level security;
alter table users    enable row level security;
alter table user_preferences enable row level security;
alter table user_history     enable row level security;
alter table event_briefs     enable row level security;
alter table looks            enable row level security;
alter table look_items       enable row level security;

-- Anyone can read active products (needed if we ever add a public API)
drop policy if exists "public read active products" on products;
create policy "public read active products"
  on products for select
  using (is_active = true);

-- Service role bypasses RLS automatically — no explicit policy needed for writes.

-- ============================================================
--  HELPER: auto-update products.updated_at on row change
-- ============================================================
create or replace function set_updated_at()
  returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_products_updated_at on products;
create trigger trg_products_updated_at
  before update on products
  for each row execute function set_updated_at();
