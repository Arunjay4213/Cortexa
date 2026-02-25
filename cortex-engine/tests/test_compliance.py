import pytest
import numpy as np
from cortex.compliance.provenance import ProvenanceGraph, ProvenanceEventType, ProvenanceNode
from cortex.compliance.sisa import SISAPartitioner, MemoryShard, UnlearningResult


class TestProvenanceGraph:
    def test_empty_graph(self):
        g = ProvenanceGraph()
        d = g.to_dict()
        assert d["stats"]["total_nodes"] == 0
        assert d["stats"]["total_edges"] == 0

    def test_add_creation_event(self):
        g = ProvenanceGraph()
        node = g.add_event("m1", ProvenanceEventType.created, agent_id="a1")
        assert node.memory_id == "m1"
        assert node.event_type == ProvenanceEventType.created

    def test_derivation_creates_edge(self):
        g = ProvenanceGraph()
        g.add_event("m1", ProvenanceEventType.created)
        g.add_event("m2", ProvenanceEventType.derived, parent_memory_ids=["m1"])
        d = g.to_dict()
        assert d["stats"]["total_nodes"] == 2
        assert d["stats"]["total_edges"] == 1

    def test_lineage_chain(self):
        """m1 -> m2 -> m3: lineage of m3 should contain all 3."""
        g = ProvenanceGraph()
        g.add_event("m1", ProvenanceEventType.created)
        g.add_event("m2", ProvenanceEventType.derived, parent_memory_ids=["m1"])
        g.add_event("m3", ProvenanceEventType.derived, parent_memory_ids=["m2"])
        lineage = g.get_lineage("m3")
        memory_ids = [n.memory_id for n in lineage]
        assert "m1" in memory_ids
        assert "m2" in memory_ids
        assert "m3" in memory_ids

    def test_descendants(self):
        """m1 -> m2, m1 -> m3: descendants of m1 should be m2 and m3."""
        g = ProvenanceGraph()
        g.add_event("m1", ProvenanceEventType.created)
        g.add_event("m2", ProvenanceEventType.derived, parent_memory_ids=["m1"])
        g.add_event("m3", ProvenanceEventType.derived, parent_memory_ids=["m1"])
        descendants = g.get_descendants("m1")
        desc_ids = [n.memory_id for n in descendants]
        assert "m2" in desc_ids
        assert "m3" in desc_ids
        assert "m1" not in desc_ids

    def test_provenance_depth(self):
        g = ProvenanceGraph()
        g.add_event("m1", ProvenanceEventType.created)
        g.add_event("m2", ProvenanceEventType.derived, parent_memory_ids=["m1"])
        g.add_event("m3", ProvenanceEventType.derived, parent_memory_ids=["m2"])
        assert g.provenance_depth("m1") == 0
        assert g.provenance_depth("m2") == 1
        assert g.provenance_depth("m3") == 2

    def test_no_cycles(self):
        """A proper DAG should never have cycles."""
        g = ProvenanceGraph()
        g.add_event("m1", ProvenanceEventType.created)
        g.add_event("m2", ProvenanceEventType.derived, parent_memory_ids=["m1"])
        g.add_event("m3", ProvenanceEventType.derived, parent_memory_ids=["m2"])
        assert g.has_cycle() is False

    def test_merge_event(self):
        """Merging two memories into one."""
        g = ProvenanceGraph()
        g.add_event("m1", ProvenanceEventType.created)
        g.add_event("m2", ProvenanceEventType.created)
        g.add_event("m3", ProvenanceEventType.merged, parent_memory_ids=["m1", "m2"])
        d = g.to_dict()
        assert d["stats"]["total_edges"] == 2  # m1->m3, m2->m3
        # Depth = len(lineage) - 1 = len([m3, m1, m2]) - 1 = 2
        assert g.provenance_depth("m3") == 2

    def test_to_dict_serialization(self):
        g = ProvenanceGraph()
        g.add_event("m1", ProvenanceEventType.created, agent_id="test-agent")
        d = g.to_dict()
        assert "nodes" in d
        assert "edges" in d
        assert "stats" in d
        assert d["nodes"][0]["agent_id"] == "test-agent"

    def test_nonexistent_memory_lineage(self):
        g = ProvenanceGraph()
        assert g.get_lineage("nonexistent") == []
        assert g.provenance_depth("nonexistent") == 0

    def test_all_event_types(self):
        """All event types should be valid."""
        g = ProvenanceGraph()
        for evt in ProvenanceEventType:
            node = g.add_event(f"m_{evt.value}", evt)
            assert node.event_type == evt


class TestSISAPartitioner:
    def test_round_robin(self):
        """Without embeddings, should partition round-robin."""
        sp = SISAPartitioner(num_shards=4)
        ids = [f"m{i}" for i in range(12)]
        shards = sp.partition(ids)
        assert len(shards) == 4
        for s in shards:
            assert s.size == 3

    def test_embedding_partition(self):
        """With embeddings, should use k-means."""
        sp = SISAPartitioner(num_shards=3)
        rng = np.random.default_rng(42)
        ids = [f"m{i}" for i in range(30)]
        emb = rng.standard_normal((30, 8))
        shards = sp.partition(ids, emb)
        assert len(shards) == 3
        total = sum(s.size for s in shards)
        assert total == 30

    def test_all_memories_assigned(self):
        """Every memory should be in exactly one shard."""
        sp = SISAPartitioner(num_shards=5)
        ids = [f"m{i}" for i in range(50)]
        sp.partition(ids)
        all_ids = set()
        for s in sp.shards:
            for mid in s.memory_ids:
                assert mid not in all_ids, f"Duplicate: {mid}"
                all_ids.add(mid)
        assert all_ids == set(ids)

    def test_find_shard(self):
        sp = SISAPartitioner(num_shards=4)
        sp.partition([f"m{i}" for i in range(20)])
        shard = sp.find_shard("m5")
        assert shard is not None
        assert "m5" in shard.memory_ids

    def test_find_shard_missing(self):
        sp = SISAPartitioner(num_shards=4)
        sp.partition([f"m{i}" for i in range(20)])
        assert sp.find_shard("nonexistent") is None

    def test_unlearn(self):
        sp = SISAPartitioner(num_shards=4)
        sp.partition([f"m{i}" for i in range(40)])
        result = sp.unlearn("m10")
        assert result is not None
        assert result.memory_id == "m10"
        assert result.efficiency_gain > 0
        # Memory should be removed from shard
        assert sp.find_shard("m10") is None

    def test_unlearn_efficiency(self):
        """More shards = higher efficiency gain."""
        ids = [f"m{i}" for i in range(100)]

        sp4 = SISAPartitioner(num_shards=4)
        sp4.partition(list(ids))
        r4 = sp4.unlearn("m50")

        sp10 = SISAPartitioner(num_shards=10)
        sp10.partition(list(ids))
        r10 = sp10.unlearn("m50")

        assert r10.efficiency_gain > r4.efficiency_gain

    def test_unlearn_missing(self):
        sp = SISAPartitioner(num_shards=4)
        sp.partition(["m1", "m2"])
        assert sp.unlearn("m99") is None

    def test_stats(self):
        sp = SISAPartitioner(num_shards=4)
        sp.partition([f"m{i}" for i in range(40)])
        stats = sp.stats()
        assert stats["num_shards"] == 4
        assert stats["total_memories"] == 40
        assert stats["min_shard_size"] > 0
        assert stats["max_shard_size"] <= 40
        assert 0 < stats["balance_ratio"] <= 1.0

    def test_single_memory(self):
        sp = SISAPartitioner(num_shards=4)
        shards = sp.partition(["m1"], np.array([[1.0, 2.0]]))
        assert len(shards) == 1
        assert shards[0].size == 1

    def test_shard_centroids_set(self):
        """Embedding-based partition should set centroids."""
        sp = SISAPartitioner(num_shards=3)
        emb = np.random.randn(30, 8)
        sp.partition([f"m{i}" for i in range(30)], emb)
        for s in sp.shards:
            if s.size > 0:
                assert len(s.embedding_centroid) == 8
