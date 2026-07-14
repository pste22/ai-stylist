#!/bin/sh
set -e

# Write nginx pid to /tmp (writable without root)
mkdir -p /tmp/nginx

echo "  → starting nginx on :8080"
nginx -g "daemon off;" &

echo "  → starting Mira voice bridge on :8765"
# Override host so Python listens on all interfaces inside the container.
# Fly.io's internal network hits 127.0.0.1 (nginx → Python) so this is safe.
export MIRA_WS_HOST=0.0.0.0
export MIRA_WS_PORT=8765

cd /app/prototype
exec python -u live_server.py
