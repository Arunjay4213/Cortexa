#!/usr/bin/env bash
# scripts/setup.sh — one-shot CortexOS setup
# Usage: bash scripts/setup.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ── 1. Create .env if it doesn't exist ────────────────────────────────────
if [ ! -f .env ]; then
  echo "==> Creating .env from .env.example with generated secrets..."
  cp .env.example .env

  DB_PASSWORD="$(openssl rand -hex 24)"
  ADMIN_SECRET="$(openssl rand -hex 32)"

  # Cross-platform sed (macOS and Linux)
  if sed --version 2>/dev/null | grep -q GNU; then
    sed -i "s|DB_PASSWORD=.*|DB_PASSWORD=${DB_PASSWORD}|" .env
    sed -i "s|ADMIN_SECRET=.*|ADMIN_SECRET=${ADMIN_SECRET}|" .env
  else
    sed -i '' "s|DB_PASSWORD=.*|DB_PASSWORD=${DB_PASSWORD}|" .env
    sed -i '' "s|ADMIN_SECRET=.*|ADMIN_SECRET=${ADMIN_SECRET}|" .env
  fi
  echo "    Generated DB_PASSWORD and ADMIN_SECRET."
else
  echo "==> .env already exists — skipping secret generation."
fi

# ── 2. Build and start containers ─────────────────────────────────────────
echo ""
echo "==> Building and starting containers (this may take a few minutes on first run)..."
docker compose up -d --build

# ── 3. Wait for engine health ──────────────────────────────────────────────
echo ""
echo "==> Waiting for CortexOS engine to become healthy..."
MAX_WAIT=120
ELAPSED=0
until curl -sf http://localhost:8000/healthz > /dev/null 2>&1; do
  if [ "$ELAPSED" -ge "$MAX_WAIT" ]; then
    echo ""
    echo "ERROR: Engine did not become healthy after ${MAX_WAIT}s."
    echo "       Check logs with: docker compose logs engine"
    exit 1
  fi
  printf "."
  sleep 2
  ELAPSED=$((ELAPSED + 2))
done
echo ""
echo "    Engine is healthy."

# ── 4. Seed admin API key ──────────────────────────────────────────────────
echo ""
echo "==> Creating admin API key..."
docker compose exec engine python -m cortex.seed_admin

# ── 5. Done ───────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║         CortexOS is running!                     ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  API endpoint: http://localhost:8000             ║"
echo "║  Health check: http://localhost:8000/healthz     ║"
echo "║                                                  ║"
echo "║  Save the API key printed above — it won't be   ║"
echo "║  shown again. Use it as:                         ║"
echo "║    Authorization: Bearer sk-cortex-...           ║"
echo "╚══════════════════════════════════════════════════╝"
