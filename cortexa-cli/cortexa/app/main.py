"""Entry point — the cx command.

Usage:
    cx audit [--demo]            Full memory health audit
    cx trace "response" [--demo] Trace attribution for a response
    cx watch [--demo]            Live event stream
    cx health [--demo]           Quick health bar
    cx chat [--demo]             Interactive chat with verification
    cx diff MEMORY_ID [--demo]   Show what changed for a memory
    cx fix MEMORY_ID [--demo]    Propose fix for stale memory
    cx report [--format md|json] Full health report
    cx init                      First-run setup
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

from cortexa.app import display

app = typer.Typer(
    name="cx",
    help="Cortexa — Memory intelligence for AI agents",
    add_completion=False,
    no_args_is_help=True,
)


# ── Helpers ──────────────────────────────────────────────────────────

def _get_client(demo: bool = False):
    """Create a Cortexa client, optionally pre-loaded with demo data."""
    from cortexa.sdk.client import Cortexa

    cx = Cortexa(backend="memory")

    if demo:
        from cortexa.demo.dataset import generate_demo_memories

        memories = generate_demo_memories()

        async def _load():
            for m in memories:
                await cx.add_memory(m.content, source=m.source, metadata=m.metadata)

        _run(_load())

    return cx


def _get_demo_scenario(name: str = "shipping_trace"):
    """Load a demo scenario by name."""
    from cortexa.demo.scenarios import get_scenario

    return get_scenario(name)


def _run(coro):
    """Run an async coroutine."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


# ── Commands ─────────────────────────────────────────────────────────

@app.command()
def audit(
    demo: bool = typer.Option(False, "--demo", help="Run with demo data"),
) -> None:
    """Full memory health audit — ghosts, contradictions, stale memories."""
    display.banner()

    if demo:
        scenario = _get_demo_scenario("pricing_audit")
        with display.spinner("auditing memory store..."):
            from cortexa.sdk.client import Cortexa

            cx = Cortexa(backend="memory")
            result = _run(cx.audit(memories=scenario.memories))
            time.sleep(0.8)
    else:
        cx = _get_client(demo=False)
        with display.spinner("auditing memory store..."):
            result = _run(cx.audit())

    display.audit_summary(result)


@app.command()
def trace(
    response_text: str = typer.Argument(..., help="The LLM response to trace"),
    query: Optional[str] = typer.Option(None, "--query", "-q", help="The user query"),
    demo: bool = typer.Option(False, "--demo", help="Run with demo data"),
) -> None:
    """Trace attribution for an LLM response against memory store."""
    display.banner()

    if demo:
        scenario = _get_demo_scenario("shipping_trace")
        q = scenario.query
        resp = scenario.response

        with display.spinner("decomposing claims..."):
            time.sleep(0.6)

        with display.spinner("running attribution..."):
            from cortexa.sdk.client import Cortexa

            cx = Cortexa(backend="memory")
            result = _run(cx.trace(query=q, response=resp, memories=scenario.memories))
            time.sleep(0.4)
    else:
        cx = _get_client(demo=False)
        q = query or "user query"

        with display.spinner("decomposing claims..."):
            time.sleep(0.3)

        with display.spinner("running attribution..."):
            result = _run(cx.trace(query=q, response=response_text))

    display.trace_header(result.query, result.response)
    display.claim_tree(result.claims, result.attributions)
    display.health_bar(result.health_score, label="Trace Health")
    display.console.print()
    display.issues_section(result.ghost_tokens, result.contradictions, result.stale_memories)
    display.verdict_line(
        result.health_score,
        len(result.ghost_tokens),
        len(result.contradictions),
        len(result.stale_memories),
    )


@app.command()
def watch(
    demo: bool = typer.Option(False, "--demo", help="Stream synthetic events"),
) -> None:
    """Live event stream — watch memory operations in real-time."""
    display.banner()
    display.dim("Watching memory events... (Ctrl+C to stop)")
    display.console.print()

    if demo:
        _watch_demo()
    else:
        display.dim("Connect a live backend to stream real events.")
        display.dim("Use --demo to see synthetic events.")


def _watch_demo() -> None:
    """Generate synthetic watch events."""
    events = [
        {"type": "trace", "message": "trace shipping_query → 4 claims, MAS=0.82"},
        {"type": "ghost", "message": "GHOST mem_1203 flagged as ghost (MAS=0.12)"},
        {"type": "health", "message": "health check: 78/100"},
        {"type": "trace", "message": "trace pricing_query → 2 claims, MAS=0.95"},
        {"type": "contradiction", "message": "mem_0044 ↔ mem_0055 — conflicting thresholds"},
        {"type": "stale", "message": "mem_2847 stale (42d since source update)"},
        {"type": "trace", "message": "trace account_query → 3 claims, MAS=0.91"},
        {"type": "health", "message": "health check: 72/100"},
        {"type": "ghost", "message": "GHOST mem_0089 flagged as ghost (MAS=0.08)"},
        {"type": "trace", "message": "trace returns_query → 1 claim, MAS=0.97"},
    ]

    try:
        idx = 0
        while True:
            event = events[idx % len(events)]
            event["timestamp"] = datetime.utcnow().strftime("%H:%M:%S")
            display.watch_event(event)
            idx += 1
            time.sleep(random.uniform(1.0, 3.0))
    except KeyboardInterrupt:
        display.console.print()
        display.dim("Stream stopped.")


@app.command()
def health(
    demo: bool = typer.Option(False, "--demo", help="Run with demo data"),
) -> None:
    """Quick memory health score."""
    display.banner()

    if demo:
        scenario = _get_demo_scenario("shipping_trace")
        with display.spinner("checking health..."):
            from cortexa.sdk.client import Cortexa

            cx = Cortexa(backend="memory")
            result = _run(cx.audit(memories=scenario.memories))
            time.sleep(0.5)
        score = result.health_score
    else:
        cx = _get_client(demo=False)
        with display.spinner("checking health..."):
            score = _run(cx.health())

    display.health_bar(score)
    display.console.print()


@app.command()
def chat(
    demo: bool = typer.Option(False, "--demo", help="Use demo data for verification"),
) -> None:
    """Interactive chat with real-time memory verification."""
    display.banner()
    display.dim("Type a response to verify, or 'exit' to quit.")
    display.console.print()

    if demo:
        scenario = _get_demo_scenario("shipping_trace")
        from cortexa.sdk.client import Cortexa

        cx = Cortexa(backend="memory")
    else:
        cx = _get_client(demo=False)
        scenario = None

    while True:
        user_input = display.chat_prompt()
        if user_input is None or user_input.strip().lower() in ("exit", "quit", "q"):
            display.dim("Goodbye.")
            break

        text = user_input.strip()
        if not text:
            continue

        display.chat_tool_call("trace", f'"{text[:50]}..."' if len(text) > 50 else f'"{text}"')

        if demo and scenario:
            result = _run(cx.trace(
                query=scenario.query,
                response=text,
                memories=scenario.memories,
            ))
        else:
            result = _run(cx.trace(query="user query", response=text))

        display.console.print()
        display.claim_tree(result.claims, result.attributions)
        display.health_bar(result.health_score, label="Trace Health")
        display.console.print()
        display.issues_section(result.ghost_tokens, result.contradictions, result.stale_memories)
        display.verdict_line(
            result.health_score,
            len(result.ghost_tokens),
            len(result.contradictions),
            len(result.stale_memories),
        )


# ── Diff / Fix / Report / Init ────────────────────────────────────────

# Demo data for diff/fix commands
_DEMO_DIFFS = {
    "mem_2847": {
        "old": "Express delivery takes 2 business days for $9.99.",
        "current": "Express delivery takes 3-5 business days for $12.99.",
        "source": "shipping_policy.md",
        "days_old": 48,
    },
    "mem_1203": {
        "old": "User prefers dark mode and metric units.",
        "current": "User prefers dark mode and metric units.",
        "source": "user_preferences",
        "days_old": 60,
    },
    "mem_0089": {
        "old": "Returns accepted within 30 days of purchase.",
        "current": "Returns accepted within 14 days of purchase. Restocking fee of 15% applies.",
        "source": "returns_policy.md",
        "days_old": 90,
    },
}


@app.command()
def diff(
    memory_id: str = typer.Argument(..., help="Memory ID to diff"),
    demo: bool = typer.Option(False, "--demo", help="Use demo diff data"),
) -> None:
    """Show what changed between a memory and its source."""
    display.banner()

    if demo:
        info = _DEMO_DIFFS.get(memory_id)
        if not info:
            available = ", ".join(_DEMO_DIFFS.keys())
            display.error(f"Unknown demo memory: {memory_id}")
            display.dim(f"Available: {available}")
            return

        with display.spinner("comparing with source..."):
            time.sleep(0.5)

        display.diff_view(
            memory_id, info["old"], info["current"],
            info["source"], info["days_old"],
        )
    else:
        cx = _get_client(demo=False)
        memory = _run(cx.get_memory(memory_id))
        if not memory:
            display.error(f"Memory {memory_id} not found.")
            return
        display.dim(f"Memory: {memory.content}")
        display.dim(f"Source: {memory.source or 'unknown'}")
        display.dim("Live diff requires source integration.")


@app.command()
def fix(
    memory_id: str = typer.Argument(..., help="Memory ID to fix"),
    demo: bool = typer.Option(False, "--demo", help="Use demo fix data"),
) -> None:
    """Propose a fix for a stale memory."""
    display.banner()

    if demo:
        info = _DEMO_DIFFS.get(memory_id)
        if not info:
            available = ", ".join(_DEMO_DIFFS.keys())
            display.error(f"Unknown demo memory: {memory_id}")
            display.dim(f"Available: {available}")
            return

        with display.spinner("analyzing staleness..."):
            time.sleep(0.4)

        display.fix_proposal(memory_id, info["old"], info["current"])

        confirm = typer.confirm("  Apply fix?", default=False)
        if confirm:
            display.success(f"Updated {memory_id}")
        else:
            display.dim("Fix skipped.")
    else:
        cx = _get_client(demo=False)
        memory = _run(cx.get_memory(memory_id))
        if not memory:
            display.error(f"Memory {memory_id} not found.")
            return
        display.dim(f"Current: {memory.content}")
        display.dim("Automated fix requires source integration.")


@app.command()
def report(
    fmt: str = typer.Option("md", "--format", "-f", help="Output format: md or json"),
    demo: bool = typer.Option(False, "--demo", help="Run with demo data"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Write to file"),
) -> None:
    """Generate a full memory health report."""
    display.banner()

    if demo:
        scenario = _get_demo_scenario("pricing_audit")
        with display.spinner("generating report..."):
            from cortexa.sdk.client import Cortexa

            cx = Cortexa(backend="memory")
            result = _run(cx.audit(memories=scenario.memories))
            time.sleep(0.6)
    else:
        cx = _get_client(demo=False)
        with display.spinner("generating report..."):
            result = _run(cx.audit())

    if fmt == "json":
        data = {
            "health_score": result.health_score,
            "total_memories": result.total_memories,
            "ghost_count": result.ghost_count,
            "ghost_percentage": result.ghost_percentage,
            "contradiction_count": result.contradiction_count,
            "stale_count": result.stale_count,
            "estimated_waste_tokens": result.estimated_waste_tokens,
            "estimated_waste_cost_monthly": result.estimated_waste_cost_monthly,
            "contradictions": [
                {"id_1": c.memory_id_1, "id_2": c.memory_id_2, "explanation": c.explanation}
                for c in result.contradictions
            ],
            "stale_memories": [
                {"id": s.memory_id, "reason": s.reason, "days_old": s.days_since_update}
                for s in result.stale_memories
            ],
            "recommendations": result.recommendations,
        }
        text = json.dumps(data, indent=2)
    else:
        text = display.report_md(result)

    if output:
        Path(output).write_text(text)
        display.success(f"Report written to {output}")
    else:
        display.console.print(text)


@app.command()
def init() -> None:
    """First-run setup — configure backend and API keys."""
    display.banner()
    display.dim("Setting up Cortexa configuration.")
    display.console.print()

    backend = typer.prompt("  Backend", default="memory", type=str)
    api_key = ""
    if backend == "api":
        api_key = typer.prompt("  Anthropic API key", hide_input=True)

    config_dir = Path.home() / ".cortexa"
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / "config.toml"

    lines = [
        "[cortexa]",
        f'backend = "{backend}"',
    ]
    if api_key:
        lines.append(f'api_key = "{api_key}"')

    config_path.write_text("\n".join(lines) + "\n")
    display.init_success(str(config_path))


# ── Entry Point ──────────────────────────────────────────────────────

def run() -> None:
    """Main entry point for the cx command."""
    app()


if __name__ == "__main__":
    run()
