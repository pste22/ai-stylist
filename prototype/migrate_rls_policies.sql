-- ─────────────────────────────────────────────────────────────────────────────
-- RLS owner-scoped policies (LAUNCH BLOCKER fix)
--
-- RLS was ENABLED on the user tables (schema.sql) but NO policies were defined,
-- so the public anon key had no owner scoping. The web client talks to these
-- tables directly with the user's OAuth JWT, so `auth.uid()` is available — these
-- policies restrict every row to its owner (read + write + delete).
--
-- The Python backend uses the SERVICE ROLE key, which BYPASSES RLS, so server
-- writes (chat_store, user_store) are unaffected.
--
-- Apply in Supabase → SQL editor. Idempotent (drops-if-exists first).
-- VERIFY after applying: sign in as account B, query account A's rows without a
-- user_id filter → must return 0 rows / 0 affected.
-- ─────────────────────────────────────────────────────────────────────────────

-- users: PK is user_id (= the auth user id)
drop policy if exists "own row" on users;
create policy "own row" on users
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- user_preferences
drop policy if exists "own prefs" on user_preferences;
create policy "own prefs" on user_preferences
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- user_history
drop policy if exists "own history" on user_history;
create policy "own history" on user_history
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- event_briefs
drop policy if exists "own briefs" on event_briefs;
create policy "own briefs" on event_briefs
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- looks (user_id nullable — anonymous/system looks are not client-owned)
drop policy if exists "own looks" on looks;
create policy "own looks" on looks
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- look_items: owned transitively via the parent look
drop policy if exists "own look items" on look_items;
create policy "own look items" on look_items
  for all using (
    exists (select 1 from looks l where l.id = look_items.look_id and l.user_id = auth.uid())
  ) with check (
    exists (select 1 from looks l where l.id = look_items.look_id and l.user_id = auth.uid())
  );

-- ── Chat tables (created by chat_store.py; hold conversation transcripts = PII) ──
-- Enable RLS if not already, and scope to owner. Server writes via service role
-- (bypasses RLS); the client only READS its own history.
alter table if exists chat_sessions enable row level security;
drop policy if exists "own chat sessions" on chat_sessions;
create policy "own chat sessions" on chat_sessions
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

alter table if exists chat_messages enable row level security;
drop policy if exists "own chat messages" on chat_messages;
create policy "own chat messages" on chat_messages
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
