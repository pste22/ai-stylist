#!/usr/bin/env bash
# Hot-reload dev environment — no deploy needed.
# Backend auto-restarts on any .py change; frontend has Vite HMR (HTTPS).
#
# Usage:  ./dev.sh
# Open https://127.0.0.1:5173 on THIS machine (or Cursor's forwarded port).
# Set MIRA_PUBLIC_TUNNEL=1 to also print a public https://*.trycloudflare.com URL.

set -e
REPO=$(cd "$(dirname "$0")" && pwd)

kill_port() {
  local port="$1"
  local pids
  pids=$(lsof -ti:"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "⚠ Port $port already in use — killing stale process ($pids)"
    kill $pids 2>/dev/null || true
    sleep 1
  fi
}

kill_port 8765
kill_port 5173

# ── Backend ───────────────────────────────────────────────────────────────────
echo "▶ Starting Python backend with auto-reload on :8765"
cd "$REPO/prototype"
if [ -f "$REPO/prototype/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$REPO/prototype/.venv/bin/activate"
elif [ -f "$REPO/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$REPO/.venv/bin/activate"
fi
export MIRA_WS_HOST="${MIRA_WS_HOST:-127.0.0.1}"
if command -v watchfiles >/dev/null 2>&1; then
  watchfiles "python live_server.py" . &
else
  python -u live_server.py &
fi
BACKEND_PID=$!

# ── Frontend ──────────────────────────────────────────────────────────────────
echo "▶ Starting Vite HTTPS dev server with HMR on :5173"
cd "$REPO/web"
if [ "${MIRA_PUBLIC_TUNNEL:-0}" = "1" ]; then
  export VITE_HMR_CLIENT_PORT="${VITE_HMR_CLIENT_PORT:-443}"
  export VITE_HMR_PROTOCOL="${VITE_HMR_PROTOCOL:-wss}"
fi
npm run dev &
FRONTEND_PID=$!

TUNNEL_ON=""
if [ "${MIRA_PUBLIC_TUNNEL:-0}" = "1" ]; then
  CLOUDFLARED="${CLOUDFLARED:-$HOME/bin/cloudflared}"
  if [ ! -x "$CLOUDFLARED" ]; then
    CLOUDFLARED="$(command -v cloudflared || true)"
  fi
  if [ -n "$CLOUDFLARED" ]; then
    # A quick tunnel gets a new random hostname every time it starts, and every new
    # hostname has to be re-added to the Supabase redirect allowlist. So the tunnel
    # is deliberately detached from this script's lifecycle: restarting ./dev.sh
    # reuses the running tunnel and keeps the same public URL.
    if pgrep -f "cloudflared tunnel .*--url https://127.0.0.1:5173" >/dev/null 2>&1; then
      echo "▶ Reusing the public HTTPS tunnel that's already running"
      TUNNEL_ON=1
    else
      echo "▶ Waiting for Vite, then opening a public HTTPS tunnel"
      for _ in $(seq 1 40); do
        if curl -k -s -o /dev/null https://127.0.0.1:5173/; then
          break
        fi
        sleep 0.25
      done
      # http2 rather than the default quic: quic control streams drop repeatedly
      # from this network and the tunnel spends minutes in reconnect backoff.
      setsid nohup "$CLOUDFLARED" tunnel --no-autoupdate --no-tls-verify --protocol http2 \
        --url https://127.0.0.1:5173 > /tmp/mira-tunnel.log 2>&1 < /dev/null &
      disown 2>/dev/null || true
      TUNNEL_ON=1
    fi
  else
    echo "⚠ MIRA_PUBLIC_TUNNEL=1 but cloudflared is not installed"
  fi
fi

# ── Cleanup on Ctrl-C ─────────────────────────────────────────────────────────
# The tunnel is intentionally left running so its public URL survives a restart.
# Stop it with:  pkill -f 'cloudflared tunnel'
trap "echo; echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

echo ""
echo "✦ Dev servers running"
echo "  Frontend (HTTPS): https://127.0.0.1:5173"
echo "  Backend (WS):     ws://127.0.0.1:8765"
echo ""
echo "  This URL only works on the machine running ./dev.sh."
echo "  Cursor Desktop: click the plug icon → forward 5173 → open that URL."
echo "  First visit: accept the self-signed cert warning (Advanced → Proceed)."
echo "  Supabase Auth → Redirect URLs: https://127.0.0.1:5173/**"
if [ -n "$TUNNEL_ON" ]; then
  echo "  Waiting for public HTTPS URL..."
  for _ in $(seq 1 40); do
    PUBLIC_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/mira-tunnel.log 2>/dev/null | head -1 || true)
    if [ -n "$PUBLIC_URL" ]; then
      echo "  Public HTTPS:     $PUBLIC_URL"
      echo ""
      echo "  Quick-tunnel hostnames are random, so add this ONCE to Supabase"
      echo "  Auth → Redirect URLs and every future tunnel works unchanged:"
      echo "      https://*.trycloudflare.com/**"
      echo "  Remove it before launch — it trusts any Cloudflare quick tunnel."
      break
    fi
    sleep 0.5
  done
fi
echo "  Press Ctrl-C to stop."
echo ""

wait
