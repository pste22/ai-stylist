-- Migration: replace old user_preferences schema with onboarding columns.
-- Run once in the Supabase SQL Editor if the table already exists.

alter table user_preferences
  add column if not exists style_vibe     text,
  add column if not exists shopping_focus text,
  add column if not exists top_size       text,
  add column if not exists bottom_size    text,
  add column if not exists budget         text;

-- Old columns (safe to drop after verifying nothing reads them)
alter table user_preferences
  drop column if exists budget_min,
  drop column if exists budget_max,
  drop column if exists vibes,
  drop column if exists body_notes;
