#!/bin/bash
# Start CortexOS
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check postgres
/opt/homebrew/opt/postgresql@17/bin/pg_isready -q || { echo "Start postgres first"; exit 1; }

# Run migrations
cd cortex-engine
/opt/anaconda3/bin/python -m alembic upgrade head 2>/dev/null

# Seed admin key if first run (idempotent)
CORTEX_ADMIN_SECRET="${CORTEX_ADMIN_SECRET:-dev-admin-secret}" \
  /opt/anaconda3/bin/python -m cortex.seed_admin 2>/dev/null || true

# Kill existing server if running
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

# Start server in background
CORTEX_ADMIN_SECRET="${CORTEX_ADMIN_SECRET:-dev-admin-secret}" \
  /opt/anaconda3/bin/python -m uvicorn cortex.api.app:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!

# Wait for healthy
for i in $(seq 1 30); do
  curl -sf http://localhost:8000/healthz > /dev/null 2>&1 && break
  sleep 1
done

if ! curl -sf http://localhost:8000/healthz > /dev/null 2>&1; then
  echo "Server failed to start"
  kill $SERVER_PID 2>/dev/null
  exit 1
fi

echo "CortexOS running on http://localhost:8000 (PID: $SERVER_PID)"
echo "Admin secret: ${CORTEX_ADMIN_SECRET:-dev-admin-secret}"
