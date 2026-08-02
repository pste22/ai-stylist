-- Session watcher reports from real tester sessions.
-- Each row = one WebSocket session's full validation summary.

create table if not exists watcher_sessions (
  id              uuid primary key default gen_random_uuid(),
  session_id      text not null,          -- client-generated UUID
  user_id         text,
  user_name       text,
  mode            text,                   -- 'text' | 'voice'
  duration_ms     int,
  turns           int default 0,
  products_shown  int default 0,
  show_more_clicks int default 0,
  looks_received  int default 0,
  vs_searches     int default 0,
  avg_latency_ms  int,
  p95_latency_ms  int,
  health_score    int,
  error_count     int default 0,
  warn_count      int default 0,
  ok_count        int default 0,
  bugs            jsonb default '[]',     -- array of {level, msg, detail, ts, turn}
  turn_log        jsonb default '[]',     -- array of {turn, text, responseMs, ...}
  latency_samples jsonb default '[]',
  reported_at     timestamptz default now()
);

-- Index for querying by user or health
create index if not exists watcher_sessions_user_id    on watcher_sessions(user_id);
create index if not exists watcher_sessions_health     on watcher_sessions(health_score);
create index if not exists watcher_sessions_reported   on watcher_sessions(reported_at desc);

-- Anyone can insert (testers), only service role can read
alter table watcher_sessions enable row level security;

create policy "testers can insert reports"
  on watcher_sessions for insert
  with check (true);

-- You (the developer) read via service key — no select policy needed for anon
