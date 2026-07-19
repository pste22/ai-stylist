#!/bin/bash
# Start the Mira development environment.
#
# Usage: ./dev.sh
#
# One command that:
#   - creates the local Python virtual environment when needed;
#   - installs lockfile-pinned web dependencies when needed;
#   - starts the Gemini voice bridge and Vite web app;
#   - streams both logs (Ctrl-C stops log streaming, not the servers).
#
# Required configuration:
#   prototype/.env  (GEMINI_API_KEY at minimum)
#   web/.env        (VITE_SUPABASE_URL + VITE_SUPABASE_ANON_KEY for login)

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="/tmp/mira-dev"
VENV="$ROOT/.venv"
PYTHON="$VENV/bin/python"
BRIDGE_PID_FILE="$LOG_DIR/live_server.pid"
VITE_PID_FILE="$LOG_DIR/vite.pid"
mkdir -p "$LOG_DIR"

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "Node.js and npm are required. Install a current Node LTS release, then rerun ./dev.sh."
  exit 1
fi

if [ ! -f "$ROOT/prototype/.env" ]; then
  echo "Missing prototype/.env."
  echo "Create it with: cp prototype/.env.example prototype/.env"
  echo "Then add GEMINI_API_KEY and your Supabase settings."
  exit 1
fi

# Export backend settings for the bridge. Python also loads this file itself, but
# exporting here lets us validate the required key before either service starts.
set -a
. "$ROOT/prototype/.env"
set +a

if [ -z "${GEMINI_API_KEY:-}" ]; then
  echo "prototype/.env is missing GEMINI_API_KEY."
  exit 1
fi

if [ ! -x "$PYTHON" ]; then
  echo "→ Creating Python virtual environment..."
  python3 -m venv "$VENV"
fi

if ! "$PYTHON" -c "import google.genai, websockets" >/dev/null 2>&1; then
  echo "→ Installing Python dependencies..."
  "$PYTHON" -m pip install -r "$ROOT/prototype/requirements.txt"
fi

if [ ! -d "$ROOT/web/node_modules" ]; then
  echo "→ Installing web dependencies..."
  (cd "$ROOT/web" && npm ci)
fi

stop_from_pidfile() {
  PID_FILE="$1"
  if [ -f "$PID_FILE" ]; then
    PID="$(cat "$PID_FILE")"
    if kill -0 "$PID" 2>/dev/null; then
      kill "$PID" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
  fi
}

# Stop only processes launched by this script; never kill another project’s Vite.
stop_from_pidfile "$BRIDGE_PID_FILE"
stop_from_pidfile "$VITE_PID_FILE"
sleep 1

echo "→ Starting Python voice bridge..."
cd "$ROOT/prototype"
nohup "$PYTHON" -u live_server.py > "$LOG_DIR/live_server.log" 2>&1 &
BRIDGE_PID="$!"
echo "$BRIDGE_PID" > "$BRIDGE_PID_FILE"
echo "  PID $BRIDGE_PID — logs: $LOG_DIR/live_server.log"

echo "→ Starting Vite dev server..."
cd "$ROOT/web"
nohup npm run dev > "$LOG_DIR/vite.log" 2>&1 &
VITE_PID="$!"
echo "$VITE_PID" > "$VITE_PID_FILE"
echo "  PID $VITE_PID — logs: $LOG_DIR/vite.log"

echo ""
echo "Open http://localhost:5173 when Vite reports ready."
echo "Both servers started. Tailing logs (Ctrl+C stops log streaming — servers keep running):"
echo "──────────────────────────────────────────────────────"
sleep 2
tail -f "$LOG_DIR/live_server.log" "$LOG_DIR/vite.log"
