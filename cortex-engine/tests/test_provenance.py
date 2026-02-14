"""End-to-end tests for the provenance graph.

Tests all ORM models, ProvenanceGraph write/read operations, F(u)/I(u)
queries, attribution versioning, and UserFootprint serialisation.

Uses an async SQLite backend (via conftest.py fixtures). PostgreSQL-specific
features (partitioning, partial indexes) are not exercised here — those are
validated by the Alembic migration against a real PG instance.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text

from cortex.compliance.provenance import NUM_SHARDS, ProvenanceGraph, UserFootprint
from cortex.db.models.compliance import ComplianceCertificate, RequestType
from cortex.db.models.provenance import (
    AttributionEdge,
    CreationEdge,
    Criticality,
    DerivationEdge,
    DerivationType,
    EmbeddingNode,
    InteractionNode,
    MemoryNode,
    MemoryStatus,
    MemoryType,
    NodeType,
    ResponseNode,
    ScoreType,
    StatementAttributionEdge,
    SummaryNode,
)

# ── Helpers ─────────────────────────────────────────────────────────────


@pytest.fixture
def graph():
    return ProvenanceGraph()


def _now():
    return datetime.now(UTC)


# ── ORM Model Tests ────────────────────────────────────────────────────


class TestInteractionNode:
    async def test_create_and_read(self, session):
        node = InteractionNode(
            user_id="user-1",
            query="What is CortexOS?",
            response="An observability layer for AI memory systems.",
            timestamp=_now(),
            agent_id="test-agent",
            transaction_cost=0.005,
            metadata_={"model": "gpt-4"},
        )
        session.add(node)
        await session.flush()

        assert isinstance(node.id, UUID)

        result = await session.execute(
            select(InteractionNode).where(InteractionNode.id == node.id)
        )
        loaded = result.scalar_one()
        assert loaded.user_id == "user-1"
        assert loaded.query == "What is CortexOS?"
        assert loaded.transaction_cost == 0.005

    async def test_metadata_round_trip(self, session):
        node = InteractionNode(
            user_id="user-1",
            query="q",
            response="r",
            timestamp=_now(),
            agent_id="a",
            metadata_={"temperature": 0.7, "top_p": 0.9},
        )
        session.add(node)
        await session.flush()

        result = await session.execute(
            select(InteractionNode).where(InteractionNode.id == node.id)
        )
        loaded = result.scalar_one()
        # SQLite stores JSONB as TEXT; SQLAlchemy deserialises it back.
        assert loaded.metadata_["temperature"] == 0.7


class TestMemoryNode:
    async def test_create_with_enums(self, session):
        node = MemoryNode(
            content="User prefers dark mode",
            memory_type=MemoryType.raw,
            status=MemoryStatus.active,
            shard_id=3,
            slice_id=0,
            created_at=_now(),
            created_by_user_id="user-1",
            token_count=5,
            criticality=Criticality.normal,
        )
        session.add(node)
        await session.flush()

        result = await session.execute(
            select(MemoryNode).where(MemoryNode.id == node.id)
        )
        loaded = result.scalar_one()
        assert loaded.memory_type == MemoryType.raw
        assert loaded.status == MemoryStatus.active
        assert loaded.criticality == Criticality.normal
        assert loaded.shard_id == 3

    async def test_deletion_scheduled_at(self, session):
        future = _now() + timedelta(days=30)
        node = MemoryNode(
            content="to be deleted",
            memory_type=MemoryType.raw,
            status=MemoryStatus.pending_deletion,
            shard_id=0,
            slice_id=0,
            created_at=_now(),
            created_by_user_id="user-1",
            deletion_scheduled_at=future,
        )
        session.add(node)
        await session.flush()

        loaded = (
            await session.execute(
                select(MemoryNode).where(MemoryNode.id == node.id)
            )
        ).scalar_one()
        assert loaded.deletion_scheduled_at is not None
        assert loaded.status == MemoryStatus.pending_deletion


class TestEdgeModels:
    async def test_creation_edge(self, session):
        interaction = InteractionNode(
            user_id="u", query="q", response="r",
            timestamp=_now(), agent_id="a",
        )
        session.add(interaction)
        await session.flush()

        edge = CreationEdge(
            source_id=interaction.id,
            target_id=uuid4(),  # memory ID
            created_at=_now(),
        )
        session.add(edge)
        await session.flush()

        loaded = (
            await session.execute(
                select(CreationEdge).where(CreationEdge.id == edge.id)
            )
        ).scalar_one()
        assert loaded.source_id == interaction.id

    async def test_derivation_edge_polymorphic(self, session):
        edge = DerivationEdge(
            source_id=uuid4(),
            source_type=NodeType.memory,
            target_id=uuid4(),
            target_type=NodeType.embedding,
            derivation_type=DerivationType.embedding,
            created_at=_now(),
        )
        session.add(edge)
        await session.flush()

        loaded = (
            await session.execute(
                select(DerivationEdge).where(DerivationEdge.id == edge.id)
            )
        ).scalar_one()
        assert loaded.source_type == NodeType.memory
        assert loaded.target_type == NodeType.embedding
        assert loaded.derivation_type == DerivationType.embedding

    async def test_attribution_edge_versioning_columns(self, session):
        interaction = InteractionNode(
            user_id="u", query="q", response="r",
            timestamp=_now(), agent_id="a",
        )
        session.add(interaction)
        await session.flush()

        edge = AttributionEdge(
            source_id=uuid4(),
            target_id=interaction.id,
            score=0.85,
            score_type=ScoreType.eas,
            version=1,
            is_current=True,
            created_at=_now(),
        )
        session.add(edge)
        await session.flush()

        loaded = (
            await session.execute(
                select(AttributionEdge).where(AttributionEdge.id == edge.id)
            )
        ).scalar_one()
        assert loaded.score == 0.85
        assert loaded.score_type == ScoreType.eas
        assert loaded.version == 1
        assert loaded.is_current is True


class TestComplianceCertificate:
    async def test_create_certificate(self, session):
        cert = ComplianceCertificate(
            user_id="user-1",
            request_type=RequestType.gdpr_deletion,
            footprint_snapshot={"memory_node_ids": ["abc"]},
            nodes_deleted=5,
            edges_affected=12,
            deletion_timestamp=_now(),
            grace_period_end=_now() + timedelta(days=30),
            certificate_hash="a" * 64,
        )
        session.add(cert)
        await session.flush()

        loaded = (
            await session.execute(
                select(ComplianceCertificate).where(
                    ComplianceCertificate.id == cert.id
                )
            )
        ).scalar_one()
        assert loaded.request_type == RequestType.gdpr_deletion
        assert loaded.verified is False
        assert loaded.nodes_deleted == 5


# ── ProvenanceGraph Write Path ──────────────────────────────────────────


class TestRecordTransaction:
    async def test_creates_interaction_and_attribution_edges(self, session, graph):
        mem_ids = [uuid4(), uuid4(), uuid4()]
        scores = [0.5, 0.3, 0.2]

        interaction = await graph.record_transaction(
            session,
            user_id="user-1",
            query="What is X?",
            response="X is Y.",
            agent_id="agent-1",
            transaction_cost=0.01,
            memory_ids=mem_ids,
            attribution_scores=scores,
            score_type=ScoreType.calibrated,
        )
        await session.flush()

        assert isinstance(interaction.id, UUID)
        assert interaction.user_id == "user-1"
        assert interaction.transaction_cost == 0.01

        # Verify attribution edges
        result = await session.execute(
            select(AttributionEdge).where(
                AttributionEdge.target_id == interaction.id
            )
        )
        edges = result.scalars().all()
        assert len(edges) == 3

        edge_scores = sorted([e.score for e in edges], reverse=True)
        assert edge_scores == [0.5, 0.3, 0.2]

        for edge in edges:
            assert edge.score_type == ScoreType.calibrated
            assert edge.version == 1
            assert edge.is_current is True

    async def test_zero_memories_creates_only_interaction(self, session, graph):
        interaction = await graph.record_transaction(
            session,
            user_id="user-1",
            query="Hello",
            response="Hi there",
            agent_id="agent-1",
            transaction_cost=0.001,
            memory_ids=[],
            attribution_scores=[],
        )
        await session.flush()

        edges = (
            await session.execute(
                select(AttributionEdge).where(
                    AttributionEdge.target_id == interaction.id
                )
            )
        ).scalars().all()
        assert len(edges) == 0

    async def test_custom_timestamp_and_metadata(self, session, graph):
        custom_ts = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        interaction = await graph.record_transaction(
            session,
            user_id="user-1",
            query="q",
            response="r",
            agent_id="a",
            transaction_cost=0.0,
            memory_ids=[],
            attribution_scores=[],
            timestamp=custom_ts,
            metadata={"model_version": "v2"},
        )
        await session.flush()

        loaded = (
            await session.execute(
                select(InteractionNode).where(
                    InteractionNode.id == interaction.id
                )
            )
        ).scalar_one()
        assert loaded.metadata_["model_version"] == "v2"


class TestRecordMemoryCreation:
    async def test_creates_memory_creation_edge_embedding_derivation(
        self, session, graph
    ):
        # First create an interaction to link to.
        interaction = await graph.record_transaction(
            session,
            user_id="user-1",
            query="q",
            response="r",
            agent_id="a",
            transaction_cost=0.0,
            memory_ids=[],
            attribution_scores=[],
        )
        await session.flush()

        mem_node, emb_node = await graph.record_memory_creation(
            session,
            interaction_id=interaction.id,
            content="User likes coffee",
            user_id="user-1",
            vector_ref="pinecone-abc",
            embedding_model="text-embedding-3-small",
            embedding_dim=1536,
            token_count=4,
        )
        await session.flush()

        # Verify memory node
        assert isinstance(mem_node.id, UUID)
        assert mem_node.content == "User likes coffee"
        assert mem_node.memory_type == MemoryType.raw
        assert mem_node.status == MemoryStatus.active
        assert mem_node.shard_id == hash("user-1") % NUM_SHARDS
        assert mem_node.token_count == 4

        # Verify embedding node
        assert emb_node.vector_ref == "pinecone-abc"
        assert emb_node.model_version == "text-embedding-3-small"
        assert emb_node.dimensions == 1536

        # Verify creation edge
        creation = (
            await session.execute(
                select(CreationEdge).where(
                    CreationEdge.source_id == interaction.id,
                    CreationEdge.target_id == mem_node.id,
                )
            )
        ).scalar_one()
        assert creation is not None

        # Verify derivation edge
        derivation = (
            await session.execute(
                select(DerivationEdge).where(
                    DerivationEdge.source_id == mem_node.id,
                    DerivationEdge.target_id == emb_node.id,
                )
            )
        ).scalar_one()
        assert derivation.source_type == NodeType.memory
        assert derivation.target_type == NodeType.embedding
        assert derivation.derivation_type == DerivationType.embedding

    async def test_slice_id_auto_increments(self, session, graph):
        interaction = await graph.record_transaction(
            session,
            user_id="user-slice",
            query="q",
            response="r",
            agent_id="a",
            transaction_cost=0.0,
            memory_ids=[],
            attribution_scores=[],
        )
        await session.flush()

        mem1, _ = await graph.record_memory_creation(
            session,
            interaction_id=interaction.id,
            content="first",
            user_id="user-slice",
            vector_ref="v1",
            embedding_model="m",
            embedding_dim=384,
        )
        await session.flush()

        mem2, _ = await graph.record_memory_creation(
            session,
            interaction_id=interaction.id,
            content="second",
            user_id="user-slice",
            vector_ref="v2",
            embedding_model="m",
            embedding_dim=384,
        )
        await session.flush()

        assert mem1.slice_id == 0
        assert mem2.slice_id == 1


class TestRecordConsolidation:
    async def test_creates_summary_and_derivation_edges(self, session, graph):
        mem_ids = [uuid4(), uuid4(), uuid4()]

        summary = await graph.record_consolidation(
            session,
            source_memory_ids=mem_ids,
            summary_content="Combined summary of 3 memories",
            method="llm_consolidation",
        )
        await session.flush()

        assert isinstance(summary.id, UUID)
        assert summary.source_memory_count == 3
        assert summary.method == "llm_consolidation"

        # Verify 3 derivation edges
        edges = (
            await session.execute(
                select(DerivationEdge).where(
                    DerivationEdge.target_id == summary.id
                )
            )
        ).scalars().all()
        assert len(edges) == 3
        for e in edges:
            assert e.source_type == NodeType.memory
            assert e.target_type == NodeType.summary
            assert e.derivation_type == DerivationType.consolidation


class TestRecordContextcite:
    async def test_creates_response_node_and_statement_edges(self, session, graph):
        interaction = InteractionNode(
            user_id="u", query="q", response="r",
            timestamp=_now(), agent_id="a",
        )
        session.add(interaction)
        await session.flush()

        mem_id_1 = uuid4()
        mem_id_2 = uuid4()

        response_node = await graph.record_contextcite(
            session,
            interaction_id=interaction.id,
            statements=[
                {"text": "Statement one.", "index": 0},
                {"text": "Statement two.", "index": 1},
            ],
            memory_scores=[
                {"memory_id": mem_id_1, "statement_index": 0, "score": 0.9},
                {"memory_id": mem_id_2, "statement_index": 0, "score": 0.1},
                {"memory_id": mem_id_1, "statement_index": 1, "score": 0.6},
            ],
        )
        await session.flush()

        assert response_node.interaction_id == interaction.id

        edges = (
            await session.execute(
                select(StatementAttributionEdge).where(
                    StatementAttributionEdge.response_id == response_node.id
                )
            )
        ).scalars().all()
        assert len(edges) == 3

        # Check specific scores
        stmt0_edges = [e for e in edges if e.statement_index == 0]
        assert len(stmt0_edges) == 2
        assert sorted([e.score for e in stmt0_edges]) == [0.1, 0.9]


class TestUpdateAttribution:
    async def test_creates_new_version_and_supersedes_old(self, session, graph):
        mem_id = uuid4()
        interaction = await graph.record_transaction(
            session,
            user_id="user-1",
            query="q",
            response="r",
            agent_id="a",
            transaction_cost=0.0,
            memory_ids=[mem_id],
            attribution_scores=[0.7],
            score_type=ScoreType.eas,
        )
        await session.flush()

        # Calibrate the score
        new_edge = await graph.update_attribution(
            session,
            source_id=mem_id,
            target_id=interaction.id,
            new_score=0.65,
            new_score_type=ScoreType.calibrated,
        )
        await session.flush()

        assert new_edge.version == 2
        assert new_edge.is_current is True
        assert new_edge.score == 0.65

        # Verify old edge is superseded
        all_edges = (
            await session.execute(
                select(AttributionEdge).where(
                    AttributionEdge.source_id == mem_id,
                    AttributionEdge.target_id == interaction.id,
                )
            )
        ).scalars().all()
        assert len(all_edges) == 2

        current = [e for e in all_edges if e.is_current]
        superseded = [e for e in all_edges if not e.is_current]
        assert len(current) == 1
        assert len(superseded) == 1
        assert current[0].version == 2
        assert current[0].score == 0.65
        assert superseded[0].version == 1
        assert superseded[0].score == 0.7

    async def test_multiple_calibrations(self, session, graph):
        mem_id = uuid4()
        interaction = await graph.record_transaction(
            session,
            user_id="u",
            query="q",
            response="r",
            agent_id="a",
            transaction_cost=0.0,
            memory_ids=[mem_id],
            attribution_scores=[0.5],
        )
        await session.flush()

        # Calibrate twice
        await graph.update_attribution(
            session,
            source_id=mem_id,
            target_id=interaction.id,
            new_score=0.55,
            new_score_type=ScoreType.calibrated,
        )
        await session.flush()

        edge_v3 = await graph.update_attribution(
            session,
            source_id=mem_id,
            target_id=interaction.id,
            new_score=0.58,
            new_score_type=ScoreType.calibrated,
        )
        await session.flush()

        assert edge_v3.version == 3
        assert edge_v3.score == 0.58

        # Only one should be current
        current = (
            await session.execute(
                select(AttributionEdge).where(
                    AttributionEdge.source_id == mem_id,
                    AttributionEdge.target_id == interaction.id,
                    AttributionEdge.is_current.is_(True),
                )
            )
        ).scalars().all()
        assert len(current) == 1
        assert current[0].version == 3


# ── F(u) and I(u) Tests ────────────────────────────────────────────────


class TestComputeUserFootprint:
    async def test_simple_footprint(self, session, graph):
        """User creates 1 interaction → 1 memory → 1 embedding.
        F(u) should return the memory and embedding."""
        interaction = await graph.record_transaction(
            session,
            user_id="fp-user",
            query="q",
            response="r",
            agent_id="a",
            transaction_cost=0.0,
            memory_ids=[],
            attribution_scores=[],
        )
        await session.flush()

        mem, emb = await graph.record_memory_creation(
            session,
            interaction_id=interaction.id,
            content="A fact",
            user_id="fp-user",
            vector_ref="v1",
            embedding_model="m",
            embedding_dim=384,
        )
        await session.flush()

        footprint = await graph.compute_user_footprint(session, "fp-user")

        assert footprint.user_id == "fp-user"
        assert len(footprint.interaction_node_ids) == 1
        assert interaction.id in footprint.interaction_node_ids
        assert len(footprint.memory_node_ids) == 1
        assert mem.id in footprint.memory_node_ids
        assert len(footprint.embedding_node_ids) == 1
        assert emb.id in footprint.embedding_node_ids

    async def test_multi_hop_derivation_chain(self, session, graph):
        """memory → embedding, memory → summary → embedding (via consolidation).
        F(u) must follow the full derivation chain."""
        interaction = await graph.record_transaction(
            session,
            user_id="chain-user",
            query="q",
            response="r",
            agent_id="a",
            transaction_cost=0.0,
            memory_ids=[],
            attribution_scores=[],
        )
        await session.flush()

        mem1, emb1 = await graph.record_memory_creation(
            session,
            interaction_id=interaction.id,
            content="fact 1",
            user_id="chain-user",
            vector_ref="v1",
            embedding_model="m",
            embedding_dim=384,
        )
        mem2, emb2 = await graph.record_memory_creation(
            session,
            interaction_id=interaction.id,
            content="fact 2",
            user_id="chain-user",
            vector_ref="v2",
            embedding_model="m",
            embedding_dim=384,
        )
        await session.flush()

        # Consolidate mem1 + mem2 → summary
        summary = await graph.record_consolidation(
            session,
            source_memory_ids=[mem1.id, mem2.id],
            summary_content="Combined facts",
        )
        await session.flush()

        # summary → embedding (another derivation)
        summary_emb = EmbeddingNode(
            vector_ref="v-summary",
            model_version="m",
            dimensions=384,
            created_at=_now(),
        )
        session.add(summary_emb)
        await session.flush()

        deriv = DerivationEdge(
            source_id=summary.id,
            source_type=NodeType.summary,
            target_id=summary_emb.id,
            target_type=NodeType.embedding,
            derivation_type=DerivationType.embedding,
            created_at=_now(),
        )
        session.add(deriv)
        await session.flush()

        footprint = await graph.compute_user_footprint(session, "chain-user")

        # Should find: 2 memories, 1 summary, 3 embeddings (2 mem embs + 1 summary emb)
        assert len(footprint.memory_node_ids) == 2
        assert len(footprint.summary_node_ids) == 1
        assert summary.id in footprint.summary_node_ids
        assert len(footprint.embedding_node_ids) == 3
        assert summary_emb.id in footprint.embedding_node_ids

    async def test_empty_footprint_for_unknown_user(self, session, graph):
        footprint = await graph.compute_user_footprint(session, "nonexistent-user")

        assert footprint.user_id == "nonexistent-user"
        assert len(footprint.all_node_ids) == 0

    async def test_footprint_isolation_between_users(self, session, graph):
        """User A's footprint must not include User B's data."""
        int_a = await graph.record_transaction(
            session,
            user_id="user-A",
            query="q",
            response="r",
            agent_id="a",
            transaction_cost=0.0,
            memory_ids=[],
            attribution_scores=[],
        )
        await session.flush()
        mem_a, _ = await graph.record_memory_creation(
            session,
            interaction_id=int_a.id,
            content="A's data",
            user_id="user-A",
            vector_ref="va",
            embedding_model="m",
            embedding_dim=384,
        )
        await session.flush()

        int_b = await graph.record_transaction(
            session,
            user_id="user-B",
            query="q",
            response="r",
            agent_id="a",
            transaction_cost=0.0,
            memory_ids=[],
            attribution_scores=[],
        )
        await session.flush()
        mem_b, _ = await graph.record_memory_creation(
            session,
            interaction_id=int_b.id,
            content="B's data",
            user_id="user-B",
            vector_ref="vb",
            embedding_model="m",
            embedding_dim=384,
        )
        await session.flush()

        fp_a = await graph.compute_user_footprint(session, "user-A")
        fp_b = await graph.compute_user_footprint(session, "user-B")

        assert mem_a.id in fp_a.memory_node_ids
        assert mem_b.id not in fp_a.memory_node_ids

        assert mem_b.id in fp_b.memory_node_ids
        assert mem_a.id not in fp_b.memory_node_ids


class TestComputeInfluenceFootprint:
    async def test_finds_influenced_interactions(self, session, graph):
        """User A creates a memory. User B's interaction is attributed to that memory.
        I(A) should return B's interaction."""
        # User A creates a memory
        int_a = await graph.record_transaction(
            session,
            user_id="influencer",
            query="q",
            response="r",
            agent_id="a",
            transaction_cost=0.0,
            memory_ids=[],
            attribution_scores=[],
        )
        await session.flush()

        mem_a, _ = await graph.record_memory_creation(
            session,
            interaction_id=int_a.id,
            content="Influencer's knowledge",
            user_id="influencer",
            vector_ref="v-inf",
            embedding_model="m",
            embedding_dim=384,
        )
        await session.flush()

        # User B's interaction is influenced by A's memory
        int_b = await graph.record_transaction(
            session,
            user_id="influenced",
            query="question from B",
            response="answer using A's memory",
            agent_id="a",
            transaction_cost=0.0,
            memory_ids=[mem_a.id],
            attribution_scores=[0.8],
        )
        await session.flush()

        influenced = await graph.compute_influence_footprint(session, "influencer")
        assert int_b.id in influenced

    async def test_zero_score_not_included(self, session, graph):
        """Attribution edges with score=0 should not count as influence."""
        int_a = await graph.record_transaction(
            session,
            user_id="zero-inf",
            query="q",
            response="r",
            agent_id="a",
            transaction_cost=0.0,
            memory_ids=[],
            attribution_scores=[],
        )
        await session.flush()

        mem, _ = await graph.record_memory_creation(
            session,
            interaction_id=int_a.id,
            content="data",
            user_id="zero-inf",
            vector_ref="vz",
            embedding_model="m",
            embedding_dim=384,
        )
        await session.flush()

        int_b = await graph.record_transaction(
            session,
            user_id="other",
            query="q2",
            response="r2",
            agent_id="a",
            transaction_cost=0.0,
            memory_ids=[mem.id],
            attribution_scores=[0.0],  # zero attribution
        )
        await session.flush()

        influenced = await graph.compute_influence_footprint(session, "zero-inf")
        assert int_b.id not in influenced

    async def test_empty_influence_for_unknown_user(self, session, graph):
        influenced = await graph.compute_influence_footprint(
            session, "no-such-user"
        )
        assert influenced == []


# ── UserFootprint Dataclass Tests ───────────────────────────────────────


class TestUserFootprint:
    def test_all_node_ids(self):
        fp = UserFootprint(
            user_id="u",
            memory_node_ids=[uuid4()],
            summary_node_ids=[uuid4()],
            embedding_node_ids=[uuid4(), uuid4()],
            interaction_node_ids=[uuid4()],
        )
        assert len(fp.all_node_ids) == 5

    def test_serialize(self):
        mid = uuid4()
        fp = UserFootprint(user_id="test-user", memory_node_ids=[mid])
        data = fp.serialize()
        assert data["user_id"] == "test-user"
        assert data["memory_node_ids"] == [str(mid)]
        assert data["summary_node_ids"] == []
        assert data["embedding_node_ids"] == []
        assert data["interaction_node_ids"] == []

    def test_certificate_hash_deterministic(self):
        mid = uuid4()
        fp1 = UserFootprint(user_id="u", memory_node_ids=[mid])
        fp2 = UserFootprint(user_id="u", memory_node_ids=[mid])
        assert fp1.certificate_hash() == fp2.certificate_hash()
        assert len(fp1.certificate_hash()) == 64  # SHA-256 hex

    def test_certificate_hash_changes_with_content(self):
        fp1 = UserFootprint(user_id="u", memory_node_ids=[uuid4()])
        fp2 = UserFootprint(user_id="u", memory_node_ids=[uuid4()])
        assert fp1.certificate_hash() != fp2.certificate_hash()


# ── Full End-to-End Pipeline ────────────────────────────────────────────


class TestEndToEndPipeline:
    async def test_full_lifecycle(self, session, graph):
        """Simulate the full provenance lifecycle:
        1. User A asks a question (no memories yet)
        2. A memory is created from A's interaction
        3. User B asks a question and A's memory is retrieved + attributed
        4. A calibration updates the attribution score
        5. ContextCite runs on B's interaction
        6. F(A) returns A's memory + embedding
        7. I(A) returns B's interaction
        """
        # Step 1: User A's first interaction (no memories yet)
        int_a = await graph.record_transaction(
            session,
            user_id="alice",
            query="My account number is 12345",
            response="I've noted your account number.",
            agent_id="support-agent",
            transaction_cost=0.003,
            memory_ids=[],
            attribution_scores=[],
        )
        await session.flush()

        # Step 2: Memory created from Alice's interaction
        mem_a, emb_a = await graph.record_memory_creation(
            session,
            interaction_id=int_a.id,
            content="Alice's account number is 12345",
            user_id="alice",
            vector_ref="pinecone-alice-001",
            embedding_model="text-embedding-3-small",
            embedding_dim=1536,
            token_count=7,
        )
        await session.flush()

        # Step 3: Bob's interaction references Alice's memory
        int_b = await graph.record_transaction(
            session,
            user_id="bob",
            query="What's Alice's account number?",
            response="Alice's account number is 12345.",
            agent_id="support-agent",
            transaction_cost=0.005,
            memory_ids=[mem_a.id],
            attribution_scores=[0.92],
            score_type=ScoreType.eas,
        )
        await session.flush()

        # Step 4: Calibration corrects the score
        calibrated_edge = await graph.update_attribution(
            session,
            source_id=mem_a.id,
            target_id=int_b.id,
            new_score=0.88,
            new_score_type=ScoreType.calibrated,
            metadata={"calibration_model": "v1.2"},
        )
        await session.flush()

        assert calibrated_edge.version == 2
        assert calibrated_edge.score == 0.88

        # Step 5: ContextCite runs on Bob's interaction
        response_node = await graph.record_contextcite(
            session,
            interaction_id=int_b.id,
            statements=[
                {"text": "Alice's account number is 12345.", "index": 0},
            ],
            memory_scores=[
                {
                    "memory_id": mem_a.id,
                    "statement_index": 0,
                    "score": 0.95,
                },
            ],
        )
        await session.flush()

        assert response_node.interaction_id == int_b.id

        # Step 6: F(alice) — Alice's data footprint
        fp = await graph.compute_user_footprint(session, "alice")

        assert int_a.id in fp.interaction_node_ids
        assert mem_a.id in fp.memory_node_ids
        assert emb_a.id in fp.embedding_node_ids
        # Bob's data should NOT be in Alice's footprint
        assert int_b.id not in fp.interaction_node_ids

        # Step 7: I(alice) — Interactions influenced by Alice's memories
        influenced = await graph.compute_influence_footprint(session, "alice")

        assert int_b.id in influenced
        # Alice's own interaction should NOT be in I(alice) (it has no
        # attribution edges from her memories — she had no memories when
        # she asked her question).
        assert int_a.id not in influenced

        # Verify the full footprint is serialisable + hashable
        data = fp.serialize()
        assert isinstance(data, dict)
        assert len(fp.certificate_hash()) == 64
