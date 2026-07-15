# ── Stage 1: Build React frontend ─────────────────────────────────────────────
FROM node:20-alpine AS frontend

WORKDIR /app
COPY web/package*.json ./
RUN npm ci --silent

# Bake public VITE_ vars into the bundle at build time.
# Values are non-secret (anon key, public URL) — safe to ship in the image.
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ARG VITE_HEYGEN_AVATAR_ID=Wayne_20240711

COPY web/ ./
RUN npm run build          # output → /app/dist


# ── Stage 2: Production Python + nginx ────────────────────────────────────────
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends nginx \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies (pinned for reproducibility)
COPY prototype/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY prototype/ ./prototype/

# Built React app → served by nginx
COPY --from=frontend /app/dist ./static/

# nginx + startup
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY deploy/start.sh   ./start.sh
RUN chmod +x start.sh

EXPOSE 8080

CMD ["./start.sh"]
