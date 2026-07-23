#!/bin/bash
# Start the Mira dev environment.
# Usage: ./dev.sh

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$ROOT/prototype/.venv"
VENV="$VENV_DIR/bin/python"
LOG_DIR="/tmp/mira-dev"
mkdir -p "$LOG_DIR"

rm -rf "$ROOT/web/node_modules/.vite" "$ROOT/web/.vite"

if [ ! -x "$VENV" ]; then
  echo "→ Creating Python virtualenv..."
  python3 -m venv "$VENV_DIR"
fi

echo "→ Installing Python dependencies..."
"$VENV" -m pip install -r "$ROOT/prototype/requirements.txt" >/tmp/mira-dev/pip-install.log 2>&1

if [ ! -d "$ROOT/web/node_modules" ]; then
  echo "→ Installing web dependencies..."
  (cd "$ROOT/web" && npm install) >/tmp/mira-dev/npm-install.log 2>&1
fi

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
  -- env PYTHONUNBUFFERED=1 "$VENV" live_server.py > "$LOG_DIR/live_server.log" 2>&1 &
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
