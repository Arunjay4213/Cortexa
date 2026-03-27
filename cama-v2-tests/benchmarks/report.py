"""Report generator — markdown report from benchmark results."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def generate_report(
    synthetic_results_path: str | None = None,
    latency_results_path: str | None = None,
    realworld_results_path: str | None = None,
    realworld_lettuce_path: str | None = None,
    output_path: str = "BENCHMARK_REPORT.md",
) -> str:
    """Generate a markdown benchmark report.

    Args:
        synthetic_results_path: Path to synthetic benchmark JSON.
        latency_results_path: Path to latency benchmark JSON.
        realworld_results_path: Path to real-world (EmbeddingDetector) results JSON.
        realworld_lettuce_path: Path to real-world (LettuceDetect) results JSON.
        output_path: Where to write the markdown report.

    Returns:
        The markdown report as a string.
    """
    lines = [
        f"# CAMA v2 Benchmark Report",
        f"",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
    ]

    # Target metrics table
    lines += [
        "## Target Metrics",
        "",
        "| Metric | Target | Status |",
        "|--------|--------|--------|",
    ]

    targets = {
        "Attribution P@1": (">60%", None),
        "Attribution P@3": (">80%", None),
        "Ghost Recall": (">70%", None),
        "Ghost Precision": (">60%", None),
        "Stale Detection Rate": (">95%", None),
        "Mean Latency (CPU)": ("<2000ms", None),
    }

    # Load synthetic results
    synthetic = None
    if synthetic_results_path and Path(synthetic_results_path).exists():
        synthetic = json.loads(Path(synthetic_results_path).read_text())
        s = synthetic["summary"]
        targets["Attribution P@1"] = (">60%", f"{s['p_at_1']:.1%}")
        targets["Attribution P@3"] = (">80%", f"{s['p_at_3']:.1%}")
        targets["Ghost Recall"] = (">70%", f"{s['ghost_recall']:.1%}")
        targets["Ghost Precision"] = (">60%", f"{s['ghost_precision']:.1%}")
        targets["Stale Detection Rate"] = (">95%", f"{s['stale_rate']:.1%}")
        targets["Mean Latency (CPU)"] = ("<2000ms", f"{s['mean_latency_ms']:.0f}ms")

    for metric, (target, actual) in targets.items():
        status = actual if actual else "not run"
        # Check pass/fail
        if actual:
            passed = _check_target(target, actual)
            emoji = "PASS" if passed else "FAIL"
            status = f"{actual} ({emoji})"
        lines.append(f"| {metric} | {target} | {status} |")

    lines.append("")

    # Synthetic benchmark details
    if synthetic:
        s = synthetic["summary"]
        lines += [
            "## Synthetic Benchmark",
            "",
            f"- Total cases: {s['total_cases']}",
            f"- Cases with hallucinated spans: {s['cases_with_spans']}",
            f"- Attribution P@1: {s['p_at_1']:.1%}",
            f"- Attribution P@3: {s['p_at_3']:.1%}",
            f"- Ghost Precision: {s['ghost_precision']:.1%}",
            f"- Ghost Recall: {s['ghost_recall']:.1%}",
            f"- Direction Accuracy: {s['direction_accuracy']:.1%}",
            f"- Stale Detection Rate: {s['stale_rate']:.1%}",
            f"- Mean Latency: {s['mean_latency_ms']:.0f}ms",
            f"- P95 Latency: {s['p95_latency_ms']:.0f}ms",
            "",
        ]

    # Real-world scenario results
    realworld = None
    realworld_lettuce = None
    if realworld_results_path and Path(realworld_results_path).exists():
        realworld = json.loads(Path(realworld_results_path).read_text())
    if realworld_lettuce_path and Path(realworld_lettuce_path).exists():
        realworld_lettuce = json.loads(Path(realworld_lettuce_path).read_text())

    if realworld_lettuce:
        lines += _generate_realworld_section(realworld_lettuce, label="LettuceDetect + NLI")
    elif realworld:
        lines += _generate_realworld_section(realworld, label="EmbeddingDetector + NLI")

    # Detector comparison
    if realworld and realworld_lettuce:
        lines += _generate_detector_comparison(realworld, realworld_lettuce)

    # Latency benchmark details
    latency = None
    if latency_results_path and Path(latency_results_path).exists():
        latency = json.loads(Path(latency_results_path).read_text())
        lines += [
            "## Latency Benchmark",
            "",
            "| Config | Memories | Sentences | Mean (ms) | Min (ms) | Max (ms) | P95 (ms) |",
            "|--------|----------|-----------|-----------|----------|----------|----------|",
        ]
        for name, entry in latency.items():
            lines.append(
                f"| {name} | {entry['n_memories']} | {entry['response_sentences']} | "
                f"{entry['mean_ms']:.0f} | {entry['min_ms']:.0f} | "
                f"{entry['max_ms']:.0f} | {entry['p95_ms']:.0f} |"
            )
        lines.append("")

    report = "\n".join(lines)
    Path(output_path).write_text(report)
    return report


def _generate_realworld_section(realworld: dict, label: str = "EmbeddingDetector + NLI") -> list[str]:
    """Generate the real-world benchmark section of the report."""
    lines = [
        f"## Real-World Scenario Benchmark ({label})",
        "",
    ]

    scenarios = realworld.get("scenarios", [])
    aggregate = realworld.get("aggregate", {})

    # Per-scenario table
    lines += [
        "### Per-Scenario Results",
        "",
        "| Scenario | P@1 | Ghost P | Ghost R | Ghost F1 | Contra P | Contra R | Stale | Latency |",
        "|----------|-----|---------|---------|----------|----------|----------|-------|---------|",
    ]

    realworld_targets = {
        "p_at_1": (">85%", ">75%"),  # (realistic, adversarial)
        "ghost_f1": ">65%",
        "ghost_precision": ">60%",
        "latency_ms": "<1000",
    }

    for s in scenarios:
        name = s.get("scenario_name", "?")
        p1 = s.get("p_at_1", 0)
        gp = s.get("ghost_precision", 0)
        gr = s.get("ghost_recall", 0)
        gf = s.get("ghost_f1", 0)
        cp = s.get("contradiction_precision", 0)
        cr = s.get("contradiction_recall", 0)
        sr = s.get("stale_rate", 0)
        lat = s.get("mean_latency_ms", 0)

        lines.append(
            f"| {name} | {p1:.0%} | {gp:.0%} | {gr:.0%} | {gf:.0%} "
            f"| {cp:.0%} | {cr:.0%} | {sr:.0%} | {lat:.0f}ms |"
        )

    lines.append("")

    # Aggregate summary with pass/fail
    if aggregate:
        lines += [
            "### Aggregate Results",
            "",
            "| Metric | Target | Actual | Status |",
            "|--------|--------|--------|--------|",
        ]

        agg_checks = [
            ("P@1 (overall)", ">85%", aggregate.get("p_at_1", 0)),
            ("Ghost Precision", ">60%", aggregate.get("ghost_precision", 0)),
            ("Ghost F1", ">65%", aggregate.get("ghost_f1", 0)),
            ("Contradiction Precision", ">50%", aggregate.get("contradiction_precision", 0)),
            ("Contradiction Recall", ">50%", aggregate.get("contradiction_recall", 0)),
            ("Mean Latency", "<1000ms", aggregate.get("mean_latency_ms", 0)),
        ]

        for metric, target, value in agg_checks:
            if "ms" in target:
                actual_str = f"{value:.0f}ms"
            else:
                actual_str = f"{value:.1%}"
            passed = _check_target(target, actual_str)
            status = "PASS" if passed else "FAIL"
            lines.append(f"| {metric} | {target} | {actual_str} | {status} |")

        lines += [
            "",
            f"- Total scenarios: {aggregate.get('total_scenarios', len(scenarios))}",
            "",
        ]

    return lines


def _generate_detector_comparison(embed_results: dict, lettuce_results: dict) -> list[str]:
    """Generate side-by-side comparison of EmbeddingDetector vs LettuceDetect."""
    lines = [
        "## Detector Comparison: EmbeddingDetector vs LettuceDetect",
        "",
        "### Per-Scenario P@1",
        "",
        "| Scenario | Embed P@1 | Lettuce P@1 | Delta |",
        "|----------|-----------|-------------|-------|",
    ]

    embed_scenarios = {s["scenario_name"]: s for s in embed_results.get("scenarios", [])}
    lettuce_scenarios = {s["scenario_name"]: s for s in lettuce_results.get("scenarios", [])}

    all_names = list(embed_scenarios.keys()) or list(lettuce_scenarios.keys())
    for name in all_names:
        e = embed_scenarios.get(name, {})
        l = lettuce_scenarios.get(name, {})
        ep1 = e.get("p_at_1", 0)
        lp1 = l.get("p_at_1", 0)
        delta = lp1 - ep1
        sign = "+" if delta > 0 else ""
        lines.append(f"| {name} | {ep1:.0%} | {lp1:.0%} | {sign}{delta:.0%} |")

    # Aggregate row
    ea = embed_results.get("aggregate", {})
    la = lettuce_results.get("aggregate", {})
    ep1 = ea.get("p_at_1", 0)
    lp1 = la.get("p_at_1", 0)
    delta = lp1 - ep1
    sign = "+" if delta > 0 else ""
    lines.append(f"| **Aggregate** | **{ep1:.1%}** | **{lp1:.1%}** | **{sign}{delta:.1%}** |")
    lines.append("")

    # Full metrics comparison
    lines += [
        "### Aggregate Metrics Comparison",
        "",
        "| Metric | EmbeddingDetector | LettuceDetect | Delta |",
        "|--------|-------------------|---------------|-------|",
    ]

    metrics = [
        ("P@1", "p_at_1", True),
        ("Ghost Precision", "ghost_precision", True),
        ("Ghost Recall", "ghost_recall", True),
        ("Ghost F1", "ghost_f1", True),
        ("Contradiction P", "contradiction_precision", True),
        ("Contradiction R", "contradiction_recall", True),
        ("Mean Latency", "mean_latency_ms", False),
    ]

    for label, key, is_pct in metrics:
        ev = ea.get(key, 0)
        lv = la.get(key, 0)
        d = lv - ev
        if is_pct:
            sign = "+" if d > 0 else ""
            lines.append(f"| {label} | {ev:.1%} | {lv:.1%} | {sign}{d:.1%} |")
        else:
            sign = "+" if d > 0 else ""
            lines.append(f"| {label} | {ev:.0f}ms | {lv:.0f}ms | {sign}{d:.0f}ms |")

    lines.append("")
    return lines


def _check_target(target: str, actual: str) -> bool:
    """Check if actual meets target (e.g., '>60%' vs '65.3%')."""
    try:
        if target.startswith(">"):
            target_val = float(target[1:].replace("%", "").replace("ms", ""))
            actual_val = float(actual.replace("%", "").replace("ms", ""))
            return actual_val > target_val
        elif target.startswith("<"):
            target_val = float(target[1:].replace("%", "").replace("ms", ""))
            actual_val = float(actual.replace("%", "").replace("ms", ""))
            return actual_val < target_val
    except ValueError:
        pass
    return False


if __name__ == "__main__":
    report = generate_report(
        synthetic_results_path="benchmark_results_v2.json",
        latency_results_path="latency_results.json",
        realworld_results_path="realworld_results.json",
        realworld_lettuce_path="realworld_results_v2_lettuce.json",
    )
    print(report)
