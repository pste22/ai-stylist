#!/bin/bash
# Start the Mira dev environment in tmux (two panes: voice bridge + Vite UI).
# Usage: ./dev.sh
# Requires: tmux installed in the Codespace (already available by default)

set -e

SESSION="mira-dev"
ROOT="$(cd "$(dirname "$0")" && pwd)"

# Kill any existing session with the same name
tmux kill-session -t "$SESSION" 2>/dev/null || true

# Create a new detached session running the Python voice bridge
tmux new-session -d -s "$SESSION" -x 220 -y 50 \
  -c "$ROOT/prototype" \
  "python live_server.py; read"

# Split horizontally and run the Vite dev server in the second pane
tmux split-window -h -t "$SESSION" \
  -c "$ROOT/web" \
  "npm run dev; read"

# Make panes equal width
tmux select-layout -t "$SESSION" even-horizontal

# Attach so you can see both servers
tmux attach-session -t "$SESSION"
