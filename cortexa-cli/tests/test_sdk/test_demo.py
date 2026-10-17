"""Tests for cortexa.demo — dataset generator and scenarios."""

from datetime import datetime, timedelta

import pytest

from cortexa.demo.dataset import generate_demo_memories, get_planted_issue_ids
from cortexa.demo.scenarios import (
    DemoScenario,
    build_ghost_hunt,
    build_healthy_response,
    build_pricing_audit,
    build_shipping_trace,
    get_scenario,
    list_scenarios,
)
from cortexa.engine.models import Memory


class TestDatasetGenerator:
    def test_generates_76_memories(self):
        memories = generate_demo_memories()
        assert len(memories) == 76

    def test_custom_count(self):
        memories = generate_demo_memories(count=10)
        assert len(memories) == 10

    def test_all_are_memory_objects(self):
        memories = generate_demo_memories()
        assert all(isinstance(m, Memory) for m in memories)

    def test_unique_ids(self):
        memories = generate_demo_memories()
        ids = [m.id for m in memories]
        assert len(set(ids)) == len(ids)

    def test_planted_stale_memory(self):
        memories = generate_demo_memories()
        mem_map = {m.id: m for m in memories}
        assert "mem_2847" in mem_map
        m = mem_map["mem_2847"]
        assert m.source == "shipping_policy.md"
        assert m.source_updated_at is not None
        assert m.source_updated_at > m.created_at

    def test_planted_ghost_memories(self):
        memories = generate_demo_memories()
        mem_map = {m.id: m for m in memories}
        assert "mem_1203" in mem_map
        assert "blue" in mem_map["mem_1203"].content.lower()
        assert "mem_0089" in mem_map
        assert "returns" in mem_map["mem_0089"].content.lower()

    def test_planted_contradiction_pair(self):
        memories = generate_demo_memories()
        mem_map = {m.id: m for m in memories}
        assert "mem_0044" in mem_map
        assert "mem_0055" in mem_map
        assert "$50" in mem_map["mem_0044"].content
        assert "$75" in mem_map["mem_0055"].content

    def test_custom_now(self):
        now = datetime(2025, 1, 1, 12, 0, 0)
        memories = generate_demo_memories(now=now)
        # All should be created before or at 'now'
        for m in memories:
            assert m.created_at <= now

    def test_all_have_source(self):
        memories = generate_demo_memories()
        # Planted memories have sources
        for m in memories[:10]:
            assert m.source is not None

    def test_categories_covered(self):
        memories = generate_demo_memories()
        sources = {m.source for m in memories if m.source}
        assert "shipping_policy.md" in sources
        assert "pricing_page" in sources


class TestPlantedIssueIds:
    def test_returns_dict(self):
        ids = get_planted_issue_ids()
        assert isinstance(ids, dict)
        assert "stale" in ids
        assert "ghost" in ids
        assert "contradiction" in ids

    def test_stale_ids(self):
        ids = get_planted_issue_ids()
        assert "mem_2847" in ids["stale"]

    def test_ghost_ids(self):
        ids = get_planted_issue_ids()
        assert "mem_1203" in ids["ghost"]
        assert "mem_0089" in ids["ghost"]

    def test_contradiction_ids(self):
        ids = get_planted_issue_ids()
        assert "mem_0044" in ids["contradiction"]
        assert "mem_0055" in ids["contradiction"]


class TestScenarios:
    def test_shipping_trace(self):
        s = build_shipping_trace()
        assert isinstance(s, DemoScenario)
        assert s.name == "shipping_trace"
        assert len(s.memories) == 5
        assert "arrives" in s.response.lower()
        assert len(s.expected_issues) >= 1

    def test_pricing_audit(self):
        s = build_pricing_audit()
        assert s.name == "pricing_audit"
        assert len(s.memories) == 3
        # Should contain the contradiction pair
        mem_ids = {m.id for m in s.memories}
        assert "mem_0044" in mem_ids
        assert "mem_0055" in mem_ids

    def test_ghost_hunt(self):
        s = build_ghost_hunt()
        assert s.name == "ghost_hunt"
        assert len(s.memories) == 8
        assert len(s.expected_issues) >= 1

    def test_healthy_response(self):
        s = build_healthy_response()
        assert s.name == "healthy_response"
        assert len(s.expected_issues) == 0

    def test_get_scenario(self):
        s = get_scenario("shipping_trace")
        assert s.name == "shipping_trace"

    def test_get_scenario_invalid(self):
        with pytest.raises(KeyError):
            get_scenario("nonexistent_scenario")

    def test_list_scenarios(self):
        names = list_scenarios()
        assert "shipping_trace" in names
        assert "pricing_audit" in names
        assert "ghost_hunt" in names
        assert "healthy_response" in names
        assert len(names) == 4

    def test_all_scenarios_have_memories(self):
        for name in list_scenarios():
            s = get_scenario(name)
            assert isinstance(s.memories, list)
            assert all(isinstance(m, Memory) for m in s.memories)

    def test_all_scenarios_have_query_and_response(self):
        for name in list_scenarios():
            s = get_scenario(name)
            assert len(s.query) > 0
            assert len(s.response) > 0
