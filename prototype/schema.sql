-- Mira user memory schema
-- Run once in: Supabase Dashboard → SQL Editor → New query → Run

create table if not exists users (
  user_id   uuid        primary key,
  name      text        not null,
  first_seen timestamptz default now(),
  last_seen  timestamptz default now()
);

create table if not exists user_preferences (
  user_id     uuid        primary key references users(user_id) on delete cascade,
  budget_min  integer,
  budget_max  integer,
  vibes       text[],
  body_notes  text,
  updated_at  timestamptz default now()
);

create table if not exists user_history (
  id           bigserial   primary key,
  user_id      uuid        references users(user_id) on delete cascade,
  product_id   text,
  product_name text,
  action       text,        -- 'shown' | 'buy_click' | 'wishlist'
  ts           timestamptz  default now()
);

create index if not exists idx_user_history_uid_ts
  on user_history(user_id, ts desc);
