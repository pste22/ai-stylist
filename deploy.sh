#!/bin/bash
# Deploy Mira AI Stylist to Fly.io.
# Run this from the repo root on your Mac (needs flyctl + fly auth login done once).
# Usage: ./deploy.sh

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# ── Load secrets from prototype/.env ───────────────────────────────────────────
ENV_FILE="$ROOT/prototype/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found. Create it with your API keys."
  exit 1
fi

# Export only lines that look like KEY=VALUE (skip comments and blanks)
set -a
# shellcheck disable=SC1090
source <(grep -E '^[A-Z_]+=.+' "$ENV_FILE")
set +a

# ── Validate required keys are present ─────────────────────────────────────────
MISSING=()
[ -z "$GEMINI_API_KEY" ]       && MISSING+=("GEMINI_API_KEY")
[ -z "$SUPABASE_SECRET_KEY" ]  && MISSING+=("SUPABASE_SECRET_KEY")

if [ ${#MISSING[@]} -gt 0 ]; then
  echo "ERROR: Missing keys in prototype/.env:"
  for k in "${MISSING[@]}"; do echo "  - $k"; done
  exit 1
fi

echo ""
echo "=== Mira → Fly.io Deploy ==="
echo ""

# ── Set Fly.io secrets (idempotent — safe to re-run) ───────────────────────────
echo "→ Setting secrets..."
fly secrets set \
  GEMINI_API_KEY="$GEMINI_API_KEY" \
  SUPABASE_URL="https://tizhjpycyygoysqbxulr.supabase.co" \
  SUPABASE_SECRET_KEY="$SUPABASE_SECRET_KEY" \
  AMAZON_PARTNER_TAG="21112112-20" \
  PRODUCT_SOURCE="supabase" \
  LIVEAVATAR_SANDBOX="1"

echo ""

# ── Build & deploy ─────────────────────────────────────────────────────────────
ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRpemhqcHljeXlnb3lzcWJ4dWxyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDcxODgzMzMsImV4cCI6MjA2Mjc2NDMzM30.KSNXNz_l3HAOqJzF9QnwGxJ0lW1EvfZiBBkFqBq6N9c"

echo "→ Building and deploying (this takes ~5 min)..."
fly deploy --build-arg VITE_SUPABASE_ANON_KEY="$ANON_KEY"

echo ""
echo "Done! App is live at https://ai-stylist.fly.dev"
