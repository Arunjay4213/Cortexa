#!/usr/bin/env python3
"""
CortexOS Stress Test Orchestrator
===================================

Runs all 10 test suites in dependency order and produces a consolidated JSON report.

Usage:
    python stress_tests/run_all.py                    # full suite
    python stress_tests/run_all.py --suite ingestion  # single suite
    python stress_tests/run_all.py --quick            # skip endurance tests
    python stress_tests/run_all.py --workers 8        # default concurrency
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path


SUITES = [
    ("ingestion",    "stress_tests/tests/test_01_ingestion.py"),
    ("retrieval",    "stress_tests/tests/test_02_retrieval.py"),
    ("attribution",  "stress_tests/tests/test_03_attribution.py"),
    ("lifecycle",    "stress_tests/tests/test_04_lifecycle.py"),
    ("multi_agent",  "stress_tests/tests/test_05_multi_agent.py"),
    ("consistency",  "stress_tests/tests/test_06_consistency.py"),
    ("adversarial",  "stress_tests/tests/test_07_adversarial.py"),
    ("compliance",   "stress_tests/tests/test_08_compliance.py"),
    ("degradation",  "stress_tests/tests/test_09_degradation.py"),
    ("endurance",    "stress_tests/tests/test_10_endurance.py"),
]

REPORTS_DIR = Path(__file__).parent / "reports"


def run_suite(name: str, path: str, *, verbose: bool = False) -> dict:
    """Run a single pytest suite; return result dict."""
    print(f"\n{'='*70}")
    print(f"Running suite: {name}")
    print(f"{'='*70}")

    report_path = REPORTS_DIR / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    cmd = [
        sys.executable, "-m", "pytest",
        path,
        "-v" if verbose else "-q",
        "--tb=short",
        f"--json-report",
        f"--json-report-file={report_path}",
        "--timeout=300",
    ]

    # Run without --json-report if plugin not available
    try:
        t0 = time.monotonic()
        result = subprocess.run(cmd, capture_output=not verbose)
        elapsed = time.monotonic() - t0
    except FileNotFoundError:
        # Fallback: no json-report plugin
        cmd_simple = [
            sys.executable, "-m", "pytest",
            path,
            "-v" if verbose else "-q",
            "--tb=short",
            "--timeout=300",
        ]
        t0 = time.monotonic()
        result = subprocess.run(cmd_simple, capture_output=not verbose)
        elapsed = time.monotonic() - t0

    returncode = result.returncode
    stdout = result.stdout.decode() if result.stdout else ""
    stderr = result.stderr.decode() if result.stderr else ""

    # Parse basic counts from pytest output
    passed = failed = errors = skipped = 0
    for line in (stdout + stderr).splitlines():
        parts = line.split()
        for i, p in enumerate(parts):
            if "passed" in p and i > 0:
                try:
                    passed = int(parts[i - 1])
                except ValueError:
                    pass
            if "failed" in p and i > 0:
                try:
                    failed = int(parts[i - 1])
                except ValueError:
                    pass
            if "error" in p and i > 0:
                try:
                    errors = int(parts[i - 1])
                except ValueError:
                    pass
            if "skipped" in p and i > 0:
                try:
                    skipped = int(parts[i - 1])
                except ValueError:
                    pass

    status = "pass" if returncode == 0 else "fail"
    print(f"Suite {name}: {status.upper()} | passed={passed} failed={failed} skipped={skipped} ({elapsed:.1f}s)")

    if not verbose and (returncode != 0):
        # Print output on failure
        print(stdout[-3000:] if len(stdout) > 3000 else stdout)
        print(stderr[-1000:] if len(stderr) > 1000 else stderr)

    return {
        "suite": name,
        "status": status,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
        "duration_s": round(elapsed, 2),
        "returncode": returncode,
    }


def get_environment() -> dict:
    """Collect environment metadata."""
    import multiprocessing
    try:
        mem_gb = os.popen("sysctl -n hw.memsize 2>/dev/null || cat /proc/meminfo 2>/dev/null | head -1").read().strip()
    except Exception:
        mem_gb = "unknown"
    return {
        "platform": platform.platform(),
        "python": sys.version,
        "cpu_count": multiprocessing.cpu_count(),
        "memory_raw": mem_gb,
        "os": platform.system(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="CortexOS stress test orchestrator")
    parser.add_argument("--suite", help="Run only this suite by name")
    parser.add_argument("--quick", action="store_true", help="Skip endurance tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show pytest output live")
    parser.add_argument("--fail-fast", action="store_true", help="Stop after first suite failure")
    args = parser.parse_args()

    REPORTS_DIR.mkdir(exist_ok=True)

    suites_to_run = SUITES
    if args.suite:
        suites_to_run = [(n, p) for n, p in SUITES if n == args.suite]
        if not suites_to_run:
            print(f"Unknown suite: {args.suite}. Available: {[n for n, _ in SUITES]}")
            return 1
    if args.quick:
        suites_to_run = [(n, p) for n, p in suites_to_run if n != "endurance"]

    run_id = str(uuid.uuid4())
    started_at = datetime.utcnow().isoformat() + "Z"
    suite_results: list[dict] = []

    print(f"\nCortexOS Stress Test Suite")
    print(f"Run ID: {run_id}")
    print(f"Suites: {[n for n, _ in suites_to_run]}")
    print(f"Started: {started_at}")

    overall_t0 = time.monotonic()

    for name, path in suites_to_run:
        result = run_suite(name, path, verbose=args.verbose)
        suite_results.append(result)

        if args.fail_fast and result["status"] == "fail":
            print(f"\nFail-fast: stopping after {name} failure.")
            break

    overall_elapsed = time.monotonic() - overall_t0

    # Build consolidated report
    total_passed = sum(r["passed"] for r in suite_results)
    total_failed = sum(r["failed"] for r in suite_results)
    total_errors = sum(r["errors"] for r in suite_results)
    overall_status = "pass" if all(r["status"] == "pass" for r in suite_results) else "fail"

    report = {
        "test_run_id": run_id,
        "timestamp": started_at,
        "environment": get_environment(),
        "overall_status": overall_status,
        "total_duration_s": round(overall_elapsed, 2),
        "suites": {
            r["suite"]: {
                "status": r["status"],
                "passed": r["passed"],
                "failed": r["failed"],
                "errors": r["errors"],
                "skipped": r["skipped"],
                "duration_s": r["duration_s"],
            }
            for r in suite_results
        },
        "summary": {
            "total_passed": total_passed,
            "total_failed": total_failed,
            "total_errors": total_errors,
            "suites_run": len(suite_results),
            "suites_passed": sum(1 for r in suite_results if r["status"] == "pass"),
            "suites_failed": sum(1 for r in suite_results if r["status"] == "fail"),
        },
    }

    report_file = REPORTS_DIR / f"stress_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_file.write_text(json.dumps(report, indent=2))

    print(f"\n{'='*70}")
    print(f"STRESS TEST COMPLETE")
    print(f"{'='*70}")
    print(f"Overall: {overall_status.upper()}")
    print(f"Suites:  {report['summary']['suites_passed']}/{report['summary']['suites_run']} passed")
    print(f"Tests:   {total_passed} passed, {total_failed} failed, {total_errors} errors")
    print(f"Total time: {overall_elapsed:.1f}s")
    print(f"Report: {report_file}")

    return 0 if overall_status == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
