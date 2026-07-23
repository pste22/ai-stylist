#!/bin/bash
# Start the Mira dev environment.
# Usage: ./dev.sh

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv/bin/python"
LOG_DIR="/tmp/mira-dev"
mkdir -p "$LOG_DIR"

# Kill previous instances — watchmedo parent AND python child AND anything on port 8765
pkill -f "watchmedo" 2>/dev/null || true
pkill -f "live_server.py" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
fuser -k 8765/tcp 2>/dev/null || true
sleep 1

echo "→ Starting Python voice bridge (auto-restarts on .py changes)..."
cd "$ROOT/prototype"
nohup watchmedo auto-restart \
  --patterns="*.py" \
  --recursive \
  --debounce-interval=1 \
  -- "$VENV" live_server.py > "$LOG_DIR/live_server.log" 2>&1 &
echo "  PID $! — logs: $LOG_DIR/live_server.log"

echo "→ Starting Vite dev server..."
cd "$ROOT/web"
nohup npm run dev > "$LOG_DIR/vite.log" 2>&1 &
echo "  PID $! — logs: $LOG_DIR/vite.log"

echo ""
echo "Both servers started. Tailing logs (Ctrl+C to stop tailing — servers keep running):"
echo "──────────────────────────────────────────────────────"
sleep 2
tail -f "$LOG_DIR/live_server.log" "$LOG_DIR/vite.log"
