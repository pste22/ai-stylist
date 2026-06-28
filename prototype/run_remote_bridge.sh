#!/usr/bin/env bash
#
# Run Mira's voice bridge on a HOME / off-corporate machine and expose it over a
# public wss:// URL via Cloudflare Tunnel — so a locked-down office PC (behind a
# TLS-intercepting proxy like Zscaler that blocks the Gemini Live WebSocket) can
# still reach Gemini through THIS machine.
#
# Why this works: the office browser only talks to a *.trycloudflare.com URL (not
# Google's AI domain), so the corporate proxy lets the WebSocket through. The real
# Gemini Live connection is made from here, where there is no proxy.
#
# Prereqs on THIS (home) machine:
#   1. This repo cloned, Python venv created, deps installed (see prototype/requirements.txt)
#   2. prototype/.env with GEMINI_API_KEY (and AMAZON_PARTNER_TAG if using curated)
#   3. cloudflared installed:   brew install cloudflared      (macOS)
#                               or https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
#
# Usage (from the repo root or anywhere):
#   bash prototype/run_remote_bridge.sh
#
# It prints a line like:
#   >>> Point the office web app at:  VITE_MIRA_WS_URL=wss://something-random.trycloudflare.com
# Copy that wss URL to the office PC (next step printed below).

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
PORT="${MIRA_WS_PORT:-8765}"
PY="$ROOT/.venv/bin/python"

if [[ ! -x "$PY" ]]; then
  echo "✗ venv python not found at $PY — create it: python3 -m venv .venv && .venv/bin/pip install -r prototype/requirements.txt" >&2
  exit 1
fi
if ! command -v cloudflared >/dev/null 2>&1; then
  echo "✗ cloudflared not installed. macOS: brew install cloudflared" >&2
  exit 1
fi

# Bind to all interfaces so the tunnel can reach it.
export MIRA_WS_HOST="0.0.0.0"
export MIRA_WS_PORT="$PORT"
export PRODUCT_SOURCE="${PRODUCT_SOURCE:-curated}"

cleanup() { kill "${BRIDGE_PID:-}" "${TUNNEL_PID:-}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo "▸ starting voice bridge on 0.0.0.0:$PORT (PRODUCT_SOURCE=$PRODUCT_SOURCE) ..."
( cd "$HERE" && "$PY" live_server.py ) &
BRIDGE_PID=$!
sleep 2

echo "▸ opening Cloudflare tunnel to http://localhost:$PORT ..."
echo "  (look for the https://<name>.trycloudflare.com line below — your wss URL is the same host)"
echo "─────────────────────────────────────────────────────────────────────────────"
# --no-autoupdate keeps it quiet; the tunnel proxies WebSocket upgrades automatically.
cloudflared tunnel --no-autoupdate --url "http://localhost:$PORT" &
TUNNEL_PID=$!

echo
echo ">>> When you see 'https://<name>.trycloudflare.com' above, on the OFFICE PC run:"
echo ">>>   cd web && VITE_MIRA_WS_URL=wss://<name>.trycloudflare.com npm run dev"
echo ">>> then open http://localhost:5173 and click Talk to Mira."
echo

wait
