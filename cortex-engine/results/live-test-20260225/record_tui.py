#!/usr/bin/env python3
"""
CortexOS TUI Headless Recorder
===============================
Runs the TUI in headless mode, fires the test script, captures SVG snapshots
at key moments, and saves everything to /tmp/cortexos-real-world-test/.

Uses Textual's built-in screenshot/export_screenshot() for pixel-perfect
terminal recording.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Add SDK to path
sys.path.insert(0, "/Users/revanshphull/cortex/cortexos-sdk")

os.environ["GROQ_API_KEY"] = os.environ.get("GROQ_API_KEY", "")
os.environ["CORTEX_URL"] = "http://localhost:10000"

OUTPUT_DIR = Path("/tmp/cortexos-real-world-test")
SNAPSHOTS_DIR = OUTPUT_DIR / "snapshots"
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

from cortexos.tui.app import CortexMonitor


async def run_recording():
    """Run TUI headless, capture snapshots while test script runs."""

    app = CortexMonitor(base_url="http://localhost:10000")

    # Run in headless mode with larger terminal size
    async with app.run_test(headless=True, size=(180, 50)) as pilot:
        # Wait for SSE connection
        await pilot.pause()
        await asyncio.sleep(2)

        # Take initial snapshot (empty state)
        svg = app.export_screenshot()
        (SNAPSHOTS_DIR / "00_initial.svg").write_text(svg)
        print("  [snap] 00_initial.svg — empty TUI connected")

        # Start the test script as subprocess
        print("  [run]  Starting test script...")
        proc = await asyncio.create_subprocess_exec(
            "/opt/anaconda3/bin/python",
            str(OUTPUT_DIR / "run_test.py"),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env={
                **os.environ,
                "PYTHONPATH": "/Users/revanshphull/cortex/cortexos-sdk",
            },
        )

        # Snapshot schedule: capture at intervals as events stream in
        snapshot_schedule = [
            (12, "01_first_checks", "first check events arriving"),
            (25, "02_hallucination_tests", "hallucination detection in progress"),
            (40, "03_injection_attacks", "injection attacks being blocked"),
            (55, "04_poison_attack", "memory poisoning attack"),
            (70, "05_grounded_facts", "grounded fact verification"),
        ]

        start = time.time()
        schedule_idx = 0

        while proc.returncode is None:
            elapsed = time.time() - start
            await asyncio.sleep(1)
            await pilot.pause()

            # Take scheduled snapshots
            if schedule_idx < len(snapshot_schedule):
                target_time, name, desc = snapshot_schedule[schedule_idx]
                if elapsed >= target_time:
                    try:
                        svg = app.export_screenshot()
                        (SNAPSHOTS_DIR / f"{name}.svg").write_text(svg)
                        print(f"  [snap] {name}.svg — {desc} ({elapsed:.0f}s)")
                    except Exception as e:
                        print(f"  [snap] {name} FAILED: {e}")
                    schedule_idx += 1

            # Check if test is done
            try:
                await asyncio.wait_for(proc.wait(), timeout=0.1)
            except asyncio.TimeoutError:
                pass

        # Wait for final events to arrive
        await asyncio.sleep(3)
        await pilot.pause()

        # Switch to each tab and capture
        tabs = [
            ("tab-feed", "06_feed_final"),
            ("tab-claims", "07_claims_final"),
            ("tab-memory", "08_memory_final"),
            ("tab-agents", "09_agents_final"),
        ]

        for tab_id, name in tabs:
            app.action_switch_tab(tab_id)
            await pilot.pause()
            await asyncio.sleep(0.5)
            try:
                svg = app.export_screenshot()
                (SNAPSHOTS_DIR / f"{name}.svg").write_text(svg)
                print(f"  [snap] {name}.svg")
            except Exception as e:
                print(f"  [snap] {name} FAILED: {e}")

        # Capture Inspect tab with attribution — pick first hallucinated event
        from cortexos.tui.tabs.inspect import InspectTab
        halluc_event = None
        for ev in app.state.events:
            if ev.hallucinated > 0 and any(c.get("attribution") for c in ev.claims):
                halluc_event = ev
                break
        if halluc_event:
            try:
                inspect = app.query_one(InspectTab)
                inspect.show_event(halluc_event)
                app.action_switch_tab("tab-inspect")
                await pilot.pause()
                await asyncio.sleep(1)
                svg = app.export_screenshot()
                (SNAPSHOTS_DIR / "10_inspect_attribution.svg").write_text(svg)
                print(f"  [snap] 10_inspect_attribution.svg — Shapley attribution detail")
            except Exception as e:
                print(f"  [snap] 10_inspect_attribution FAILED: {e}")

        # Read test output
        stdout_data = await proc.stdout.read()
        test_output = stdout_data.decode("utf-8", errors="replace")
        (OUTPUT_DIR / "test_output.txt").write_text(test_output)
        print(f"\n  [done] Test exited with code {proc.returncode}")
        print(f"  [done] Test output saved to test_output.txt")
        print(f"  [done] {len(list(SNAPSHOTS_DIR.glob('*.svg')))} SVG snapshots in {SNAPSHOTS_DIR}")

        # Export session data
        try:
            session_data = {
                "total_checks": app.state.total_checks,
                "total_events": len(app.state.events),
                "avg_hi": app.state.avg_hi,
                "halluc_pct": app.state.halluc_pct,
                "events": [e.raw for e in app.state.events],
            }
            (OUTPUT_DIR / "session_export.json").write_text(
                json.dumps(session_data, indent=2, default=str)
            )
            print(f"  [done] Session data: {app.state.total_checks} checks, "
                  f"{len(app.state.events)} events, "
                  f"avg HI={app.state.avg_hi:.2f}")
        except Exception as e:
            print(f"  [warn] Session export failed: {e}")


def main():
    print()
    print("═══════════════════════════════════════════════════════")
    print("  CortexOS TUI Headless Recording")
    print("═══════════════════════════════════════════════════════")
    print()

    # Clean old data
    import shutil
    for f in SNAPSHOTS_DIR.glob("*.svg"):
        f.unlink()
    chromadb_dir = OUTPUT_DIR / "chromadb"
    if chromadb_dir.exists():
        shutil.rmtree(chromadb_dir)

    asyncio.run(run_recording())

    print()
    print("  Files:")
    for f in sorted(OUTPUT_DIR.glob("*")):
        if f.is_file():
            size = f.stat().st_size
            print(f"    {f.name:30s} {size:>10,} bytes")
    for f in sorted(SNAPSHOTS_DIR.glob("*.svg")):
        size = f.stat().st_size
        print(f"    snapshots/{f.name:20s} {size:>10,} bytes")
    print()


if __name__ == "__main__":
    main()
