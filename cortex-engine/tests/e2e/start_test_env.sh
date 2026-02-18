#!/bin/bash
# Start CortexOS test environment for E2E tests
#
# Usage:
#   ./tests/e2e/start_test_env.sh [port]
#
# Default port: 8001

set -e

PORT="${1:-8001}"
DB_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/cortex_test}"
MAX_WAIT=30

echo "======================================================================"
echo "Starting CortexOS Test Environment"
echo "======================================================================"
echo "Port: $PORT"
echo "Database: $DB_URL"
echo ""

# Export database URL for alembic and uvicorn
export DATABASE_URL="$DB_URL"

# Step 1: Check if PostgreSQL is running
echo "[1/4] Checking PostgreSQL..."
if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo "❌ PostgreSQL is not running on localhost:5432"
    echo ""
    echo "Please start PostgreSQL first:"
    echo "  brew services start postgresql@14  # macOS"
    echo "  sudo service postgresql start      # Linux"
    echo "  docker run -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:14  # Docker"
    exit 1
fi
echo "✓ PostgreSQL is running"

# Step 2: Create test database if needed
echo ""
echo "[2/4] Creating test database..."
psql -h localhost -U postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'cortex_test'" | grep -q 1 || \
    psql -h localhost -U postgres -c "CREATE DATABASE cortex_test" || true
echo "✓ Database ready: cortex_test"

# Step 3: Run migrations
echo ""
echo "[3/4] Running database migrations..."
cd "$(dirname "$0")/../.." || exit 1  # Go to cortex-engine root

if [ ! -d "alembic" ]; then
    echo "❌ alembic directory not found. Are you in the cortex-engine directory?"
    exit 1
fi

alembic upgrade head
echo "✓ Migrations complete"

# Step 4: Start uvicorn
echo ""
echo "[4/4] Starting uvicorn on port $PORT..."
echo "Press Ctrl+C to stop the server"
echo ""

# Kill any existing process on the port
lsof -ti :$PORT | xargs kill -9 2>/dev/null || true

# Start uvicorn in the foreground (so Ctrl+C stops it)
uvicorn cortex.api.app:app --host 0.0.0.0 --port $PORT --log-level info
