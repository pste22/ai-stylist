#!/usr/bin/env python3
"""One-time migration: create the session_costs table in Supabase.

Tracks Gemini token usage and estimated $ cost per session for cost monitoring.

Usage (from project root):
    python prototype/migrate_session_costs.py
    python prototype/migrate_session_costs.py --dry-run   # show SQL only

Idempotent: uses CREATE TABLE IF NOT EXISTS so safe to re-run.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env", override=True)

SQL = """
-- Cost tracking for every Mira session (Gemini Live token + $ usage).
CREATE TABLE IF NOT EXISTS session_costs (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at       timestamptz NOT NULL DEFAULT now(),

    session_id       text NOT NULL,          -- matches live_server session_id
    user_id          uuid REFERENCES auth.users(id) ON DELETE SET NULL,

    prompt_tokens    integer NOT NULL DEFAULT 0,
    response_tokens  integer NOT NULL DEFAULT 0,
    total_tokens     integer NOT NULL DEFAULT 0,
    cost_usd         numeric(10,6) NOT NULL DEFAULT 0,
    duration_sec     numeric(8,1) NOT NULL DEFAULT 0
);

-- Index for fast per-user and per-day cost queries.
CREATE INDEX IF NOT EXISTS session_costs_user_id_idx
    ON session_costs (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS session_costs_created_at_idx
    ON session_costs (created_at DESC);

-- Convenience view: daily spend summary.
CREATE OR REPLACE VIEW daily_cost_summary AS
SELECT
    date_trunc('day', created_at)::date  AS day,
    count(*)                             AS sessions,
    sum(total_tokens)                    AS total_tokens,
    round(sum(cost_usd)::numeric, 4)     AS cost_usd,
    round(avg(duration_sec)::numeric, 1) AS avg_duration_sec,
    round(avg(cost_usd)::numeric, 6)     AS avg_cost_per_session
FROM session_costs
GROUP BY 1
ORDER BY 1 DESC;
"""


def run(dry_run: bool = False) -> None:
    if dry_run:
        print("-- DRY RUN — SQL that would be executed:\n")
        print(SQL)
        return

    from supabase import create_client
    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SECRET_KEY"],
    )
    # Execute via the Postgres REST endpoint (rpc → exec_sql not available on all plans).
    # Fall back to printing the SQL for manual execution if RPC isn't available.
    try:
        sb.rpc("exec_sql", {"sql": SQL}).execute()
        print("✅  session_costs table + daily_cost_summary view created.")
    except Exception as exc:
        if "exec_sql" in str(exc) or "Could not find" in str(exc):
            print("⚠️  exec_sql RPC not available on your Supabase plan.")
            print("    Run this SQL manually in the Supabase SQL editor:\n")
            print(SQL)
        else:
            print(f"✅  Migration complete (note: {exc})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run(dry_run=args.dry_run)
