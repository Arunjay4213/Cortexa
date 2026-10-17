#!/usr/bin/env python3
"""
CortexOS × TerraLink Stress Test
═════════════════════════════════
25 real queries against TerraLink, verified by CortexOS.
5 adversarial cases with intentional corruption.
Rich TUI for live monitoring.

Usage:
    python scripts/stress_test.py
    python scripts/stress_test.py --threshold 0.6
    python scripts/stress_test.py --tune  # runs at 0.6, 0.7, 0.8
"""

import argparse
import asyncio
import copy
import json
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

# Rich TUI imports
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from rich.align import Align

# Local imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.terralink_source_aggregator import run_terralink_query

console = Console()

CORTEX_BASE = os.environ.get("CORTEX_URL", "https://api.cortexa.ink")
TERRALINK_BASE = "http://localhost:5001"

# ═══════════════════════════════════════════════════════════════════════════════
# 25 Diverse Queries
# ═══════════════════════════════════════════════════════════════════════════════

QUERIES = [
    # Texas Panhandle (demo region)
    "Find me a 50-acre solar site in the Texas Panhandle",
    "500-acre utility-scale solar farm in Wheeler County, TX",
    "Solar project near Shamrock, TX with low permitting risk",
    "Large solar installation in Gray County, Texas",
    "100MW solar site in Roberts County, TX near existing transmission",

    # Arizona Sonoran (demo region)
    "50-acre solar site in Maricopa County, Arizona",
    "Utility-scale solar project in the Arizona Sonoran desert",
    "Solar farm in Pinal County, AZ with high irradiance",
    "200-acre solar development near Phoenix, AZ",
    "Solar site in Yuma County, Arizona",

    # Ohio Appalachian (demo region)
    "Solar site in Licking County, Ohio",
    "50-acre solar farm in the Ohio Appalachian region",
    "Community solar project in Knox County, OH",
    "Solar development in Muskingum County, Ohio",

    # Other states (dynamic generation)
    "100-acre solar site in Lancaster County, Pennsylvania",
    "Solar farm in Wake County, North Carolina",
    "Utility-scale solar in Kern County, California",
    "Solar project in Nye County, Nevada",
    "50-acre solar site in Pueblo County, Colorado",

    # Edge cases — specific constraints
    "Cheapest 50-acre solar site in Texas under $2M total capex",
    "Solar site within 1 mile of a 345kV substation in Texas",
    "Low-risk solar project in a county with no moratorium in Ohio",
    "Solar farm on agricultural land in the Texas Panhandle",
    "Energy community eligible solar site in Collingsworth County, TX",
    "Solar project in Hemphill County, TX with maximum IRA credits",
]

# ═══════════════════════════════════════════════════════════════════════════════
# Adversarial Corruption Functions
# ═══════════════════════════════════════════════════════════════════════════════

def _corrupt_irr(response_text: str) -> tuple[str, str]:
    """Replace IRR percentages with fabricated higher values."""
    original = response_text
    # Find P50 IRR pattern like "P50 IRR 4.5%"
    match = re.search(r"P50 IRR (\d+\.?\d*)%", response_text)
    if match:
        real_irr = match.group(1)
        fake_irr = f"{float(real_irr) + random.uniform(8, 15):.1f}"
        response_text = response_text.replace(f"P50 IRR {real_irr}%", f"P50 IRR {fake_irr}%")
        return response_text, f"Changed P50 IRR from {real_irr}% to {fake_irr}%"
    return original, "No IRR found to corrupt"


def _corrupt_distance(response_text: str) -> tuple[str, str]:
    """Replace substation distance with a fabricated value."""
    match = re.search(r"substation .+? at (.+? mi)", response_text)
    if match:
        real_dist = match.group(1)
        fake_dist = f"{random.uniform(5.0, 12.0):.1f} mi"
        response_text = response_text.replace(real_dist, fake_dist)
        return response_text, f"Changed distance from {real_dist} to {fake_dist}"
    return response_text, "No distance found to corrupt"


def _corrupt_capex(response_text: str) -> tuple[str, str]:
    """Replace capex with a wildly different number."""
    match = re.search(r"capex (\$[\d,.]+[MBK]?)", response_text)
    if match:
        real_capex = match.group(1)
        fake_capex = f"${random.uniform(500, 900):.1f}M"
        response_text = response_text.replace(f"capex {real_capex}", f"capex {fake_capex}")
        return response_text, f"Changed capex from {real_capex} to {fake_capex}"
    return response_text, "No capex found to corrupt"


def _corrupt_acreage(response_text: str) -> tuple[str, str]:
    """Replace acreage with a wrong number."""
    match = re.search(r"(\d+) acres", response_text)
    if match:
        real_acreage = match.group(1)
        fake_acreage = str(int(real_acreage) + random.randint(200, 500))
        response_text = response_text.replace(f"{real_acreage} acres", f"{fake_acreage} acres")
        return response_text, f"Changed acreage from {real_acreage} to {fake_acreage}"
    return response_text, "No acreage found to corrupt"


def _corrupt_yield(response_text: str) -> tuple[str, str]:
    """Replace P50 yield with a fabricated value."""
    match = re.search(r"P50 (\d[\d,]*) MWh/yr", response_text)
    if match:
        real_yield = match.group(1)
        real_num = int(real_yield.replace(",", ""))
        fake_num = real_num + random.randint(50000, 150000)
        fake_yield = f"{fake_num:,}"
        response_text = response_text.replace(f"P50 {real_yield} MWh/yr", f"P50 {fake_yield} MWh/yr")
        return response_text, f"Changed P50 yield from {real_yield} to {fake_yield} MWh/yr"
    return response_text, "No yield found to corrupt"


CORRUPTION_FNS = [_corrupt_irr, _corrupt_distance, _corrupt_capex, _corrupt_acreage, _corrupt_yield]

# Indices of the 25 queries that will be adversarially corrupted
ADVERSARIAL_INDICES = {2, 7, 12, 19, 23}


# ═══════════════════════════════════════════════════════════════════════════════
# Core Test Runner
# ═══════════════════════════════════════════════════════════════════════════════

async def run_single_check(
    query: str,
    query_idx: int,
    threshold: float,
    progress: Progress,
    task_id,
    results: list,
):
    """Run one TerraLink query → CortexOS check cycle."""
    is_adversarial = query_idx in ADVERSARIAL_INDICES
    result = {
        "query_idx": query_idx,
        "query": query,
        "adversarial": is_adversarial,
        "corruption_desc": None,
        "threshold": threshold,
    }

    progress.update(task_id, description=f"[cyan]Q{query_idx+1:02d}[/] TerraLink...")

    # Step 1: Call TerraLink
    try:
        packet, response_text, sources, meta = await run_terralink_query(
            query, terralink_base=TERRALINK_BASE
        )
    except Exception as e:
        result["error"] = f"TerraLink error: {e}"
        result["status"] = "TERRALINK_FAIL"
        results.append(result)
        progress.update(task_id, description=f"[red]Q{query_idx+1:02d}[/] TL FAIL", advance=1)
        return

    if packet is None:
        result["error"] = meta.get("error", "No packet returned")
        result["status"] = "TERRALINK_FAIL"
        result["terralink_meta"] = meta
        results.append(result)
        progress.update(task_id, description=f"[red]Q{query_idx+1:02d}[/] TL FAIL", advance=1)
        return

    result["terralink_meta"] = meta
    result["response_text_original"] = response_text
    result["num_sources"] = len(sources)

    # Step 2: Adversarial corruption
    if is_adversarial:
        corrupt_fn = CORRUPTION_FNS[list(ADVERSARIAL_INDICES).index(query_idx) % len(CORRUPTION_FNS)]
        response_text, corruption_desc = corrupt_fn(response_text)
        result["corruption_desc"] = corruption_desc
        result["response_text_corrupted"] = response_text

    progress.update(task_id, description=f"[yellow]Q{query_idx+1:02d}[/] CortexOS...")

    # Step 3: Call CortexOS /v1/check
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"{CORTEX_BASE}/v1/check",
                json={
                    "response": response_text,
                    "sources": sources,
                    "config": {"nli_entailment_threshold": threshold} if threshold != 0.7 else None,
                },
            )
            r.raise_for_status()
            check_result = r.json()
    except Exception as e:
        result["error"] = f"CortexOS error: {e}"
        result["status"] = "CORTEX_FAIL"
        results.append(result)
        progress.update(task_id, description=f"[red]Q{query_idx+1:02d}[/] CX FAIL", advance=1)
        return

    result["status"] = "OK"
    result["hallucination_index"] = check_result["hallucination_index"]
    result["total_claims"] = check_result["total_claims"]
    result["grounded_count"] = check_result["grounded_count"]
    result["hallucinated_count"] = check_result["hallucinated_count"]
    result["opinion_count"] = check_result["opinion_count"]
    result["cortex_latency_ms"] = check_result["latency_ms"]
    result["claims"] = check_result["claims"]

    # Determine display
    hi = check_result["hallucination_index"]
    if is_adversarial:
        caught = hi > 0
        result["adversarial_caught"] = caught
        label = f"[green]Q{query_idx+1:02d}[/] ADV {'CAUGHT' if caught else '[red]MISSED[/red]'} HI={hi:.2f}"
    else:
        label = f"[green]Q{query_idx+1:02d}[/] HI={hi:.2f}"

    results.append(result)
    progress.update(task_id, description=label, advance=1)


# ═══════════════════════════════════════════════════════════════════════════════
# Aggregate Metrics
# ═══════════════════════════════════════════════════════════════════════════════

def compute_metrics(results: list) -> dict:
    """Compute aggregate metrics from test results."""
    ok_results = [r for r in results if r["status"] == "OK"]
    if not ok_results:
        return {"error": "No successful results"}

    # Basic counts
    total = len(ok_results)
    adversarial = [r for r in ok_results if r["adversarial"]]
    normal = [r for r in ok_results if not r["adversarial"]]

    # Average HI for normal queries (these should ideally be low)
    avg_hi_normal = sum(r["hallucination_index"] for r in normal) / len(normal) if normal else 0

    # Adversarial catch rate
    adv_caught = sum(1 for r in adversarial if r.get("adversarial_caught", False))
    adv_total = len(adversarial)
    adv_catch_rate = adv_caught / adv_total if adv_total > 0 else 0

    # False positive analysis (normal queries with HI > 0.5 are suspicious)
    # We consider claims marked UNSUPPORTED in normal queries as potential false positives
    total_normal_claims = sum(r["total_claims"] for r in normal)
    total_normal_hallucinated = sum(r["hallucinated_count"] for r in normal)
    false_positive_rate = total_normal_hallucinated / total_normal_claims if total_normal_claims > 0 else 0

    # Latency
    cortex_latencies = [r["cortex_latency_ms"] for r in ok_results]
    avg_latency = sum(cortex_latencies) / len(cortex_latencies)
    max_latency = max(cortex_latencies)
    min_latency = min(cortex_latencies)

    # Verdict breakdown
    all_claims = []
    for r in ok_results:
        for c in r.get("claims", []):
            all_claims.append(c)
    verdict_counts = {}
    for c in all_claims:
        v = c["verdict"]
        verdict_counts[v] = verdict_counts.get(v, 0) + 1

    # Failed queries
    failed = [r for r in results if r["status"] != "OK"]

    # Determine overall verdict
    if adv_catch_rate > 0.9 and false_positive_rate < 0.15:
        verdict = "PASS"
    elif adv_catch_rate > 0.7 and false_positive_rate < 0.25:
        verdict = "WARN"
    else:
        verdict = "FAIL"

    return {
        "total_queries": len(results),
        "successful": total,
        "failed": len(failed),
        "avg_hi_normal": round(avg_hi_normal, 4),
        "adversarial_total": adv_total,
        "adversarial_caught": adv_caught,
        "adversarial_catch_rate": round(adv_catch_rate, 4),
        "false_positive_rate": round(false_positive_rate, 4),
        "total_claims": len(all_claims),
        "verdict_counts": verdict_counts,
        "avg_latency_ms": round(avg_latency, 1),
        "min_latency_ms": round(min_latency, 1),
        "max_latency_ms": round(max_latency, 1),
        "verdict": verdict,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TUI Display
# ═══════════════════════════════════════════════════════════════════════════════

def render_summary_table(results: list, metrics: dict, threshold: float) -> Table:
    """Build a Rich table with per-query results."""
    table = Table(
        title=f"CortexOS × TerraLink Stress Test (threshold={threshold})",
        show_lines=True,
        title_style="bold cyan",
    )
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Query", max_width=45, no_wrap=True)
    table.add_column("Type", width=5, justify="center")
    table.add_column("HI", width=6, justify="right")
    table.add_column("Claims", width=7, justify="right")
    table.add_column("G/H/O", width=9, justify="center")
    table.add_column("CX ms", width=7, justify="right")
    table.add_column("Status", width=12, justify="center")

    for r in sorted(results, key=lambda x: x["query_idx"]):
        idx = r["query_idx"] + 1
        query = r["query"][:42] + ("..." if len(r["query"]) > 42 else "")
        qtype = "[red]ADV[/red]" if r["adversarial"] else "NRM"

        if r["status"] != "OK":
            table.add_row(
                str(idx), query, qtype,
                "-", "-", "-", "-",
                f"[red]{r['status']}[/red]",
            )
            continue

        hi = r["hallucination_index"]
        hi_color = "green" if hi < 0.2 else "yellow" if hi < 0.5 else "red"
        hi_str = f"[{hi_color}]{hi:.2f}[/{hi_color}]"

        gho = f"{r['grounded_count']}/{r['hallucinated_count']}/{r['opinion_count']}"
        latency = f"{r['cortex_latency_ms']:.0f}"

        if r["adversarial"]:
            caught = r.get("adversarial_caught", False)
            status = "[green]CAUGHT[/green]" if caught else "[red bold]MISSED[/red bold]"
        else:
            status = f"[{hi_color}]{'CLEAN' if hi == 0 else 'FLAGS'}[/{hi_color}]"

        table.add_row(str(idx), query, qtype, hi_str, str(r["total_claims"]), gho, latency, status)

    return table


def render_metrics_panel(metrics: dict, threshold: float) -> Panel:
    """Build a Rich panel with aggregate metrics."""
    v = metrics["verdict"]
    v_color = {"PASS": "green", "WARN": "yellow", "FAIL": "red"}[v]
    vc = metrics.get("verdict_counts", {})

    text = Text()
    text.append(f"  Verdict: ", style="bold")
    text.append(f"{v}\n", style=f"bold {v_color}")
    text.append(f"  Threshold: {threshold}\n")
    text.append(f"  Queries: {metrics['successful']}/{metrics['total_queries']} successful\n")
    text.append(f"  Avg HI (normal): {metrics['avg_hi_normal']:.4f}\n")
    text.append(f"  Adversarial: {metrics['adversarial_caught']}/{metrics['adversarial_total']} caught ")
    text.append(f"({metrics['adversarial_catch_rate']:.0%})\n")
    text.append(f"  False Positive Rate: {metrics['false_positive_rate']:.1%}\n")
    text.append(f"  Total Claims: {metrics['total_claims']}\n")
    text.append(f"  Verdicts: ")
    for k, count in sorted(vc.items()):
        color = {"GROUNDED": "green", "NUM_MISMATCH": "red", "UNSUPPORTED": "yellow", "OPINION": "dim"}.get(k, "white")
        text.append(f"{k}={count} ", style=color)
    text.append(f"\n  Latency: avg={metrics['avg_latency_ms']:.0f}ms ")
    text.append(f"min={metrics['min_latency_ms']:.0f}ms max={metrics['max_latency_ms']:.0f}ms")

    return Panel(text, title="[bold]Aggregate Metrics[/bold]", border_style=v_color)


def render_adversarial_detail(results: list) -> Panel:
    """Show details of adversarial cases."""
    text = Text()
    adv = [r for r in results if r["adversarial"] and r["status"] == "OK"]
    for r in adv:
        caught = r.get("adversarial_caught", False)
        icon = "[green]CAUGHT[/green]" if caught else "[red bold]MISSED[/red bold]"
        text.append(f"  Q{r['query_idx']+1}: ", style="bold")
        text.append_text(Text.from_markup(f"{icon}\n"))
        text.append(f"    Corruption: {r.get('corruption_desc', '?')}\n")
        text.append(f"    HI: {r['hallucination_index']:.2f} | ")
        text.append(f"Claims: {r['grounded_count']}G/{r['hallucinated_count']}H\n")
        # Show flagged claims
        for c in r.get("claims", []):
            if not c["grounded"]:
                text.append(f"    [red]x[/red] [{c['verdict']}] {c['text'][:70]}\n", style="dim")
        text.append("\n")
    if not adv:
        text.append("  No adversarial results yet.\n")
    return Panel(text, title="[bold red]Adversarial Cases[/bold red]", border_style="red")


# ═══════════════════════════════════════════════════════════════════════════════
# Main Runner
# ═══════════════════════════════════════════════════════════════════════════════

async def run_single_check_simple(
    query: str,
    query_idx: int,
    threshold: float,
    results: list,
    sem: asyncio.Semaphore,
):
    """Wrapper for concurrent execution with semaphore."""
    async with sem:
        # Create a dummy progress for the existing function
        is_adversarial = query_idx in ADVERSARIAL_INDICES
        tag = "[ADV]" if is_adversarial else "     "
        print(f"  [{query_idx+1:02d}/25] {tag} Starting: {query[:50]}...", flush=True)

        result = {
            "query_idx": query_idx,
            "query": query,
            "adversarial": is_adversarial,
            "corruption_desc": None,
            "threshold": threshold,
        }

        # Step 1: Call TerraLink
        try:
            packet, response_text, sources, meta = await run_terralink_query(
                query, terralink_base=TERRALINK_BASE
            )
        except Exception as e:
            result["error"] = f"TerraLink error: {e}"
            result["status"] = "TERRALINK_FAIL"
            results.append(result)
            print(f"  [{query_idx+1:02d}/25] FAIL (TerraLink: {e})", flush=True)
            return

        if packet is None:
            result["error"] = meta.get("error", "No packet returned")
            result["status"] = "TERRALINK_FAIL"
            result["terralink_meta"] = meta
            results.append(result)
            print(f"  [{query_idx+1:02d}/25] FAIL (no packet: {meta.get('error', '?')})", flush=True)
            return

        result["terralink_meta"] = meta
        result["response_text_original"] = response_text
        result["num_sources"] = len(sources)

        # Step 2: Adversarial corruption
        if is_adversarial:
            corrupt_fn = CORRUPTION_FNS[list(ADVERSARIAL_INDICES).index(query_idx) % len(CORRUPTION_FNS)]
            response_text, corruption_desc = corrupt_fn(response_text)
            result["corruption_desc"] = corruption_desc
            result["response_text_corrupted"] = response_text

        # Step 3: Call CortexOS /v1/check
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(
                    f"{CORTEX_BASE}/v1/check",
                    json={
                        "response": response_text,
                        "sources": sources,
                    },
                )
                r.raise_for_status()
                check_result = r.json()
        except Exception as e:
            result["error"] = f"CortexOS error: {e}"
            result["status"] = "CORTEX_FAIL"
            results.append(result)
            print(f"  [{query_idx+1:02d}/25] FAIL (CortexOS: {e})", flush=True)
            return

        result["status"] = "OK"
        result["hallucination_index"] = check_result["hallucination_index"]
        result["total_claims"] = check_result["total_claims"]
        result["grounded_count"] = check_result["grounded_count"]
        result["hallucinated_count"] = check_result["hallucinated_count"]
        result["opinion_count"] = check_result["opinion_count"]
        result["cortex_latency_ms"] = check_result["latency_ms"]
        result["claims"] = check_result["claims"]

        hi = check_result["hallucination_index"]
        if is_adversarial:
            caught = hi > 0
            result["adversarial_caught"] = caught
            status = f"ADV {'CAUGHT' if caught else 'MISSED'}"
        else:
            status = f"HI={hi:.2f}"

        tl_time = meta.get("total_elapsed", 0)
        cx_time = check_result["latency_ms"]
        print(
            f"  [{query_idx+1:02d}/25] {tag} {status} | "
            f"{result['grounded_count']}G/{result['hallucinated_count']}H/{result['opinion_count']}O | "
            f"TL={tl_time:.0f}s CX={cx_time:.0f}ms",
            flush=True,
        )
        results.append(result)


async def run_stress_test(threshold: float = 0.7) -> tuple[list, dict]:
    """Run all 25 queries and return results + metrics."""
    results = []

    console.print(f"\n[bold cyan]CortexOS x TerraLink Stress Test[/bold cyan]")
    console.print(f"  Threshold: {threshold}")
    console.print(f"  Queries: {len(QUERIES)} ({len(ADVERSARIAL_INDICES)} adversarial)")
    console.print(f"  CortexOS: {CORTEX_BASE}")
    console.print(f"  TerraLink: {TERRALINK_BASE}")
    console.print()

    # Check services are up
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.get(f"{CORTEX_BASE}/healthz")
            r.raise_for_status()
            cx_health = r.json()
            assert cx_health.get("model_loaded"), "NLI model not loaded"
        except Exception as e:
            console.print(f"[red bold]CortexOS not ready: {e}[/red bold]")
            return [], {}
        try:
            r = await client.get(f"{TERRALINK_BASE}/api/health")
            r.raise_for_status()
        except Exception as e:
            console.print(f"[red bold]TerraLink not ready: {e}[/red bold]")
            return [], {}

    console.print("[green]Both services healthy. Starting...[/green]\n")

    start = time.time()

    # Run 2 queries concurrently (limited by Groq API + DNS)
    sem = asyncio.Semaphore(2)
    tasks = [
        run_single_check_simple(query, idx, threshold, results, sem)
        for idx, query in enumerate(QUERIES)
    ]
    await asyncio.gather(*tasks)

    elapsed = time.time() - start
    console.print(f"\n[dim]All queries completed in {elapsed:.0f}s[/dim]\n")

    metrics = compute_metrics(results)

    # Display results
    console.print(render_summary_table(results, metrics, threshold))
    console.print()
    if "error" in metrics:
        console.print(f"[red bold]{metrics['error']}[/red bold]")
    else:
        console.print(render_metrics_panel(metrics, threshold))
        console.print()
        console.print(render_adversarial_detail(results))

    return results, metrics


async def run_threshold_tuning():
    """Run the full suite at multiple thresholds and compare."""
    thresholds = [0.6, 0.7, 0.8]
    all_runs = {}

    for t in thresholds:
        console.print(f"\n{'='*60}")
        console.print(f"[bold] Threshold = {t} [/bold]")
        console.print(f"{'='*60}")
        results, metrics = await run_stress_test(threshold=t)
        all_runs[t] = {"results": results, "metrics": metrics}

    # Comparison table
    console.print(f"\n\n{'='*60}")
    console.print("[bold cyan]Threshold Comparison[/bold cyan]")
    console.print(f"{'='*60}\n")

    table = Table(show_lines=True, title="Threshold Tuning Results")
    table.add_column("Metric", style="bold")
    for t in thresholds:
        table.add_column(f"t={t}", justify="right")

    rows = [
        ("Verdict", [all_runs[t]["metrics"].get("verdict", "?") for t in thresholds]),
        ("Avg HI (normal)", [f"{all_runs[t]['metrics'].get('avg_hi_normal', 0):.4f}" for t in thresholds]),
        ("Adv Catch Rate", [f"{all_runs[t]['metrics'].get('adversarial_catch_rate', 0):.0%}" for t in thresholds]),
        ("False Positive Rate", [f"{all_runs[t]['metrics'].get('false_positive_rate', 0):.1%}" for t in thresholds]),
        ("Total Claims", [str(all_runs[t]["metrics"].get("total_claims", 0)) for t in thresholds]),
        ("Avg Latency (ms)", [f"{all_runs[t]['metrics'].get('avg_latency_ms', 0):.0f}" for t in thresholds]),
    ]

    for label, vals in rows:
        table.add_row(label, *vals)

    # Compute optimal: maximize (catch_rate - false_positive_rate)
    scores = {}
    for t in thresholds:
        m = all_runs[t]["metrics"]
        scores[t] = m.get("adversarial_catch_rate", 0) - m.get("false_positive_rate", 0)

    best = max(scores, key=scores.get)
    table.add_row(
        "[bold]Score (catch - FP)[/bold]",
        *[f"[{'green bold' if t == best else 'white'}]{scores[t]:.3f}[/]" for t in thresholds],
    )

    console.print(table)
    console.print(f"\n[bold green]Optimal threshold: {best}[/bold green] (score={scores[best]:.3f})\n")

    return all_runs


async def main():
    parser = argparse.ArgumentParser(description="CortexOS × TerraLink Stress Test")
    parser.add_argument("--threshold", type=float, default=0.7, help="NLI entailment threshold")
    parser.add_argument("--tune", action="store_true", help="Run threshold tuning (0.6, 0.7, 0.8)")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)

    if args.tune:
        all_runs = await run_threshold_tuning()
        # Save all results
        output = {
            "type": "threshold_tuning",
            "timestamp": timestamp,
            "thresholds": {},
        }
        for t, data in all_runs.items():
            output["thresholds"][str(t)] = {
                "metrics": data["metrics"],
                "results": data["results"],
            }
        out_path = results_dir / f"tuning_{timestamp}.json"
    else:
        results, metrics = await run_stress_test(threshold=args.threshold)
        output = {
            "type": "stress_test",
            "timestamp": timestamp,
            "threshold": args.threshold,
            "metrics": metrics,
            "results": results,
        }
        out_path = results_dir / f"stress_test_{timestamp}.json"

    # Save results
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    console.print(f"\n[dim]Results saved to {out_path}[/dim]")


if __name__ == "__main__":
    asyncio.run(main())
