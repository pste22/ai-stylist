-- Migration: add pin_code to user_preferences
-- Run once in Supabase SQL Editor
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS pin_code text;
