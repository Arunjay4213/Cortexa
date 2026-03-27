"""Tests for cortexa.engine.staleness."""

from datetime import datetime, timedelta

from cortexa.engine.staleness import StalenessDetector
from cortexa.engine.models import Memory


class TestStalenessDetector:
    def setup_method(self):
        self.detector = StalenessDetector(staleness_days=30, similarity_threshold=0.85)
        self.now = datetime(2026, 3, 24, 12, 0, 0)

    def test_source_updated_after_creation(self):
        """mem_2847 scenario — source updated 6 weeks after creation."""
        three_months_ago = self.now - timedelta(days=90)
        six_weeks_ago = self.now - timedelta(weeks=6)
        memory = Memory(
            id="mem_2847",
            content="All orders ship express (2-day delivery)",
            source="shipping_policy.md",
            source_updated_at=six_weeks_ago,
            created_at=three_months_ago,
        )
        stale = self.detector.detect([memory])
        assert len(stale) == 1
        assert stale[0].memory_id == "mem_2847"
        assert "Source updated" in stale[0].reason

    def test_old_memory_with_source(self):
        """Memory older than staleness_days with a source is stale."""
        old = self.now - timedelta(days=60)
        memory = Memory(
            id="m1", content="Old policy info",
            source="policy.md", created_at=old,
        )
        stale = self.detector.detect([memory])
        assert len(stale) == 1
        assert stale[0].days_since_update >= 60

    def test_old_memory_without_source_not_stale(self):
        """Memory without a source shouldn't be flagged by age check."""
        old = self.now - timedelta(days=60)
        memory = Memory(
            id="m1", content="No source info",
            source=None, created_at=old,
        )
        stale = self.detector.detect([memory])
        assert len(stale) == 0

    def test_fresh_memory_not_stale(self):
        recent = self.now - timedelta(days=5)
        memory = Memory(
            id="m1", content="Fresh info",
            source="docs.md", created_at=recent,
        )
        stale = self.detector.detect([memory])
        assert len(stale) == 0

    def test_embedding_similarity_overrides_age(self):
        """Old memory with high embedding similarity is NOT stale."""
        old = self.now - timedelta(days=60)
        memory = Memory(
            id="m1", content="Still accurate",
            source="docs.md", created_at=old,
            embedding=[1.0, 0.0, 0.0],
        )
        # Source embedding is very similar
        source_embeddings = {"m1": [0.99, 0.01, 0.0]}
        stale = self.detector.detect([memory], source_embeddings)
        assert len(stale) == 0

    def test_embedding_divergence_flags_stale(self):
        """Old memory with low embedding similarity IS stale."""
        old = self.now - timedelta(days=60)
        memory = Memory(
            id="m1", content="Outdated info",
            source="docs.md", created_at=old,
            embedding=[1.0, 0.0, 0.0],
        )
        # Source embedding has diverged
        source_embeddings = {"m1": [0.0, 1.0, 0.0]}
        stale = self.detector.detect([memory], source_embeddings)
        assert len(stale) == 1
        assert stale[0].similarity_to_source is not None
        assert stale[0].similarity_to_source < 0.85

    def test_empty_input(self):
        stale = self.detector.detect([])
        assert stale == []

    def test_source_updated_at_before_created_at(self):
        """source_updated_at < created_at means source hasn't changed since."""
        memory = Memory(
            id="m1", content="Recent memory",
            source="docs.md",
            created_at=self.now - timedelta(days=5),
            source_updated_at=self.now - timedelta(days=10),
        )
        stale = self.detector.detect([memory])
        assert len(stale) == 0

    def test_fixture_stale_detection(self, memories):
        """Test against the synthetic dataset — mem_2847 should be stale."""
        stale = self.detector.detect(memories)
        stale_ids = [s.memory_id for s in stale]
        assert "mem_2847" in stale_ids


class TestCosineSimilarity:
    def test_identical_vectors(self):
        sim = StalenessDetector._cosine_similarity([1.0, 0.0], [1.0, 0.0])
        assert abs(sim - 1.0) < 0.001

    def test_orthogonal_vectors(self):
        sim = StalenessDetector._cosine_similarity([1.0, 0.0], [0.0, 1.0])
        assert abs(sim) < 0.001

    def test_opposite_vectors(self):
        sim = StalenessDetector._cosine_similarity([1.0, 0.0], [-1.0, 0.0])
        assert abs(sim - (-1.0)) < 0.001

    def test_empty_vectors(self):
        assert StalenessDetector._cosine_similarity([], []) == 0.0

    def test_mismatched_lengths(self):
        assert StalenessDetector._cosine_similarity([1.0], [1.0, 0.0]) == 0.0
