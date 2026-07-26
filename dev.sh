#!/usr/bin/env bash
# Hot-reload dev environment — no deploy needed.
# Backend auto-restarts on any .py change; frontend has Vite HMR.
#
# Usage:  ./dev.sh
# Then open the Codespaces forwarded URL for port 5173.

set -e
REPO=$(cd "$(dirname "$0")" && pwd)

# ── Backend ───────────────────────────────────────────────────────────────────
echo "▶ Starting Python backend with auto-reload on :8765"
cd "$REPO/prototype"
source .venv/bin/activate
# watchfiles re-runs the command whenever any .py file in prototype/ changes
watchfiles "python live_server.py" . &
BACKEND_PID=$!

# ── Frontend ──────────────────────────────────────────────────────────────────
echo "▶ Starting Vite dev server with HMR on :5173"
cd "$REPO/web"
npm run dev &
FRONTEND_PID=$!

# ── Cleanup on Ctrl-C ─────────────────────────────────────────────────────────
trap "echo; echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

echo ""
echo "✦ Dev servers running"
echo "  Frontend (HMR):  http://localhost:5173"
echo "  Backend (WS):    ws://localhost:8765"
echo ""
echo "  In Codespaces: open the forwarded port 5173 URL"
echo "  Press Ctrl-C to stop both."
echo ""

wait
