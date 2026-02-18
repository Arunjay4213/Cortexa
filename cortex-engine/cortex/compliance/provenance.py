"""Provenance Graph — §6.1.

Directed Acyclic Graph tracking memory lineage and derivation chains.
Each node represents a memory event (creation, modification, derivation, merge).
Edges represent derivation relationships.

G = (V, E) where V = memory events, E = derivation relationships
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


class ProvenanceEventType(str, Enum):
    """Types of provenance events."""
    created = "created"
    modified = "modified"
    derived = "derived"       # new memory derived from existing
    merged = "merged"         # multiple memories merged into one
    split = "split"           # one memory split into multiple
    archived = "archived"
    restored = "restored"
    deleted = "deleted"


@dataclass
class ProvenanceNode:
    """A node in the provenance DAG."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    memory_id: str = ""
    event_type: ProvenanceEventType = ProvenanceEventType.created
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    agent_id: str = "default"
    actor: str = "system"       # who triggered this event
    metadata: dict[str, Any] = field(default_factory=dict)
    parent_ids: list[str] = field(default_factory=list)  # parent node IDs (derivation sources)
    content_hash: str | None = None


@dataclass
class ProvenanceEdge:
    """An edge in the provenance DAG."""
    source_id: str    # parent node
    target_id: str    # child node
    relationship: str = "derived_from"  # derived_from | merged_from | split_from


class ProvenanceGraph:
    """In-memory provenance DAG for an agent's memory lineage.

    Supports:
    - Adding provenance events
    - Querying lineage (ancestors/descendants)
    - Computing provenance depth (how many derivation steps from original)
    - Detecting cycles (should never happen in a valid DAG)
    """

    def __init__(self):
        self._nodes: dict[str, ProvenanceNode] = {}
        self._edges: list[ProvenanceEdge] = []
        self._children: dict[str, list[str]] = {}  # parent_id -> [child_ids]
        self._parents: dict[str, list[str]] = {}    # child_id -> [parent_ids]

    def add_event(
        self,
        memory_id: str,
        event_type: ProvenanceEventType,
        agent_id: str = "default",
        actor: str = "system",
        parent_memory_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        content_hash: str | None = None,
    ) -> ProvenanceNode:
        """Record a provenance event and link to parent memories."""
        node = ProvenanceNode(
            memory_id=memory_id,
            event_type=event_type,
            agent_id=agent_id,
            actor=actor,
            metadata=metadata or {},
            content_hash=content_hash,
        )
        self._nodes[node.id] = node

        if parent_memory_ids:
            # Find the most recent nodes for each parent memory
            for parent_mid in parent_memory_ids:
                parent_node = self._find_latest_node(parent_mid)
                if parent_node:
                    node.parent_ids.append(parent_node.id)
                    edge = ProvenanceEdge(
                        source_id=parent_node.id,
                        target_id=node.id,
                        relationship=f"{event_type.value}_from",
                    )
                    self._edges.append(edge)
                    self._children.setdefault(parent_node.id, []).append(node.id)
                    self._parents.setdefault(node.id, []).append(parent_node.id)

        return node

    def _find_latest_node(self, memory_id: str) -> ProvenanceNode | None:
        """Find the most recent provenance node for a memory."""
        candidates = [n for n in self._nodes.values() if n.memory_id == memory_id]
        if not candidates:
            return None
        return max(candidates, key=lambda n: n.timestamp)

    def get_lineage(self, memory_id: str) -> list[ProvenanceNode]:
        """Get full ancestor chain for a memory (BFS upward)."""
        latest = self._find_latest_node(memory_id)
        if not latest:
            return []

        visited = set()
        queue = [latest.id]
        lineage = []

        while queue:
            node_id = queue.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)

            node = self._nodes.get(node_id)
            if node:
                lineage.append(node)
                for parent_id in self._parents.get(node_id, []):
                    if parent_id not in visited:
                        queue.append(parent_id)

        return lineage

    def get_descendants(self, memory_id: str) -> list[ProvenanceNode]:
        """Get all derived memories (BFS downward)."""
        latest = self._find_latest_node(memory_id)
        if not latest:
            return []

        visited = set()
        queue = [latest.id]
        descendants = []

        while queue:
            node_id = queue.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)

            node = self._nodes.get(node_id)
            if node and node.id != latest.id:
                descendants.append(node)

            for child_id in self._children.get(node_id, []):
                if child_id not in visited:
                    queue.append(child_id)

        return descendants

    def provenance_depth(self, memory_id: str) -> int:
        """How many derivation steps from an original (root) memory."""
        lineage = self.get_lineage(memory_id)
        return max(0, len(lineage) - 1)

    def has_cycle(self) -> bool:
        """Detect cycles in the provenance graph (should always be False)."""
        visited = set()
        rec_stack = set()

        def _dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)

            for child_id in self._children.get(node_id, []):
                if child_id not in visited:
                    if _dfs(child_id):
                        return True
                elif child_id in rec_stack:
                    return True

            rec_stack.discard(node_id)
            return False

        for node_id in self._nodes:
            if node_id not in visited:
                if _dfs(node_id):
                    return True
        return False

    def to_dict(self) -> dict:
        """Serialize the graph for API responses."""
        return {
            "nodes": [
                {
                    "id": n.id,
                    "memory_id": n.memory_id,
                    "event_type": n.event_type.value,
                    "timestamp": n.timestamp.isoformat(),
                    "agent_id": n.agent_id,
                    "actor": n.actor,
                    "parent_ids": n.parent_ids,
                    "content_hash": n.content_hash,
                }
                for n in self._nodes.values()
            ],
            "edges": [
                {
                    "source": e.source_id,
                    "target": e.target_id,
                    "relationship": e.relationship,
                }
                for e in self._edges
            ],
            "stats": {
                "total_nodes": len(self._nodes),
                "total_edges": len(self._edges),
                "has_cycle": self.has_cycle(),
            },
        }


async def build_provenance_graph(
    db,  # AsyncConnection
    agent_id: str,
) -> ProvenanceGraph:
    """Build a provenance graph from lifecycle_events table.

    Maps lifecycle events (archive, tier_change, consolidate) to provenance nodes.
    """
    from sqlalchemy import select
    from cortex.db.tables import lifecycle_events, memories

    graph = ProvenanceGraph()

    # Add creation events for all memories
    mem_rows = (
        await db.execute(
            select(memories.c.id, memories.c.agent_id, memories.c.created_at, memories.c.content_hash)
            .where(memories.c.agent_id == agent_id)
            .order_by(memories.c.created_at)
        )
    ).fetchall()

    for row in mem_rows:
        graph.add_event(
            memory_id=row.id,
            event_type=ProvenanceEventType.created,
            agent_id=row.agent_id,
            actor="sdk",
            content_hash=row.content_hash,
        )

    # Add lifecycle events
    lc_rows = (
        await db.execute(
            select(lifecycle_events)
            .where(lifecycle_events.c.agent_id == agent_id)
            .order_by(lifecycle_events.c.created_at)
        )
    ).fetchall()

    for row in lc_rows:
        if row.action == "archive":
            graph.add_event(
                memory_id=row.memory_id,
                event_type=ProvenanceEventType.archived,
                agent_id=row.agent_id,
                actor=row.executed_by or "system",
                metadata=dict(row.details) if row.details else {},
            )
        elif row.action == "consolidate":
            details = dict(row.details) if row.details else {}
            canonical_id = details.get("canonical_id")
            graph.add_event(
                memory_id=row.memory_id,
                event_type=ProvenanceEventType.merged,
                agent_id=row.agent_id,
                actor=row.executed_by or "system",
                parent_memory_ids=[canonical_id] if canonical_id else [],
                metadata=details,
            )
        elif row.action == "tier_change":
            graph.add_event(
                memory_id=row.memory_id,
                event_type=ProvenanceEventType.modified,
                agent_id=row.agent_id,
                actor=row.executed_by or "system",
                metadata=dict(row.details) if row.details else {},
            )

    return graph
