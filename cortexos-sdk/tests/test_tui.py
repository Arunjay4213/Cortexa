"""Tests for CortexOS TUI — state, event parsing, and headless app tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from cortexos.tui.state import AgentStats, EventRecord, SessionState


# ── Test data ──────────────────────────────────────────────

def _check_event(hi: float = 0.12, agent: str = "agent-1", claims: int = 3) -> dict:
    return {
        "type": "check",
        "ts": "2026-02-25T18:33:41+00:00",
        "hi": hi,
        "total_claims": claims,
        "grounded": claims - 1,
        "hallucinated": 1,
        "opinion_count": 0,
        "latency_ms": 245.0,
        "verdicts": ["GROUNDED"] * (claims - 1) + ["UNSUPPORTED"],
        "api_key_id": agent,
        "response_preview": "The site scores 87 on the GEE...",
        "claims": [
            {
                "text": f"Claim {i+1}",
                "verdict": "GROUNDED" if i < claims - 1 else "UNSUPPORTED",
                "grounded": i < claims - 1,
                "confidence": 0.91 if i < claims - 1 else 0.3,
                "reason": "",
                "source_quote": "source text" if i < claims - 1 else None,
                "attribution": None,
                "primary_source_index": 0 if i < claims - 1 else None,
            }
            for i in range(claims)
        ],
    }


def _gate_event(grounded: bool = True, hi: float = 0.05, agent: str = "agent-2") -> dict:
    return {
        "type": "gate",
        "ts": "2026-02-25T18:33:38+00:00",
        "grounded": grounded,
        "hi": hi,
        "flagged": 0 if grounded else 2,
        "latency_ms": 180.0,
        "api_key_id": agent,
        "candidate_preview": "The IRR is 24.7%...",
        "total_claims": 3,
        "verdicts": ["GROUNDED", "GROUNDED", "GROUNDED"] if grounded else ["GROUNDED", "NUM_MISMATCH", "UNSUPPORTED"],
        "flagged_claims": [] if grounded else [
            {"text": "IRR is 24.7%", "verdict": "NUM_MISMATCH", "reason": "Source says 18.2%"},
        ],
        "suggested_corrections": None,
        "claims": [
            {"text": "Claim A", "verdict": "GROUNDED", "grounded": True, "confidence": 0.9, "reason": "", "source_quote": "src", "attribution": None, "primary_source_index": 0},
        ],
    }


# ── EventRecord tests ─────────────────────────────────────

class TestEventRecord:
    def test_from_sse_check(self):
        data = _check_event()
        record = EventRecord.from_sse(data)
        assert record is not None
        assert record.type == "check"
        assert record.hi == 0.12
        assert record.total_claims == 3
        assert record.grounded == 2
        assert record.hallucinated == 1
        assert record.api_key_id == "agent-1"
        assert len(record.claims) == 3
        assert record.response_preview.startswith("The site")

    def test_from_sse_gate(self):
        data = _gate_event(grounded=False, hi=0.67)
        record = EventRecord.from_sse(data)
        assert record is not None
        assert record.type == "gate"
        assert record.hi == 0.67
        # gate grounded is bool, so grounded_int should be 0
        assert record.grounded == 0
        assert record.flagged == 2
        assert record.response_preview.startswith("The IRR")

    def test_from_sse_ignores_heartbeat(self):
        assert EventRecord.from_sse({"type": "heartbeat"}) is None

    def test_from_sse_ignores_connected(self):
        assert EventRecord.from_sse({"type": "connected"}) is None

    def test_from_sse_ignores_unknown(self):
        assert EventRecord.from_sse({"type": "foo"}) is None

    def test_from_sse_missing_ts(self):
        data = _check_event()
        del data["ts"]
        record = EventRecord.from_sse(data)
        assert record is not None
        assert isinstance(record.ts, datetime)


# ── SessionState tests ────────────────────────────────────

class TestSessionState:
    def test_add_check_event(self):
        state = SessionState()
        record = EventRecord.from_sse(_check_event())
        state.add_event(record)

        assert state.total_checks == 1
        assert state.total_claims == 3
        assert state.total_grounded == 2
        assert state.total_hallucinated == 1
        assert state.avg_hi == pytest.approx(0.12)
        assert state.avg_latency == pytest.approx(245.0)

    def test_add_multiple_events(self):
        state = SessionState()
        state.add_event(EventRecord.from_sse(_check_event(hi=0.0)))
        state.add_event(EventRecord.from_sse(_check_event(hi=0.5)))

        assert state.total_checks == 2
        assert state.avg_hi == pytest.approx(0.25)

    def test_blocked_count(self):
        state = SessionState()
        state.add_event(EventRecord.from_sse(_gate_event(grounded=True)))
        assert state.blocked_count == 0

        state.add_event(EventRecord.from_sse(_gate_event(grounded=False, hi=0.67)))
        assert state.blocked_count == 1

    def test_all_claims_flattens(self):
        state = SessionState()
        state.add_event(EventRecord.from_sse(_check_event(claims=3)))
        state.add_event(EventRecord.from_sse(_check_event(claims=2)))

        all_claims = state.all_claims()
        assert len(all_claims) == 5
        for event, claim in all_claims:
            assert isinstance(event, EventRecord)
            assert "text" in claim

    def test_agent_stats(self):
        state = SessionState()
        state.add_event(EventRecord.from_sse(_check_event(hi=0.2, agent="a1")))
        state.add_event(EventRecord.from_sse(_check_event(hi=0.4, agent="a1")))
        state.add_event(EventRecord.from_sse(_check_event(hi=0.1, agent="a2")))

        assert "a1" in state.agents
        assert "a2" in state.agents
        assert state.agents["a1"].checks == 2
        assert state.agents["a1"].avg_hi == pytest.approx(0.3)
        assert state.agents["a2"].checks == 1

    def test_p95_latency(self):
        state = SessionState()
        # Add 20 events with increasing latency
        for i in range(20):
            event = _check_event(hi=0.1)
            event["latency_ms"] = float(i * 50)
            state.add_event(EventRecord.from_sse(event))

        assert state.p95_latency > 0
        assert state.p95_latency <= 950.0

    def test_hi_trend_caps_at_30(self):
        state = SessionState()
        for i in range(50):
            state.add_event(EventRecord.from_sse(_check_event(hi=i * 0.02)))

        assert len(state.hi_trend) == 30

    def test_gate_events_filter(self):
        state = SessionState()
        state.add_event(EventRecord.from_sse(_check_event()))
        state.add_event(EventRecord.from_sse(_gate_event()))
        state.add_event(EventRecord.from_sse(_check_event()))

        gate_only = state.gate_events()
        assert len(gate_only) == 1
        assert gate_only[0].type == "gate"

    def test_halluc_pct(self):
        state = SessionState()
        state.add_event(EventRecord.from_sse(_check_event(hi=0.5, claims=4)))
        # 4 claims total, 1 hallucinated
        assert state.halluc_pct == pytest.approx(0.25)

    def test_clear(self):
        state = SessionState()
        state.add_event(EventRecord.from_sse(_check_event()))
        state.add_event(EventRecord.from_sse(_gate_event(grounded=False)))
        state.clear()

        assert state.total_checks == 0
        assert state.total_claims == 0
        assert state.blocked_count == 0
        assert len(state.agents) == 0
        assert state.hi_trend == []


# ── AgentStats tests ──────────────────────────────────────

class TestAgentStats:
    def test_avg_hi_zero_checks(self):
        a = AgentStats(api_key_id="x")
        assert a.avg_hi == 0.0

    def test_halluc_pct_zero_claims(self):
        a = AgentStats(api_key_id="x")
        assert a.halluc_pct == 0.0

    def test_stats_accumulation(self):
        a = AgentStats(api_key_id="x")
        a.checks = 3
        a.total_hi = 0.6
        a.total_claims = 10
        a.total_hallucinated = 2

        assert a.avg_hi == pytest.approx(0.2)
        assert a.halluc_pct == pytest.approx(0.2)


# ── Headless Textual app tests ────────────────────────────

class TestCortexMonitorApp:
    """Headless tests using Textual's app.run_test()."""

    @pytest.fixture
    def app(self):
        from cortexos.tui.app import CortexMonitor
        return CortexMonitor(base_url="https://api.cortexa.ink", api_key="test-key")

    @pytest.mark.asyncio
    async def test_app_mounts_five_tabs(self, app):
        async with app.run_test(size=(120, 40)) as pilot:
            from textual.widgets import ContentSwitcher
            switcher = app.query_one(ContentSwitcher)
            assert switcher is not None
            # Verify all 5 tab panes exist
            from cortexos.tui.tabs import FeedTab, ClaimsTab, MemoryTab, AgentsTab, InspectTab
            assert app.query_one(FeedTab) is not None
            assert app.query_one(ClaimsTab) is not None
            assert app.query_one(MemoryTab) is not None
            assert app.query_one(AgentsTab) is not None
            assert app.query_one(InspectTab) is not None

    @pytest.mark.asyncio
    async def test_sse_event_updates_state(self, app):
        async with app.run_test(size=(120, 40)) as pilot:
            from cortexos.tui.stream import SSEEvent
            msg = SSEEvent(_check_event(hi=0.15))
            app.on_sse_event(msg)
            await pilot.pause()

            assert app.state.total_checks == 1
            assert app.state.avg_hi == pytest.approx(0.15)

    @pytest.mark.asyncio
    async def test_tab_switching_with_keys(self, app):
        async with app.run_test(size=(120, 40)) as pilot:
            from textual.widgets import ContentSwitcher
            switcher = app.query_one(ContentSwitcher)

            await pilot.press("2")
            await pilot.pause()
            assert switcher.current == "tab-claims"

            await pilot.press("3")
            await pilot.pause()
            assert switcher.current == "tab-memory"

            await pilot.press("4")
            await pilot.pause()
            assert switcher.current == "tab-agents"

            await pilot.press("5")
            await pilot.pause()
            assert switcher.current == "tab-inspect"

            await pilot.press("1")
            await pilot.pause()
            assert switcher.current == "tab-feed"

    @pytest.mark.asyncio
    async def test_multiple_events_accumulate(self, app):
        async with app.run_test(size=(120, 40)) as pilot:
            from cortexos.tui.stream import SSEEvent
            for hi in [0.1, 0.2, 0.3]:
                app.on_sse_event(SSEEvent(_check_event(hi=hi)))
            await pilot.pause()

            assert app.state.total_checks == 3
            assert app.state.avg_hi == pytest.approx(0.2)

    @pytest.mark.asyncio
    async def test_gate_event_tracked(self, app):
        async with app.run_test(size=(120, 40)) as pilot:
            from cortexos.tui.stream import SSEEvent
            app.on_sse_event(SSEEvent(_gate_event(grounded=False, hi=0.67)))
            await pilot.pause()

            assert app.state.blocked_count == 1

    @pytest.mark.asyncio
    async def test_heartbeat_ignored(self, app):
        async with app.run_test(size=(120, 40)) as pilot:
            from cortexos.tui.stream import SSEEvent
            app.on_sse_event(SSEEvent({"type": "heartbeat", "ts": "2026-02-25T18:33:41+00:00"}))
            await pilot.pause()

            assert app.state.total_checks == 0

    @pytest.mark.asyncio
    async def test_inspect_event(self, app):
        async with app.run_test(size=(120, 40)) as pilot:
            from cortexos.tui.stream import SSEEvent
            from cortexos.tui.tabs.inspect import InspectTab

            event_data = _check_event(hi=0.42)
            app.on_sse_event(SSEEvent(event_data))
            await pilot.pause()

            record = app.state.events[0]
            app.inspect_event(record)
            await pilot.pause()

            from textual.widgets import ContentSwitcher
            switcher = app.query_one(ContentSwitcher)
            assert switcher.current == "tab-inspect"

            inspect = app.query_one(InspectTab)
            assert inspect._record is not None
            assert inspect._record.hi == 0.42
