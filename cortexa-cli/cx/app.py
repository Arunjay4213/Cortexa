"""Cortexa — full-screen Textual application for memory intelligence."""

from __future__ import annotations

import asyncio
import json
import os
import random
from datetime import datetime
from typing import Union

from rich.text import Text
from textual.app import App, ComposeResult
from textual.events import Click, Key
from textual.timer import Timer
from textual.widgets import Footer, Input

from cx.agent.agent import CortexaAgent
from cx.ui.formatters import (
    format_action_prompt,
    format_audit_report,
    format_config,
    format_contradictions,
    format_ghost_list,
    format_health_summary,
    format_help,
    format_memory_card,
    format_search_results,
    format_stale_list,
    format_startup_step,
    format_trace_results,
    format_watch_event,
)
from cx.widgets.header_bar import HeaderBar
from cx.widgets.conversation import ConversationView
from cx.widgets.input_bar import InputBar
from cx.widgets.message import MessageBubble
from cx.widgets.tool_call import ToolCallWidget
from cx.widgets.thinking import ThinkingIndicator
from cx.widgets.watch_sparkline import WatchSparkline


# Slash commands handled locally (no agent needed)
SLASH_COMMANDS = {
    "/help": "Show available commands.",
    "/audit": "Run a full memory health audit.",
    "/health": "Quick health summary.",
    "/watch": "Start live memory event stream.",
    "/trace": "Trace memory attribution for a query.",
    "/search": "Search the memory store.",
    "/contradictions": "Find contradicting memories.",
    "/ghosts": "List ghost token memories.",
    "/stale": "List stale memories.",
    "/memory": "Inspect a specific memory by ID.",
    "/fix": "Apply a fix to a memory.",
    "/config": "Show current configuration.",
    "/export": "Export audit report.",
    "/clear": "Clear conversation history.",
    "/quit": "Exit Cortexa.",
}


class CortexaApp(App):
    """One app. One command. cx."""

    CSS_PATH = "theme.tcss"
    TITLE = "cortexa"
    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+h", "health", "Health"),
        ("f2", "audit", "Audit"),
        ("f3", "watch_toggle", "Watch"),
        ("f4", "export_audit", "Export"),
        ("ctrl+l", "clear_all", "Clear"),
    ]

    def __init__(self, demo: bool = False) -> None:
        super().__init__()
        self._demo = demo
        self.adapter = None
        self._agent: CortexaAgent | None = None
        self._tool_widgets: dict[str, ToolCallWidget] = {}
        self._pending_action: dict | None = None  # {memory_id, action, new_content}
        self._watch_timer: Timer | None = None
        self._watch_rng = random.Random(0)
        self._watch_sparkline: WatchSparkline | None = None
        self._setup_step: str | None = None  # tracks first-run wizard state
        self._input_history: list[str] = []
        self._history_index: int = -1

    def compose(self) -> ComposeResult:
        yield HeaderBar()
        yield ConversationView(id="conversation")
        yield InputBar()
        yield Footer()

    def on_mount(self) -> None:
        """Initialize adapter and display welcome message."""
        if self._demo:
            self.run_worker(self._demo_startup(), exclusive=True)
        elif self.adapter:
            self._agent = CortexaAgent(self.adapter)
            from cx.ui.theme import get_banner
            from cx import __version__
            banner = Text()
            banner.append(f"cortexa ", style="#00D4E8 bold")
            banner.append(f"v{__version__}", style="#4A4A6A")
            banner.append(" \u2014 memory intelligence for AI agents\n", style="#555570")
            banner.append("type a question or /help to get started", style="#555570")
            self._append_message(banner, role="system")
        else:
            self._start_first_run_setup()

        # Focus the input
        self.query_one("#prompt-input").focus()

    async def _demo_startup(self) -> None:
        """Progressive demo startup — animated reveal."""
        from cx.adapters.demo import DemoAdapter
        from cx.core.auditor import run_audit

        delay = 0.3

        self._append_message(
            format_startup_step("Initializing Cortexa...", "pending"),
            role="system",
        )
        await asyncio.sleep(delay)

        self._append_message(
            format_startup_step("Connecting to demo memory store...", "pending"),
            role="system",
        )
        adapter = DemoAdapter()
        adapter.connect()
        self.adapter = adapter
        await asyncio.sleep(delay)

        memories = adapter.list_memories()
        collections = adapter.list_collections()
        header = self.query_one(HeaderBar)
        header.connected = True
        header.mode = "demo"
        header.memory_count = len(memories)
        self._append_message(
            format_startup_step(
                "Connected",
                "done",
                f"{len(memories)} memories across {len(collections)} collections",
            ),
            role="agent",
        )
        await asyncio.sleep(delay)

        self._append_message(
            format_startup_step("Scanning for ghost tokens...", "pending"),
            role="system",
        )
        await asyncio.sleep(delay)
        report = run_audit(adapter)
        header.ghost_count = len(report.ghost_tokens)
        header.contradiction_count = len(report.contradictions)
        self._append_message(
            format_startup_step(
                "Found ghost tokens",
                "done",
                f"{len(report.ghost_tokens)} ghost tokens ({report.ghost_pct:.1f}% of store)",
            ),
            role="agent",
        )
        await asyncio.sleep(delay)

        self._append_message(
            format_startup_step("Detecting contradictions...", "pending"),
            role="system",
        )
        await asyncio.sleep(delay)
        self._append_message(
            format_startup_step(
                "Found contradictions",
                "done",
                f"{len(report.contradictions)} contradiction pairs",
            ),
            role="agent",
        )
        await asyncio.sleep(delay)

        score = report.health_score
        header.health_score = score
        if score >= 75:
            verdict = "Healthy"
        elif score >= 40:
            verdict = "Needs attention"
        else:
            verdict = "Critical"
        self._append_message(
            format_startup_step(
                "Health score",
                "done",
                f"{score:.1f}/100 \u2014 {verdict}",
            ),
            role="agent",
        )
        await asyncio.sleep(delay)

        self._agent = CortexaAgent(adapter)
        # Update header sparkline
        header.update_mas_from_adapter(adapter)
        await self._typewrite_message(
            "\nReady. Type a question or /help to get started.",
            role="system",
        )

    # ── Focus guard ────────────────────────────────────────────────

    def on_click(self, event: Click) -> None:
        """Keep focus pinned to the input — clicking conversation area won't steal it."""
        self.query_one("#prompt-input", Input).focus()

    # ── Input handling ───────────────────────────────────────────────

    def on_key(self, event: Key) -> None:
        """Handle up/down arrow for input history navigation."""
        if event.key not in ("up", "down"):
            return
        if not self._input_history:
            return

        inp = self.query_one("#prompt-input", Input)
        if not inp.has_focus:
            return

        if event.key == "up":
            if self._history_index == -1:
                self._history_index = len(self._input_history) - 1
            elif self._history_index > 0:
                self._history_index -= 1
            else:
                return
            inp.value = self._input_history[self._history_index]
            inp.cursor_position = len(inp.value)
            event.prevent_default()

        elif event.key == "down":
            if self._history_index == -1:
                return
            elif self._history_index < len(self._input_history) - 1:
                self._history_index += 1
                inp.value = self._input_history[self._history_index]
            else:
                self._history_index = -1
                inp.value = ""
            inp.cursor_position = len(inp.value)
            event.prevent_default()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user pressing Enter in the input bar."""
        text = event.value.strip()
        if not text:
            return

        # Clear input + flash feedback
        event.input.value = ""
        try:
            self.query_one(InputBar).flash()
        except Exception:
            pass

        # First-run setup intercept
        if self._handle_setup_input(text):
            return

        # Check for pending action prompt — handle y/n
        if self._pending_action and text.lower() in ("y", "yes"):
            self._apply_pending_action(True)
            return
        if self._pending_action and text.lower() in ("n", "no"):
            self._apply_pending_action(False)
            return

        # Save to history
        self._input_history.append(text)
        self._history_index = -1

        # Show user message in conversation
        self._append_message(text, role="user")

        # Route to handler
        if text.startswith("/"):
            self._handle_slash_command(text)
        else:
            self._handle_natural_language(text)

    # ── Slash command routing ────────────────────────────────────────

    def _handle_slash_command(self, text: str) -> None:
        """Route slash commands."""
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("/quit", "/exit", "/q"):
            self.exit()
        elif cmd == "/clear":
            self._clear_conversation()
        elif cmd == "/help":
            self._show_help()
        elif cmd == "/health":
            self._run_health()
        elif cmd == "/audit":
            self._run_audit()
        elif cmd == "/watch":
            self._run_watch()
        elif cmd == "/ghosts":
            self._run_ghosts()
        elif cmd == "/stale":
            self._run_stale()
        elif cmd == "/contradictions":
            self._run_contradictions()
        elif cmd == "/search":
            if arg:
                self._run_search(arg)
            else:
                self._append_message("Usage: /search <query>", role="error")
        elif cmd == "/trace":
            if arg:
                self._run_trace(arg)
            else:
                self._append_message("Usage: /trace <text>", role="error")
        elif cmd == "/memory":
            if arg:
                self._run_memory_detail(arg)
            else:
                self._append_message("Usage: /memory <memory_id>", role="error")
        elif cmd == "/config":
            self._show_config()
        elif cmd == "/export":
            self._run_export()
        elif cmd == "/fix":
            if arg:
                self._run_fix(arg)
            else:
                self._append_message("Usage: /fix <memory_id> <action> [new_content]", role="error")
        else:
            self._append_message(f"Unknown command: {cmd}. Type /help for available commands.", role="error")

    def _handle_natural_language(self, text: str) -> None:
        """Route natural language input to the Claude agent."""
        if not self._agent:
            self._append_message(
                "No adapter connected. Use --demo or configure an adapter first.",
                role="error",
            )
            return
        self.run_worker(self._run_agent(text), exclusive=True)

    async def _run_agent(self, text: str) -> None:
        """Run the agent loop in a worker."""
        await self._agent.send_message(text, on_event=self._on_agent_event)

    def _dismiss_thinking(self) -> None:
        """Remove any active ThinkingIndicator."""
        for indicator in self.query(ThinkingIndicator):
            indicator.dismiss()

    async def _on_agent_event(self, event: dict) -> None:
        """Handle progressive events from the agent."""
        etype = event["type"]
        conv = self.query_one("#conversation", ConversationView)

        if etype == "text":
            self._dismiss_thinking()
            bubble = MessageBubble(event["content"], role="agent")
            conv.mount(bubble)
            conv.scroll_end(animate=False)

        elif etype == "tool_start":
            self._dismiss_thinking()
            widget = ToolCallWidget(
                tool_name=event["name"],
                tool_input_summary=event["input_summary"],
            )
            self._tool_widgets[event["id"]] = widget
            conv.mount(widget)
            conv.scroll_end(animate=False)

        elif etype == "tool_end":
            widget = self._tool_widgets.pop(event["id"], None)
            if widget:
                widget.complete(event["summary"], event.get("detail", ""))
            # Show thinking indicator while agent processes next step
            indicator = ThinkingIndicator()
            conv.mount(indicator)
            conv.scroll_end(animate=False)

        elif etype == "error":
            self._dismiss_thinking()
            bubble = MessageBubble(event["content"], role="error")
            conv.mount(bubble)
            conv.scroll_end(animate=False)

    # ── Slash command implementations ────────────────────────────────

    def _show_help(self) -> None:
        self._append_message(format_help(SLASH_COMMANDS), role="system")

    def _clear_conversation(self) -> None:
        conv = self.query_one("#conversation", ConversationView)
        conv.remove_children()
        self._tool_widgets.clear()
        self._pending_action = None
        if self._watch_timer:
            self._watch_timer.stop()
            self._watch_timer = None
        if self._watch_sparkline:
            self._watch_sparkline.remove()
            self._watch_sparkline = None
        if self._agent:
            self._agent.clear_history()
        self._append_message("Conversation cleared.", role="system")
        self.notify("Conversation cleared")

    def _show_config(self) -> None:
        from cx.config import CortexaConfig

        cfg = CortexaConfig.load()
        self._append_message(format_config(cfg), role="system")

    def _run_health(self) -> None:
        if not self.adapter:
            self._append_message("No adapter connected. Use --demo or configure an adapter.", role="error")
            return

        from cx.core.auditor import run_audit

        report = run_audit(self.adapter)
        self._append_message(format_health_summary(report), role="agent")

    def _run_audit(self) -> None:
        if not self.adapter:
            self._append_message("No adapter connected. Use --demo or configure an adapter.", role="error")
            return
        self.run_worker(self._animated_audit(), exclusive=True)

    async def _animated_audit(self) -> None:
        """Progressive audit scan with animated reveal."""
        from cx.core.auditor import run_audit

        delay = 0.3
        self._append_message(format_startup_step("scanning memories...", "pending"), role="system")
        await asyncio.sleep(delay)
        report = run_audit(self.adapter)
        self._append_message(
            format_startup_step("scanned memories", "done", f"{report.total_memories} memories"),
            role="agent",
        )
        await asyncio.sleep(delay)

        self._append_message(format_startup_step("detecting ghosts...", "pending"), role="system")
        await asyncio.sleep(delay)
        self._append_message(
            format_startup_step("found ghosts", "done", f"{len(report.ghost_tokens)} ghosts"),
            role="agent",
        )
        await asyncio.sleep(delay)

        self._append_message(
            format_startup_step("checking contradictions...", "pending"), role="system"
        )
        await asyncio.sleep(delay)
        self._append_message(
            format_startup_step(
                "found contradictions", "done", f"{len(report.contradictions)} contradiction pairs"
            ),
            role="agent",
        )
        await asyncio.sleep(delay)

        self._append_message(format_audit_report(report), role="agent")

        # Mount MAS chart
        try:
            from cx.widgets.mas_chart import MASChart

            memories = self.adapter.list_memories()
            scores = [m.mas_score for m in memories if m.mas_score is not None]
            if scores:
                conv = self.query_one("#conversation", ConversationView)
                conv.mount(MASChart(scores))
                conv.scroll_end(animate=False)
        except Exception:
            pass

        # Update header
        header = self.query_one(HeaderBar)
        header.health_score = report.health_score
        header.ghost_count = len(report.ghost_tokens)
        header.contradiction_count = len(report.contradictions)
        header.update_mas_from_adapter(self.adapter)

    def _run_ghosts(self) -> None:
        if not self.adapter:
            self._append_message("No adapter connected.", role="error")
            return

        from cx.core.auditor import run_audit

        report = run_audit(self.adapter)
        if not report.ghost_tokens:
            self._append_message("No ghost tokens found.", role="agent")
            return

        self._append_message(format_ghost_list(report.ghost_tokens), role="agent")

    def _run_stale(self) -> None:
        if not self.adapter:
            self._append_message("No adapter connected.", role="error")
            return

        from datetime import datetime

        memories = self.adapter.list_memories()
        now = datetime.now()
        stale = []
        for m in memories:
            if m.last_accessed:
                days = (now - m.last_accessed).days
                if days > 30:
                    stale.append((m, days))
        stale.sort(key=lambda x: x[1], reverse=True)

        if not stale:
            self._append_message("No stale memories found.", role="agent")
            return

        self._append_message(format_stale_list(stale), role="agent")

    def _run_contradictions(self) -> None:
        if not self.adapter:
            self._append_message("No adapter connected.", role="error")
            return

        if not hasattr(self.adapter, "get_contradictions"):
            self._append_message("Adapter does not support contradiction detection.", role="error")
            return

        contradictions = self.adapter.get_contradictions()
        if not contradictions:
            self._append_message("No contradictions found.", role="agent")
            return

        self._append_message(format_contradictions(contradictions), role="agent")

    def _run_search(self, query: str) -> None:
        if not self.adapter:
            self._append_message("No adapter connected.", role="error")
            return

        memories = self.adapter.list_memories()
        results = []
        for m in memories:
            if any(w.lower() in m.content.lower() for w in query.split() if len(w) > 2):
                results.append(m)
        results.sort(key=lambda m: m.mas_score or 0, reverse=True)

        if not results:
            self._append_message(f"No memories matching '{query}'.", role="agent")
            return

        self._append_message(format_search_results(results, query), role="agent")

    def _run_trace(self, text: str) -> None:
        if not self.adapter:
            self._append_message("No adapter connected.", role="error")
            return

        memories = self.adapter.list_memories()
        matches = []
        for m in memories:
            if any(w.lower() in m.content.lower() for w in text.split() if len(w) > 3):
                matches.append(m)
        matches.sort(key=lambda m: m.mas_score or 0, reverse=True)

        if not matches:
            self._append_message(f"No memories attributed to '{text}'.", role="agent")
            return

        self._append_message(format_trace_results(matches, text), role="agent")

    def _run_memory_detail(self, memory_id: str) -> None:
        if not self.adapter:
            self._append_message("No adapter connected.", role="error")
            return

        mem = self.adapter.get_memory(memory_id)
        if not mem:
            self._append_message(f"Memory '{memory_id}' not found.", role="error")
            return

        t = Text()
        t.append("Memory Detail\n\n", style="bold #e4e4ef")
        t.append_text(format_memory_card(mem))
        self._append_message(t, role="agent")

    # ── Export ─────────────────────────────────────────────────────────

    def _run_export(self) -> None:
        if not self.adapter:
            self._append_message("No adapter connected.", role="error")
            return

        from cx.core.auditor import run_audit

        report = run_audit(self.adapter)
        export = {
            "timestamp": datetime.now().isoformat(),
            "health_score": report.health_score,
            "total_memories": report.total_memories,
            "ghost_pct": report.ghost_pct,
            "ghost_count": len(report.ghost_tokens),
            "contradiction_count": len(report.contradictions),
            "stale_count": report.stale_count,
            "mas_avg": report.mas_avg,
            "mas_high": report.mas_high_count,
            "mas_mid": report.mas_mid_count,
            "mas_low": report.mas_low_count,
            "token_waste_per_day": report.estimated_token_waste_per_day,
            "cost_waste_per_day": report.estimated_cost_waste_per_day,
            "ghost_tokens": [
                {"id": g.memory_id, "reason": g.reason, "mas": g.mas_score}
                for g in report.ghost_tokens
            ],
            "contradictions": [
                {"a": c.memory_a_id, "b": c.memory_b_id, "explanation": c.explanation}
                for c in report.contradictions
            ],
        }
        fname = f"cortexa-audit-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        path = os.path.join(os.getcwd(), fname)
        with open(path, "w") as f:
            json.dump(export, f, indent=2)
        self._append_message(f"Audit exported to {path}", role="agent")
        self.notify(f"Exported to {fname}")

    # ── Fix with confirmation ────────────────────────────────────────

    def _run_fix(self, arg: str) -> None:
        if not self.adapter:
            self._append_message("No adapter connected.", role="error")
            return

        parts = arg.split(maxsplit=2)
        if len(parts) < 2:
            self._append_message("Usage: /fix <memory_id> <delete|update|archive> [new_content]", role="error")
            return

        memory_id = parts[0]
        action = parts[1]
        new_content = parts[2] if len(parts) > 2 else ""

        if action not in ("delete", "update", "archive"):
            self._append_message(f"Unknown action: {action}. Use delete, update, or archive.", role="error")
            return

        mem = self.adapter.get_memory(memory_id)
        if not mem:
            self._append_message(f"Memory '{memory_id}' not found.", role="error")
            return

        self._pending_action = {
            "memory_id": memory_id,
            "action": action,
            "new_content": new_content,
        }
        self._append_message(format_action_prompt(mem, action), role="warning")

    def _apply_pending_action(self, confirm: bool) -> None:
        """Resolve the pending action prompt."""
        ctx = self._pending_action
        if not ctx:
            return
        self._pending_action = None

        if confirm:
            mid = ctx["memory_id"]
            action = ctx["action"]
            if action == "delete":
                ok = self.adapter.delete_memory(mid)
            elif action == "archive":
                ok = self.adapter.archive_memory(mid)
            elif action == "update":
                ok = self.adapter.update_memory(mid, ctx.get("new_content", ""))
            else:
                ok = False
            if ok:
                self._append_message(f"\u2713 Applied: {action} {mid}", role="agent")
                self.notify(f"\u2713 Memory {mid} {action}d")
            else:
                self._append_message(f"Failed to {action} {mid}", role="error")
        else:
            self._append_message("\u2717 Action cancelled.", role="system")

    # ── Watch mode ─────────────────────────────────────────────────

    def _run_watch(self) -> None:
        if not self.adapter:
            self._append_message("No adapter connected.", role="error")
            return

        if self._watch_timer is not None:
            # Stop watching
            self._watch_timer.stop()
            self._watch_timer = None
            if self._watch_sparkline:
                self._watch_sparkline.remove()
                self._watch_sparkline = None
            self._append_message("Watch stopped.", role="system")
            self.notify("Watch mode stopped")
            return

        self._append_message("Watching memory events... (type /watch again to stop)", role="system")
        # Mount live sparkline
        conv = self.query_one("#conversation", ConversationView)
        self._watch_sparkline = WatchSparkline()
        conv.mount(self._watch_sparkline)
        conv.scroll_end(animate=False)
        self._watch_timer = self.set_interval(2.0, self._emit_watch_event)
        self.notify("Watch mode active")

    def _emit_watch_event(self) -> None:
        """Emit a simulated memory event (demo) or read from event log."""
        if not self.adapter:
            if self._watch_timer:
                self._watch_timer.stop()
                self._watch_timer = None
            return

        memories = self.adapter.list_memories()
        if not memories:
            return

        mem = self._watch_rng.choice(memories)
        event_types = ["access", "access", "access", "mas_update", "query_hit"]
        etype = self._watch_rng.choice(event_types)
        ts = datetime.now().strftime("%H:%M:%S")

        if etype == "mas_update":
            delta = self._watch_rng.uniform(-0.05, 0.05)
            old_mas = mem.mas_score or 0
            new_mas = max(0, min(1, old_mas + delta))
            details = {"delta": delta, "old_mas": old_mas, "new_mas": new_mas}
        else:
            details = None

        self._append_message(
            format_watch_event(etype, mem, ts, details),
            role="system",
        )
        # Feed sparkline
        if self._watch_sparkline and mem.mas_score is not None:
            self._watch_sparkline.add_score(mem.mas_score)

    # ── First-run setup ──────────────────────────────────────────────

    def _start_first_run_setup(self) -> None:
        """Start the first-run configuration wizard."""
        self._setup_step = "welcome"
        self._append_message(
            "Welcome to Cortexa \u2014 memory intelligence for AI agents.\n\n"
            "It looks like this is your first run. Let's get you set up.\n"
            "Which adapter would you like to use?\n\n"
            "  [1] demo     \u2014 Synthetic data for exploration\n"
            "  [2] mem0     \u2014 Connect to Mem0\n"
            "  [3] custom   \u2014 Custom adapter (advanced)\n\n"
            "Type a number (or 'demo' to start exploring):",
            role="system",
        )

    def _handle_setup_input(self, text: str) -> bool:
        """Handle input during first-run setup. Returns True if consumed."""
        if self._setup_step is None:
            return False

        if self._setup_step == "welcome":
            choice = text.strip().lower()
            if choice in ("1", "demo"):
                from cx.adapters.demo import DemoAdapter

                self.adapter = DemoAdapter()
                self.adapter.connect()
                self._agent = CortexaAgent(self.adapter)

                header = self.query_one(HeaderBar)
                memories = self.adapter.list_memories()
                header.memory_count = len(memories)
                header.connected = True
                header.mode = "demo"

                from cx.core.auditor import run_audit

                report = run_audit(self.adapter)
                header.health_score = report.health_score

                self._setup_step = None
                self._append_message(
                    f"Demo adapter connected \u2014 {len(memories)} memories loaded.\n"
                    "Type /health, /audit, or ask a question to get started.",
                    role="agent",
                )
                return True

            elif choice in ("2", "mem0"):
                self._setup_step = "mem0_key"
                self._append_message(
                    "Enter your Mem0 API key (or press Enter to skip and use demo):",
                    role="system",
                )
                return True

            elif choice in ("3", "custom"):
                self._setup_step = None
                self._append_message(
                    "Custom adapters are configured via .cortexa.yml.\n"
                    "See docs at https://github.com/cortexa-ai/cortexa-cli\n"
                    "Falling back to demo mode.",
                    role="system",
                )
                # Fall through to demo
                self._handle_setup_input("demo")
                return True

            else:
                self._append_message("Please type 1, 2, or 3.", role="error")
                return True

        elif self._setup_step == "mem0_key":
            if not text.strip():
                # Skip to demo
                self._setup_step = None
                self._handle_setup_input("demo")
                return True
            # Save key and try to connect
            from cx.config import CortexaConfig, GLOBAL_CONFIG_DIR

            GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            cfg = CortexaConfig(adapter="mem0", api_key=text.strip())
            cfg.save_global()
            self._setup_step = None
            self._append_message(
                "API key saved to ~/.config/cortexa/config.yml\n"
                "Restart cx to connect with Mem0, or type 'demo' for now.",
                role="agent",
            )
            # For now, fall back to demo
            self._handle_setup_input("demo")
            return True

        return False

    # ── Keyboard shortcuts ──────────────────────────────────────────

    def action_health(self) -> None:
        self._run_health()

    def action_audit(self) -> None:
        self._run_audit()

    def action_watch_toggle(self) -> None:
        self._run_watch()

    def action_export_audit(self) -> None:
        self._run_export()

    def action_clear_all(self) -> None:
        self._clear_conversation()

    # ── Message helpers ──────────────────────────────────────────────

    async def _typewrite_message(
        self, text: str, role: str = "system", speed: float = 0.01
    ) -> None:
        """Type out a message character by character with organic timing."""
        conv = self.query_one("#conversation", ConversationView)
        bubble = MessageBubble("", role=role)
        conv.mount(bubble)
        rendered = ""
        for char in text:
            rendered += char
            bubble.update(rendered)
            conv.scroll_end(animate=False)
            # Organic timing — pause longer after punctuation
            if char in ".!?\n":
                await asyncio.sleep(speed * 8)
            elif char in ",;:":
                await asyncio.sleep(speed * 3)
            elif char == " ":
                await asyncio.sleep(speed * 0.5)
            else:
                await asyncio.sleep(speed)

    def _append_message(self, content: Union[str, Text], role: str = "system") -> None:
        """Add a message to the conversation view and scroll to bottom."""
        conv = self.query_one("#conversation", ConversationView)
        bubble = MessageBubble(content, role=role)
        conv.mount(bubble)
        conv.scroll_end(animate=False)
