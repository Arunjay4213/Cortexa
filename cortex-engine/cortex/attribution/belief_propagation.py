"""Multi-Hop Contradiction Detection via Belief Propagation — §4.1.3.

Detects transitive contradictions across chains of memories.
If A contradicts B and B contradicts C, then A may indirectly contradict C.

Uses loopy belief propagation on a factor graph where:
- Variable nodes = memories
- Factor nodes = pairwise contradiction probabilities
- Messages = belief updates about contradiction state

This catches contradictions that pairwise NLI misses because the
semantic distance between A and C may be too large for direct comparison.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class TransitiveContradiction:
    """A contradiction detected through multi-hop inference."""
    source_memory_id: str
    target_memory_id: str
    path: list[str]           # memory IDs in the contradiction chain
    confidence: float         # product of edge confidences, decayed
    hop_count: int
    direct_confidence: float  # pairwise NLI confidence (may be low)


@dataclass
class BeliefPropagationResult:
    """Results of multi-hop contradiction analysis."""
    direct_contradictions: int
    transitive_contradictions: list[TransitiveContradiction]
    total_memories: int
    graph_density: float       # edges / possible edges
    max_chain_length: int
    convergence_iterations: int


class ContradictionGraph:
    """Factor graph for multi-hop contradiction detection.

    Nodes: memory IDs
    Edges: pairwise contradiction probabilities from NLI
    """

    def __init__(self):
        self._nodes: set[str] = set()
        self._edges: dict[tuple[str, str], float] = {}  # (a, b) -> confidence
        self._adjacency: dict[str, list[str]] = {}

    def add_contradiction(
        self, memory_id_1: str, memory_id_2: str, confidence: float
    ) -> None:
        """Add a direct pairwise contradiction."""
        self._nodes.add(memory_id_1)
        self._nodes.add(memory_id_2)

        # Store both directions for easy lookup
        key = tuple(sorted([memory_id_1, memory_id_2]))
        self._edges[key] = confidence

        self._adjacency.setdefault(memory_id_1, []).append(memory_id_2)
        self._adjacency.setdefault(memory_id_2, []).append(memory_id_1)

    def run_belief_propagation(
        self,
        max_hops: int = 3,
        decay_factor: float = 0.7,
        min_confidence: float = 0.3,
        max_iterations: int = 20,
    ) -> BeliefPropagationResult:
        """Run loopy belief propagation to find transitive contradictions.

        Args:
            max_hops: maximum chain length to consider
            decay_factor: confidence decay per hop (0.7 = 30% decay per hop)
            min_confidence: minimum transitive confidence to report
            max_iterations: BP convergence iterations
        """
        nodes = list(self._nodes)
        n = len(nodes)

        if n < 2:
            return BeliefPropagationResult(
                direct_contradictions=len(self._edges),
                transitive_contradictions=[],
                total_memories=n,
                graph_density=0.0,
                max_chain_length=0,
                convergence_iterations=0,
            )

        node_idx = {nid: i for i, nid in enumerate(nodes)}

        # Initialize belief matrix: beliefs[i][j] = P(i contradicts j)
        beliefs = np.zeros((n, n))

        # Set direct contradictions
        for (a, b), conf in self._edges.items():
            i, j = node_idx[a], node_idx[b]
            beliefs[i][j] = conf
            beliefs[j][i] = conf

        # Message passing
        messages = np.zeros((n, n))
        converged_at = max_iterations

        for iteration in range(max_iterations):
            old_beliefs = beliefs.copy()

            # Update messages: for each pair (i, j), aggregate evidence from neighbors
            for i in range(n):
                for j in range(i + 1, n):
                    if beliefs[i][j] > 0:
                        continue  # skip direct contradictions

                    # Check for transitive paths through shared neighbors.
                    # Noisy-OR: each independent path contributes evidence.
                    # P(contradiction) = 1 - ∏(1 - P_path_k)
                    # Two weak paths (0.3, 0.3) → 0.51 combined, not 0.3.
                    survival = 1.0
                    for k in range(n):
                        if k == i or k == j:
                            continue
                        if beliefs[i][k] > 0 and beliefs[k][j] > 0:
                            path_conf = beliefs[i][k] * beliefs[k][j] * decay_factor
                            survival *= (1.0 - path_conf)

                    transitive_conf = 1.0 - survival
                    if transitive_conf >= min_confidence:
                        messages[i][j] = transitive_conf
                        messages[j][i] = transitive_conf

            # Update beliefs with messages
            beliefs = np.maximum(beliefs, messages)

            # Check convergence
            if np.allclose(beliefs, old_beliefs, atol=1e-6):
                converged_at = iteration + 1
                break

        # Extract transitive contradictions (those not in direct edges)
        transitive: list[TransitiveContradiction] = []

        for i in range(n):
            for j in range(i + 1, n):
                a, b = nodes[i], nodes[j]
                key = tuple(sorted([a, b]))

                if key in self._edges:
                    continue  # skip direct contradictions

                if beliefs[i][j] >= min_confidence:
                    # Find the path
                    path = self._find_path(a, b, max_hops)
                    if path and len(path) > 2:
                        transitive.append(TransitiveContradiction(
                            source_memory_id=a,
                            target_memory_id=b,
                            path=path,
                            confidence=round(float(beliefs[i][j]), 4),
                            hop_count=len(path) - 1,
                            direct_confidence=0.0,
                        ))

        # Sort by confidence descending
        transitive.sort(key=lambda x: x.confidence, reverse=True)

        max_possible_edges = n * (n - 1) / 2
        density = len(self._edges) / max_possible_edges if max_possible_edges > 0 else 0.0
        max_chain = max((t.hop_count for t in transitive), default=0)

        return BeliefPropagationResult(
            direct_contradictions=len(self._edges),
            transitive_contradictions=transitive,
            total_memories=n,
            graph_density=round(density, 4),
            max_chain_length=max_chain,
            convergence_iterations=converged_at,
        )

    def _find_path(
        self, start: str, end: str, max_hops: int
    ) -> list[str] | None:
        """BFS to find shortest path between two nodes."""
        if start == end:
            return [start]

        visited = {start}
        queue: list[tuple[str, list[str]]] = [(start, [start])]

        while queue:
            current, path = queue.pop(0)

            if len(path) > max_hops + 1:
                continue

            for neighbor in self._adjacency.get(current, []):
                if neighbor == end:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None


async def detect_transitive_contradictions(
    db,  # AsyncConnection
    agent_id: str | None = None,
    max_hops: int = 3,
    decay_factor: float = 0.7,
    min_confidence: float = 0.3,
) -> BeliefPropagationResult:
    """Run multi-hop contradiction detection on stored contradictions.

    Reads direct contradictions from the contradictions table,
    builds a factor graph, and runs belief propagation.
    """
    from sqlalchemy import select
    from cortex.db.tables import contradictions

    stmt = select(contradictions).where(contradictions.c.resolved == False)
    if agent_id:
        # Filter by memory agent — need to join through memories table
        from cortex.db.tables import memories
        memory_ids_stmt = select(memories.c.id).where(memories.c.agent_id == agent_id)
        stmt = stmt.where(
            (contradictions.c.memory_id_1.in_(memory_ids_stmt))
            | (contradictions.c.memory_id_2.in_(memory_ids_stmt))
        )

    rows = (await db.execute(stmt)).fetchall()

    graph = ContradictionGraph()
    for row in rows:
        graph.add_contradiction(row.memory_id_1, row.memory_id_2, row.confidence)

    return graph.run_belief_propagation(
        max_hops=max_hops,
        decay_factor=decay_factor,
        min_confidence=min_confidence,
    )
