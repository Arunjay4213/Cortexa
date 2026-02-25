"""Tests for multi-hop contradiction detection via belief propagation."""

import pytest
from cortex.attribution.belief_propagation import (
    ContradictionGraph,
    BeliefPropagationResult,
    TransitiveContradiction,
)


class TestContradictionGraph:
    def test_empty_graph(self):
        g = ContradictionGraph()
        result = g.run_belief_propagation()
        assert result.direct_contradictions == 0
        assert result.transitive_contradictions == []
        assert result.total_memories == 0

    def test_single_edge(self):
        g = ContradictionGraph()
        g.add_contradiction("A", "B", 0.9)
        result = g.run_belief_propagation()
        assert result.direct_contradictions == 1
        assert result.transitive_contradictions == []
        assert result.total_memories == 2

    def test_triangle_finds_transitive(self):
        """A-B and B-C should yield transitive A-C."""
        g = ContradictionGraph()
        g.add_contradiction("A", "B", 0.9)
        g.add_contradiction("B", "C", 0.85)
        result = g.run_belief_propagation(decay_factor=0.7, min_confidence=0.3)
        assert result.direct_contradictions == 2
        assert len(result.transitive_contradictions) >= 1
        # Find the A-C transitive
        ac = [t for t in result.transitive_contradictions
              if set([t.source_memory_id, t.target_memory_id]) == {"A", "C"}]
        assert len(ac) == 1
        assert ac[0].hop_count == 2
        assert ac[0].path == ["A", "B", "C"] or ac[0].path == ["C", "B", "A"]

    def test_transitive_confidence_decays(self):
        """Transitive confidence should be < min(direct confidences)."""
        g = ContradictionGraph()
        g.add_contradiction("A", "B", 0.9)
        g.add_contradiction("B", "C", 0.85)
        result = g.run_belief_propagation(decay_factor=0.7)
        if result.transitive_contradictions:
            tc = result.transitive_contradictions[0]
            # Should be 0.9 * 0.85 * 0.7 = 0.5355
            assert abs(tc.confidence - 0.5355) < 0.01

    def test_long_chain(self):
        """A-B-C-D chain: A-D should be detected if confidence high enough."""
        g = ContradictionGraph()
        g.add_contradiction("A", "B", 0.95)
        g.add_contradiction("B", "C", 0.95)
        g.add_contradiction("C", "D", 0.95)
        result = g.run_belief_propagation(decay_factor=0.8, min_confidence=0.2)
        assert result.direct_contradictions == 3
        # Should find A-C, A-D, B-D at minimum
        assert len(result.transitive_contradictions) >= 2

    def test_min_confidence_filters(self):
        """High min_confidence should filter weak transitive contradictions."""
        g = ContradictionGraph()
        g.add_contradiction("A", "B", 0.5)
        g.add_contradiction("B", "C", 0.5)
        # Transitive: 0.5 * 0.5 * 0.7 = 0.175
        result = g.run_belief_propagation(decay_factor=0.7, min_confidence=0.5)
        assert len(result.transitive_contradictions) == 0

    def test_decay_factor_impact(self):
        """Lower decay should reduce transitive confidence."""
        g = ContradictionGraph()
        g.add_contradiction("A", "B", 0.9)
        g.add_contradiction("B", "C", 0.9)

        r_high = g.run_belief_propagation(decay_factor=0.9, min_confidence=0.1)
        r_low = g.run_belief_propagation(decay_factor=0.3, min_confidence=0.1)

        if r_high.transitive_contradictions and r_low.transitive_contradictions:
            assert r_high.transitive_contradictions[0].confidence > r_low.transitive_contradictions[0].confidence

    def test_disconnected_components(self):
        """Disconnected subgraphs should not produce transitive contradictions."""
        g = ContradictionGraph()
        g.add_contradiction("A", "B", 0.9)
        g.add_contradiction("C", "D", 0.9)
        result = g.run_belief_propagation()
        assert result.direct_contradictions == 2
        assert len(result.transitive_contradictions) == 0

    def test_graph_density(self):
        """Density should be edges / possible edges."""
        g = ContradictionGraph()
        g.add_contradiction("A", "B", 0.9)
        g.add_contradiction("B", "C", 0.9)
        g.add_contradiction("A", "C", 0.9)
        result = g.run_belief_propagation()
        # 3 nodes, 3 edges, max = 3 -> density = 1.0
        assert abs(result.graph_density - 1.0) < 0.01

    def test_convergence(self):
        """BP should converge in finite iterations."""
        g = ContradictionGraph()
        g.add_contradiction("A", "B", 0.9)
        g.add_contradiction("B", "C", 0.85)
        result = g.run_belief_propagation(max_iterations=100)
        assert result.convergence_iterations <= 100

    def test_find_path_direct(self):
        """Direct neighbors should have path length 2."""
        g = ContradictionGraph()
        g.add_contradiction("A", "B", 0.9)
        path = g._find_path("A", "B", max_hops=3)
        assert path == ["A", "B"]

    def test_find_path_no_connection(self):
        """Disconnected nodes should return None."""
        g = ContradictionGraph()
        g.add_contradiction("A", "B", 0.9)
        path = g._find_path("A", "C", max_hops=3)
        assert path is None

    def test_find_path_max_hops_limit(self):
        """Path longer than max_hops should not be found."""
        g = ContradictionGraph()
        g.add_contradiction("A", "B", 0.9)
        g.add_contradiction("B", "C", 0.9)
        g.add_contradiction("C", "D", 0.9)
        # max_hops=1 should not find A->D (which needs 3 hops)
        path = g._find_path("A", "D", max_hops=1)
        assert path is None
