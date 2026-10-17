#!/usr/bin/env bash
# Quick smoke test — unit tests + shipping story only.
# Usage: bash scripts/run_quick.sh

set -euo pipefail
cd "$(dirname "$0")/.."

VENV=".venv/bin/python"
if [ ! -f "$VENV" ]; then
    echo "ERROR: Virtual environment not found at $VENV"
    exit 1
fi

echo "--- Quick Smoke Test ---"
echo ""

# Unit tests (fast, no ML)
echo "1. Unit tests (types, text, diagnose)..."
$VENV -m pytest unit/test_types.py unit/test_text.py unit/test_diagnose.py -v --tb=short 2>&1
echo ""

# Shipping story gate test (the one that matters)
echo "2. THE GATE TEST: Shipping Story..."
$VENV -m pytest integration/test_shipping_story.py -v --tb=long 2>&1
echo ""

echo "--- Quick smoke test complete ---"
