#!/usr/bin/env python3
"""
CortexOS Failure Analyzer
═════════════════════════
Loads stress test JSON results and produces detailed analysis.

Usage:
    python scripts/analyze_failures.py                          # latest results
    python scripts/analyze_failures.py results/stress_test_*.json  # specific file
"""

import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def load_results(path: str | None = None) -> dict:
    """Load the most recent results file, or a specific one."""
    results_dir = Path("results")

    if path:
        p = Path(path)
    else:
        # Find the most recent file
        files = sorted(results_dir.glob("stress_test_*.json")) + sorted(results_dir.glob("tuning_*.json"))
        if not files:
            console.print("[red]No results files found in results/[/red]")
            sys.exit(1)
        p = files[-1]

    console.print(f"[dim]Loading: {p}[/dim]\n")
    with open(p) as f:
        return json.load(f)


def analyze_stress_test(data: dict):
    """Analyze a single stress test run."""
    results = data.get("results", [])
    metrics = data.get("metrics", {})
    threshold = data.get("threshold", 0.7)

    if not results:
        console.print("[red]No results to analyze.[/red]")
        return

    ok_results = [r for r in results if r.get("status") == "OK"]

    # ═══════════════════════════════════════════════════════════════════
    # Summary Table
    # ═══════════════════════════════════════════════════════════════════
    console.print("[bold cyan]Summary Table[/bold cyan]\n")

    table = Table(show_lines=True)
    table.add_column("Query", max_width=40, no_wrap=True)
    table.add_column("Region", width=18)
    table.add_column("Type", width=5, justify="center")
    table.add_column("HI", width=6, justify="right")
    table.add_column("Claims", width=7, justify="right")
    table.add_column("Caught", width=7, justify="right")
    table.add_column("Missed", width=7, justify="right")
    table.add_column("CX ms", width=7, justify="right")

    for r in sorted(ok_results, key=lambda x: x["query_idx"]):
        query_short = r["query"][:37] + ("..." if len(r["query"]) > 37 else "")

        # Extract region from query
        region = "Unknown"
        q = r["query"].lower()
        if "texas" in q or ", tx" in q:
            region = "Texas"
        elif "arizona" in q or ", az" in q:
            region = "Arizona"
        elif "ohio" in q or ", oh" in q:
            region = "Ohio"
        elif "pennsylvania" in q or ", pa" in q:
            region = "Pennsylvania"
        elif "carolina" in q or ", nc" in q:
            region = "N. Carolina"
        elif "california" in q or ", ca" in q:
            region = "California"
        elif "nevada" in q or ", nv" in q:
            region = "Nevada"
        elif "colorado" in q or ", co" in q:
            region = "Colorado"

        is_adv = r.get("adversarial", False)
        qtype = "[red]ADV[/red]" if is_adv else "NRM"

        hi = r.get("hallucination_index", 0)
        hi_color = "green" if hi < 0.2 else "yellow" if hi < 0.5 else "red"

        caught = r.get("hallucinated_count", 0)
        # "Missed" for adversarial = corruption not detected
        if is_adv:
            missed = "0" if r.get("adversarial_caught", False) else "[red bold]1[/red bold]"
        else:
            missed = "0"

        table.add_row(
            query_short,
            region,
            qtype,
            f"[{hi_color}]{hi:.2f}[/{hi_color}]",
            str(r.get("total_claims", 0)),
            str(caught),
            missed,
            f"{r.get('cortex_latency_ms', 0):.0f}",
        )

    console.print(table)

    # ═══════════════════════════════════════════════════════════════════
    # False Positives — UNSUPPORTED claims that might actually be correct
    # ═══════════════════════════════════════════════════════════════════
    console.print("\n[bold yellow]Potential False Positives (UNSUPPORTED in normal queries)[/bold yellow]\n")

    fp_count = 0
    for r in ok_results:
        if r.get("adversarial"):
            continue
        for c in r.get("claims", []):
            if c["verdict"] == "UNSUPPORTED" and not c["grounded"]:
                fp_count += 1
                conf = c.get("confidence", 0)
                console.print(f"  [dim]Q{r['query_idx']+1}[/dim] [yellow]{c['text'][:80]}[/yellow]")
                console.print(f"       Confidence: {conf:.4f} (threshold: {threshold})")
                if c.get("reason"):
                    console.print(f"       Reason: {c['reason'][:100]}")
                # Flag borderline cases
                if conf > threshold - 0.15:
                    console.print(f"       [yellow]^ BORDERLINE — only {threshold - conf:.3f} below threshold[/yellow]")
                console.print()

    if fp_count == 0:
        console.print("  [green]None found.[/green]\n")
    else:
        console.print(f"  [yellow]Total potential false positives: {fp_count}[/yellow]\n")

    # ═══════════════════════════════════════════════════════════════════
    # Critical Misses — Adversarial corruptions not caught
    # ═══════════════════════════════════════════════════════════════════
    console.print("[bold red]Critical Misses (Adversarial Not Caught)[/bold red]\n")

    miss_count = 0
    for r in ok_results:
        if not r.get("adversarial"):
            continue
        if not r.get("adversarial_caught", False):
            miss_count += 1
            console.print(f"  [red bold]CRITICAL MISS — Q{r['query_idx']+1}[/red bold]")
            console.print(f"    Query: {r['query']}")
            console.print(f"    Corruption: {r.get('corruption_desc', '?')}")
            console.print(f"    HI: {r.get('hallucination_index', '?')}")
            console.print(f"    All claims grounded — corruption slipped through!")
            console.print()

    if miss_count == 0:
        console.print("  [green]All adversarial corruptions caught![/green]\n")

    # ═══════════════════════════════════════════════════════════════════
    # Verdict Breakdown
    # ═══════════════════════════════════════════════════════════════════
    console.print("[bold]Verdict Breakdown[/bold]\n")

    all_claims = []
    for r in ok_results:
        for c in r.get("claims", []):
            all_claims.append(c)

    verdict_table = Table(show_lines=True)
    verdict_table.add_column("Verdict", style="bold")
    verdict_table.add_column("Count", justify="right")
    verdict_table.add_column("Pct", justify="right")

    verdicts = {}
    for c in all_claims:
        v = c["verdict"]
        verdicts[v] = verdicts.get(v, 0) + 1

    total_claims = len(all_claims)
    for v in ["GROUNDED", "NUM_MISMATCH", "UNSUPPORTED", "OPINION"]:
        count = verdicts.get(v, 0)
        pct = f"{count/total_claims:.1%}" if total_claims > 0 else "0%"
        color = {"GROUNDED": "green", "NUM_MISMATCH": "red", "UNSUPPORTED": "yellow", "OPINION": "dim"}.get(v, "white")
        verdict_table.add_row(f"[{color}]{v}[/{color}]", str(count), pct)

    verdict_table.add_row("[bold]TOTAL[/bold]", f"[bold]{total_claims}[/bold]", "100%")
    console.print(verdict_table)

    # ═══════════════════════════════════════════════════════════════════
    # Final Verdict
    # ═══════════════════════════════════════════════════════════════════
    v = metrics.get("verdict", "?")
    v_color = {"PASS": "green", "WARN": "yellow", "FAIL": "red"}.get(v, "white")
    console.print(f"\n[bold {v_color}]{'='*40}[/bold {v_color}]")
    console.print(f"[bold {v_color}]  FINAL VERDICT: {v}[/bold {v_color}]")
    console.print(f"[bold {v_color}]{'='*40}[/bold {v_color}]")
    console.print(f"  Adversarial catch rate: {metrics.get('adversarial_catch_rate', 0):.0%}")
    console.print(f"  False positive rate: {metrics.get('false_positive_rate', 0):.1%}")
    console.print(f"  Avg latency: {metrics.get('avg_latency_ms', 0):.0f}ms")
    console.print()


def analyze_tuning(data: dict):
    """Analyze a threshold tuning run."""
    console.print("[bold cyan]Threshold Tuning Analysis[/bold cyan]\n")

    thresholds_data = data.get("thresholds", {})

    # Comparison table
    table = Table(show_lines=True, title="Threshold Comparison")
    table.add_column("Metric", style="bold")
    for t in sorted(thresholds_data.keys()):
        table.add_column(f"t={t}", justify="right")

    metrics_list = [thresholds_data[t]["metrics"] for t in sorted(thresholds_data.keys())]

    rows = [
        ("Verdict", [m.get("verdict", "?") for m in metrics_list]),
        ("Avg HI (normal)", [f"{m.get('avg_hi_normal', 0):.4f}" for m in metrics_list]),
        ("Adv Catch Rate", [f"{m.get('adversarial_catch_rate', 0):.0%}" for m in metrics_list]),
        ("False Positive Rate", [f"{m.get('false_positive_rate', 0):.1%}" for m in metrics_list]),
        ("Total Claims", [str(m.get("total_claims", 0)) for m in metrics_list]),
        ("Avg Latency (ms)", [f"{m.get('avg_latency_ms', 0):.0f}" for m in metrics_list]),
    ]

    for label, vals in rows:
        table.add_row(label, *vals)

    # Score = catch_rate - FP_rate
    scores = {}
    for t, m in zip(sorted(thresholds_data.keys()), metrics_list):
        scores[t] = m.get("adversarial_catch_rate", 0) - m.get("false_positive_rate", 0)

    best = max(scores, key=scores.get)
    table.add_row(
        "[bold]Score (catch - FP)[/bold]",
        *[f"[{'green bold' if t == best else 'white'}]{scores[t]:.3f}[/]" for t in sorted(scores.keys())],
    )

    console.print(table)
    console.print(f"\n[bold green]Optimal threshold: {best}[/bold green]")

    # Analyze each threshold
    for t in sorted(thresholds_data.keys()):
        console.print(f"\n{'─'*40}")
        console.print(f"[bold] Threshold = {t} [/bold]")
        analyze_stress_test({
            "results": thresholds_data[t]["results"],
            "metrics": thresholds_data[t]["metrics"],
            "threshold": float(t),
        })


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    data = load_results(path)

    if data.get("type") == "threshold_tuning":
        analyze_tuning(data)
    else:
        analyze_stress_test(data)


if __name__ == "__main__":
    main()
