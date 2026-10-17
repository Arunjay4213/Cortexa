"""Tests for the Rich+Typer CLI.

Uses Rich Console.capture() and Typer CliRunner to test
that commands don't crash and output contains expected strings.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from cortexa.app.main import app

runner = CliRunner()


# ── Banner & Help ────────────────────────────────────────────────────

class TestHelp:
    """Test that help and basic invocation work."""

    def test_help_flag(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "cortexa" in result.output.lower() or "memory" in result.output.lower()

    def test_no_args_shows_help(self):
        result = runner.invoke(app, [])
        # Typer returns exit code 0 for --help but 2 for no args with no_args_is_help
        assert result.exit_code in (0, 2)

    def test_audit_help(self):
        result = runner.invoke(app, ["audit", "--help"])
        assert result.exit_code == 0
        assert "demo" in result.output.lower()

    def test_trace_help(self):
        result = runner.invoke(app, ["trace", "--help"])
        assert result.exit_code == 0

    def test_health_help(self):
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0

    def test_watch_help(self):
        result = runner.invoke(app, ["watch", "--help"])
        assert result.exit_code == 0

    def test_chat_help(self):
        result = runner.invoke(app, ["chat", "--help"])
        assert result.exit_code == 0


# ── Audit Command ────────────────────────────────────────────────────

class TestAudit:
    """Test the audit command."""

    def test_audit_demo_runs(self):
        result = runner.invoke(app, ["audit", "--demo"])
        assert result.exit_code == 0
        assert "cortexa" in result.output.lower()

    def test_audit_demo_shows_health(self):
        result = runner.invoke(app, ["audit", "--demo"])
        assert "%" in result.output or "health" in result.output.lower()

    def test_audit_demo_shows_memories(self):
        result = runner.invoke(app, ["audit", "--demo"])
        assert "memor" in result.output.lower()

    def test_audit_empty_store(self):
        result = runner.invoke(app, ["audit"])
        assert result.exit_code == 0


# ── Trace Command ────────────────────────────────────────────────────

class TestTrace:
    """Test the trace command."""

    def test_trace_demo_runs(self):
        result = runner.invoke(app, ["trace", "test response", "--demo"])
        assert result.exit_code == 0
        assert "cortexa" in result.output.lower()

    def test_trace_demo_shows_claims(self):
        result = runner.invoke(app, ["trace", "test response", "--demo"])
        assert "claim" in result.output.lower() or "MAS" in result.output

    def test_trace_demo_shows_query(self):
        result = runner.invoke(app, ["trace", "test response", "--demo"])
        # Should show the demo scenario query
        assert "query" in result.output.lower()

    def test_trace_with_query(self):
        result = runner.invoke(app, ["trace", "The price is $49.99", "--query", "How much?"])
        assert result.exit_code == 0

    def test_trace_requires_response(self):
        result = runner.invoke(app, ["trace"])
        assert result.exit_code != 0


# ── Health Command ───────────────────────────────────────────────────

class TestHealth:
    """Test the health command."""

    def test_health_demo_runs(self):
        result = runner.invoke(app, ["health", "--demo"])
        assert result.exit_code == 0

    def test_health_demo_shows_bar(self):
        result = runner.invoke(app, ["health", "--demo"])
        assert "%" in result.output or "health" in result.output.lower()

    def test_health_empty_store(self):
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0


# ── Watch Command ────────────────────────────────────────────────────

class TestWatch:
    """Test the watch command (non-demo mode only, demo would block)."""

    def test_watch_no_demo_runs(self):
        result = runner.invoke(app, ["watch"])
        assert result.exit_code == 0
        assert "watch" in result.output.lower() or "event" in result.output.lower()


# ── Chat Command ─────────────────────────────────────────────────────

class TestChat:
    """Test the chat command with simulated input."""

    def test_chat_exit(self):
        result = runner.invoke(app, ["chat"], input="exit\n")
        assert result.exit_code == 0
        assert "goodbye" in result.output.lower() or "bye" in result.output.lower()

    def test_chat_quit(self):
        result = runner.invoke(app, ["chat"], input="quit\n")
        assert result.exit_code == 0

    def test_chat_empty_then_exit(self):
        result = runner.invoke(app, ["chat"], input="\nexit\n")
        assert result.exit_code == 0

    def test_chat_demo_with_input(self):
        result = runner.invoke(app, ["chat", "--demo"], input="Your order ships in 2 days\nexit\n")
        assert result.exit_code == 0

    def test_chat_shows_banner(self):
        result = runner.invoke(app, ["chat"], input="exit\n")
        assert "cortexa" in result.output.lower()


# ── Display Module ───────────────────────────────────────────────────

class TestDisplay:
    """Test display rendering functions using Console.capture()."""

    def test_banner_output(self):
        from cortexa.app.display import console, banner as _banner
        with console.capture() as capture:
            _banner()
        output = capture.get()
        assert "cortexa" in output.lower()
        assert "v0.1.0" in output

    def test_error_output(self):
        from cortexa.app.display import console, error as _error
        with console.capture() as capture:
            _error("something broke")
        assert "something broke" in capture.get()

    def test_success_output(self):
        from cortexa.app.display import console, success as _success
        with console.capture() as capture:
            _success("all good")
        assert "all good" in capture.get()

    def test_dim_output(self):
        from cortexa.app.display import console, dim as _dim
        with console.capture() as capture:
            _dim("info message")
        assert "info message" in capture.get()

    def test_health_bar_renders(self):
        from cortexa.app.display import console, health_bar as _health_bar
        with console.capture() as capture:
            _health_bar(85.0)
        output = capture.get()
        assert "health" in output.lower() or "%" in output

    def test_health_bar_low_score(self):
        from cortexa.app.display import console, health_bar as _health_bar
        with console.capture() as capture:
            _health_bar(30.0)
        output = capture.get()
        assert "%" in output

    def test_score_style_good(self):
        from cortexa.app.display import score_style
        assert score_style(90) == "score.good"

    def test_score_style_warn(self):
        from cortexa.app.display import score_style
        assert score_style(65) == "score.warn"

    def test_score_style_bad(self):
        from cortexa.app.display import score_style
        assert score_style(30) == "score.bad"

    def test_format_score(self):
        from cortexa.app.display import format_score
        text = format_score(85.7)
        assert "86/100" in text.plain

    def test_watch_event_renders(self):
        from cortexa.app.display import console, watch_event as _watch_event
        with console.capture() as capture:
            _watch_event({"type": "ghost", "timestamp": "12:00:00", "message": "ghost found"})
        assert "ghost found" in capture.get()

    def test_issues_section_empty(self):
        from cortexa.app.display import console, issues_section as _issues
        with console.capture() as capture:
            _issues([], [], [])
        assert "no issues" in capture.get().lower()

    def test_issues_section_with_ghosts(self):
        from cortexa.app.display import console, issues_section as _issues
        from cortexa.engine.models import GhostToken
        ghosts = [GhostToken(memory_id="mem_001", max_mas=0.1, waste_tokens=50, reason="irrelevant")]
        with console.capture() as capture:
            _issues(ghosts, [], [])
        output = capture.get()
        assert "ghost" in output.lower()
        assert "mem_001" in output

    def test_claim_tree_renders(self):
        from cortexa.app.display import console, claim_tree as _claim_tree
        from cortexa.engine.models import Claim, Attribution
        claims = [Claim(id="c1", text="Price is $49.99", source_response="test")]
        attrs = [Attribution(claim_id="c1", memory_id="mem_020", mas_score=0.9, entailment_score=0.85, contribution_type="supporting")]
        with console.capture() as capture:
            _claim_tree(claims, attrs)
        output = capture.get()
        assert "49.99" in output
        assert "mem_020" in output

    def test_gate_result_safe(self):
        from cortexa.app.display import console, gate_result as _gate_result
        from cortexa.engine.models import GateResult
        gr = GateResult(query="test", memories_scored=5, safe_to_generate=True, risk_summary="No risks detected")
        with console.capture() as capture:
            _gate_result(gr)
        output = capture.get()
        assert "safe" in output.lower()

    def test_gate_result_risky(self):
        from cortexa.app.display import console, gate_result as _gate_result
        from cortexa.engine.models import GateResult
        gr = GateResult(query="test", memories_scored=5, safe_to_generate=False, risk_summary="1 contradiction", high_risk=["mem_001"])
        with console.capture() as capture:
            _gate_result(gr)
        output = capture.get()
        assert "risk" in output.lower() or "mem_001" in output

    def test_trace_header(self):
        from cortexa.app.display import console, trace_header as _trace_header
        with console.capture() as capture:
            _trace_header("How much?", "The price is $49.99")
        output = capture.get()
        assert "how much" in output.lower()
        assert "49.99" in output

    def test_chat_response(self):
        from cortexa.app.display import console, chat_response as _chat_response
        with console.capture() as capture:
            _chat_response("Here is the answer")
        assert "here is the answer" in capture.get().lower()

    def test_chat_tool_call(self):
        from cortexa.app.display import console, chat_tool_call as _chat_tool_call
        with console.capture() as capture:
            _chat_tool_call("trace", '"some text"')
        output = capture.get()
        assert "trace" in output
        assert "some text" in output


# ── Version ──────────────────────────────────────────────────────────

class TestVersion:
    """Test version is accessible."""

    def test_display_version(self):
        from cortexa.app.display import __version__
        assert __version__ == "0.1.0"
