#!/bin/sh
set -e

echo "==> Starting CortexOS Engine v2.0..."

exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}
