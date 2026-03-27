#!/usr/bin/env bash
# Run the complete CAMA v2 stress test and benchmark suite.
# Usage: bash scripts/run_all.sh

set -euo pipefail
cd "$(dirname "$0")/.."

VENV=".venv/bin/python"
if [ ! -f "$VENV" ]; then
    echo "ERROR: Virtual environment not found at $VENV"
    echo "Create it with: python3 -m venv .venv && .venv/bin/pip install -e ../cama-v2[cpu,dev]"
    exit 1
fi

echo "========================================"
echo "  CAMA v2 Stress Test Suite"
echo "========================================"
echo ""

# 1. Unit tests
echo "--- Unit Tests ---"
$VENV -m pytest unit/ -v --tb=short 2>&1
echo ""

# 2. Integration tests
echo "--- Integration Tests ---"
$VENV -m pytest integration/ -v --tb=short 2>&1
echo ""

# 3. Synthetic benchmark (50 cases for quick run, use run_benchmark.sh for full 500)
echo "--- Synthetic Benchmark (50 cases) ---"
$VENV -m benchmarks.synthetic.evaluate 50 2>&1
echo ""

# 4. Latency benchmark
echo "--- Latency Benchmark ---"
$VENV -m benchmarks.latency.benchmark 2>&1
echo ""

# 5. Generate report
echo "--- Generating Report ---"
$VENV -m benchmarks.report 2>&1
echo ""

echo "========================================"
echo "  All done. See BENCHMARK_REPORT.md"
echo "========================================"
