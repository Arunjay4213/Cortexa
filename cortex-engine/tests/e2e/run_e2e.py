#!/usr/bin/env python3
"""E2E Test Runner for CortexOS.

Orchestrates all E2E test suites and generates comprehensive reports.

Usage:
    python tests/e2e/run_e2e.py                    # Run all tests
    python tests/e2e/run_e2e.py --suite validity   # Run specific suite
    python tests/e2e/run_e2e.py --quick            # Run quick mode (reduced queries)
    python tests/e2e/run_e2e.py --report-dir ./my-reports  # Custom report directory
"""

import asyncio
import argparse
import json
import sys
import os
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from e2e.test_attribution_validity import run_all_validity_tests
from e2e.test_performance import run_all_performance_tests
from e2e.test_memorybench import run_all_benchmark_tests
from e2e.agent_simulator import setup_test_environment, teardown_test_environment
from e2e.datasets import generate_personal_assistant_dataset


class E2ETestRunner:
    """Orchestrates E2E test execution and reporting."""

    def __init__(
        self,
        report_dir: str = "tests/e2e/reports",
        quick_mode: bool = False,
        backend_url: str | None = None,
    ):
        self.report_dir = Path(report_dir)
        self.quick_mode = quick_mode
        self.backend_url = backend_url
        self.timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        self.agent_id = None
        self.memory_ids = []
        self.memory_id_map = {}
        self.dataset = None

        # Ensure report directory exists
        self.report_dir.mkdir(parents=True, exist_ok=True)

    async def _setup_backend(self):
        """Set up backend environment by seeding test data."""
        print("\n" + "="*70)
        print("BACKEND SETUP")
        print("="*70)

        # Generate dataset
        self.dataset = generate_personal_assistant_dataset()

        # Prepare memories for backend
        dataset_memories = [(m.id, m.content) for m in self.dataset.memories]

        # Setup test environment (creates agent, seeds memories)
        result = await setup_test_environment(
            base_url=self.backend_url,
            dataset_memories=dataset_memories,
        )

        self.agent_id = result["agent_id"]
        self.memory_ids = result["memory_ids"]
        self.memory_id_map = result.get("memory_id_map", {})

        print(f"\n✓ Backend setup complete")
        print(f"  Agent: {self.agent_id}")
        print(f"  Memories seeded: {len(self.memory_ids)}")
        print(f"  ID mappings: {len(self.memory_id_map)}")

    async def _cleanup_backend(self):
        """Clean up test data from backend."""
        if self.backend_url and self.agent_id:
            try:
                await teardown_test_environment(
                    base_url=self.backend_url,
                    agent_id=self.agent_id,
                    memory_ids=self.memory_ids,
                )
            except Exception as e:
                print(f"\nWarning: Cleanup failed: {e}")

    async def run_all_suites(self) -> Dict:
        """Run all test suites and aggregate results."""
        print(f"\n{'#'*70}")
        print("# CortexOS E2E Test Suite Runner")
        print(f"# Timestamp: {self.timestamp}")
        print(f"# Mode: {'QUICK' if self.quick_mode else 'FULL'}")
        print(f"# Backend: {self.backend_url or 'None (simulated scores)'}")
        print(f"{'#'*70}\n")

        all_suite_results = {}

        # Setup backend if URL provided
        if self.backend_url:
            try:
                await self._setup_backend()
            except Exception as e:
                print(f"\n❌ Backend setup failed: {e}")
                print("Tests will run without real attribution scores")
                self.backend_url = None

        # Run validity tests
        print("\n" + "="*70)
        print("RUNNING: Attribution Validity Tests")
        print("="*70)

        try:
            validity_results = await run_all_validity_tests(
                dataset=self.dataset,  # Use seeded dataset
                cortex_base_url=self.backend_url,
                agent_id=self.agent_id,
                memory_id_map=self.memory_id_map,
            )
            all_suite_results["validity"] = {
                "suite_name": "Attribution Validity",
                "results": validity_results,
                "passed": all(r["passed"] for r in validity_results),
            }
        except Exception as e:
            print(f"\n❌ Validity tests failed with error: {e}")
            import traceback
            traceback.print_exc()
            all_suite_results["validity"] = {
                "suite_name": "Attribution Validity",
                "error": str(e),
                "passed": False,
            }

        # Run performance tests
        print("\n" + "="*70)
        print("RUNNING: Performance Tests")
        print("="*70)

        try:
            performance_results = await run_all_performance_tests()
            all_suite_results["performance"] = {
                "suite_name": "Performance",
                "results": performance_results,
                "passed": all(r["passed"] for r in performance_results),
            }
        except Exception as e:
            print(f"\n❌ Performance tests failed with error: {e}")
            all_suite_results["performance"] = {
                "suite_name": "Performance",
                "error": str(e),
                "passed": False,
            }

        # Run benchmark tests
        print("\n" + "="*70)
        print("RUNNING: Benchmark Tests")
        print("="*70)

        try:
            benchmark_results = await run_all_benchmark_tests()
            all_suite_results["benchmark"] = {
                "suite_name": "Benchmark",
                "results": benchmark_results,
                "passed": all(
                    r["passed"] for r in benchmark_results
                    if not r.get("skipped", False)
                ),
            }
        except Exception as e:
            print(f"\n❌ Benchmark tests failed with error: {e}")
            all_suite_results["benchmark"] = {
                "suite_name": "Benchmark",
                "error": str(e),
                "passed": False,
            }

        # Cleanup backend if used
        if self.backend_url:
            await self._cleanup_backend()

        return all_suite_results

    async def run_suite(self, suite_name: str) -> Dict:
        """Run a specific test suite."""
        print(f"\n{'#'*70}")
        print(f"# CortexOS E2E Test Suite Runner")
        print(f"# Timestamp: {self.timestamp}")
        print(f"# Suite: {suite_name}")
        print(f"# Backend: {self.backend_url or 'None (simulated scores)'}")
        print(f"{'#'*70}\n")

        # Setup backend if URL provided
        if self.backend_url:
            try:
                await self._setup_backend()
            except Exception as e:
                print(f"\n❌ Backend setup failed: {e}")
                import traceback
                traceback.print_exc()
                print("Tests will run without real attribution scores")
                self.backend_url = None

        try:
            if suite_name == "validity":
                results = await run_all_validity_tests(
                    dataset=self.dataset,
                    cortex_base_url=self.backend_url,
                    agent_id=self.agent_id,
                    memory_id_map=self.memory_id_map,
                )
                return {
                    "validity": {
                        "suite_name": "Attribution Validity",
                        "results": results,
                        "passed": all(r["passed"] for r in results),
                    }
                }
        finally:
            # Cleanup backend if used
            if self.backend_url:
                await self._cleanup_backend()

        if suite_name == "validity":
            # Fallback (shouldn't reach here)
            results = await run_all_validity_tests()
            return {
                "validity": {
                    "suite_name": "Attribution Validity",
                    "results": results,
                    "passed": all(r["passed"] for r in results),
                }
            }
        elif suite_name == "performance":
            results = await run_all_performance_tests()
            return {
                "performance": {
                    "suite_name": "Performance",
                    "results": results,
                    "passed": all(r["passed"] for r in results),
                }
            }
        elif suite_name == "benchmark":
            results = await run_all_benchmark_tests()
            return {
                "benchmark": {
                    "suite_name": "Benchmark",
                    "results": results,
                    "passed": all(
                        r["passed"] for r in results
                        if not r.get("skipped", False)
                    ),
                }
            }
        else:
            raise ValueError(f"Unknown test suite: {suite_name}")

    def generate_report(self, suite_results: Dict) -> Dict:
        """Generate comprehensive test report."""
        report = {
            "timestamp": self.timestamp,
            "mode": "quick" if self.quick_mode else "full",
            "suites": self._convert_to_json_serializable(suite_results),
            "summary": self._generate_summary(suite_results),
        }

        return report

    def _convert_to_json_serializable(self, obj):
        """Convert numpy types and other non-serializable objects to JSON-compatible types."""
        import numpy as np

        if isinstance(obj, dict):
            return {key: self._convert_to_json_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_json_serializable(item) for item in obj]
        elif isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return obj

    def _generate_summary(self, suite_results: Dict) -> Dict:
        """Generate summary statistics."""
        total_suites = len(suite_results)
        passed_suites = sum(1 for s in suite_results.values() if s.get("passed", False))

        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0

        for suite_data in suite_results.values():
            if "results" in suite_data:
                for test_result in suite_data["results"]:
                    if test_result.get("skipped", False):
                        skipped_tests += 1
                    else:
                        total_tests += 1
                        if test_result.get("passed", False):
                            passed_tests += 1
                        else:
                            failed_tests += 1

        return {
            "total_suites": total_suites,
            "passed_suites": passed_suites,
            "failed_suites": total_suites - passed_suites,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "skipped_tests": skipped_tests,
            "success_rate": round(passed_tests / total_tests, 4) if total_tests > 0 else 0.0,
        }

    def save_report(self, report: Dict):
        """Save report to JSON file."""
        report_path = self.report_dir / f"e2e_report_{self.timestamp}.json"

        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n📊 Report saved to: {report_path}")

        # Also save latest report
        latest_path = self.report_dir / "latest.json"
        with open(latest_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"📊 Latest report: {latest_path}")

    def print_summary(self, report: Dict):
        """Print human-readable summary."""
        summary = report["summary"]

        print(f"\n{'='*70}")
        print("FINAL SUMMARY")
        print(f"{'='*70}")

        print(f"\nSuites:")
        print(f"  Total: {summary['total_suites']}")
        print(f"  Passed: {summary['passed_suites']} ✅")
        print(f"  Failed: {summary['failed_suites']} ❌")

        print(f"\nTests:")
        print(f"  Total: {summary['total_tests']}")
        print(f"  Passed: {summary['passed_tests']} ✅")
        print(f"  Failed: {summary['failed_tests']} ❌")
        print(f"  Skipped: {summary['skipped_tests']} ⏭️")

        print(f"\nSuccess Rate: {summary['success_rate']:.1%}")

        # Overall status
        if summary['failed_tests'] == 0 and summary['failed_suites'] == 0:
            print("\n🎉 ALL TESTS PASSED! CortexOS is production-ready.")
        else:
            print(f"\n⚠️ {summary['failed_tests']} test(s) failed. Review failures above.")

        print(f"\n{'='*70}\n")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run CortexOS E2E test suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tests/e2e/run_e2e.py                          # Run all tests (simulated)
  python tests/e2e/run_e2e.py --backend-url http://localhost:8000  # Use real backend
  python tests/e2e/run_e2e.py --suite validity         # Run specific suite
  python tests/e2e/run_e2e.py --quick                  # Quick mode
        """
    )

    parser.add_argument(
        "--suite",
        choices=["validity", "performance", "benchmark"],
        help="Run specific test suite only"
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run in quick mode (reduced test counts)"
    )

    parser.add_argument(
        "--backend-url",
        default=None,
        help="CortexOS backend URL (e.g., http://localhost:8000). If not provided, uses simulated scores."
    )

    parser.add_argument(
        "--report-dir",
        default="tests/e2e/reports",
        help="Directory for test reports (default: tests/e2e/reports)"
    )

    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Don't save JSON report (just print to console)"
    )

    args = parser.parse_args()

    # Create runner
    runner = E2ETestRunner(
        report_dir=args.report_dir,
        quick_mode=args.quick,
        backend_url=args.backend_url,
    )

    # Run tests
    try:
        if args.suite:
            suite_results = await runner.run_suite(args.suite)
        else:
            suite_results = await runner.run_all_suites()

        # Generate report
        report = runner.generate_report(suite_results)

        # Save report (unless disabled)
        if not args.no_report:
            runner.save_report(report)

        # Print summary
        runner.print_summary(report)

        # Exit with appropriate code
        summary = report["summary"]
        exit_code = 0 if summary["failed_tests"] == 0 else 1
        sys.exit(exit_code)

    except KeyboardInterrupt:
        print("\n\n⚠️ Tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
