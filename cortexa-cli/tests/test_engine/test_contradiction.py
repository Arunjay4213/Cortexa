"""Tests for cortexa.engine.contradiction."""

from cortexa.engine.contradiction import ContradictionDetector
from cortexa.engine.models import Attribution, Claim, EntailmentScore, Memory


class TestContradictionFromEntailments:
    def setup_method(self):
        self.detector = ContradictionDetector(contradiction_threshold=0.7)

    def test_entail_vs_contradict(self):
        memories = [
            Memory(id="m1", content="Free shipping on orders over $50"),
            Memory(id="m2", content="Free shipping on orders over $75"),
        ]
        claims = [
            Claim(id="c1", text="Free shipping over $50", source_response="resp"),
        ]
        entailments = [
            EntailmentScore(
                memory_id="m1", claim_id="c1",
                entailment=0.85, contradiction=0.05, neutral=0.1,
                label="entailment", confidence=0.85,
            ),
            EntailmentScore(
                memory_id="m2", claim_id="c1",
                entailment=0.05, contradiction=0.85, neutral=0.1,
                label="contradiction", confidence=0.85,
            ),
        ]
        attributions = [
            Attribution(
                claim_id="c1", memory_id="m1", mas_score=0.4,
                entailment_score=0.85, contribution_type="supporting",
            ),
            Attribution(
                claim_id="c1", memory_id="m2", mas_score=0.3,
                entailment_score=0.05, contribution_type="contradicting",
            ),
        ]

        result = self.detector.detect_from_entailments(
            memories, claims, entailments, attributions
        )
        assert len(result) == 1
        assert "m1" in {result[0].memory_id_1, result[0].memory_id_2}
        assert "m2" in {result[0].memory_id_1, result[0].memory_id_2}
        assert result[0].severity >= 0.7

    def test_no_contradiction_when_both_entail(self):
        memories = [
            Memory(id="m1", content="A"),
            Memory(id="m2", content="B"),
        ]
        claims = [Claim(id="c1", text="test", source_response="resp")]
        entailments = [
            EntailmentScore(
                memory_id="m1", claim_id="c1",
                entailment=0.8, contradiction=0.1, neutral=0.1,
                label="entailment", confidence=0.8,
            ),
            EntailmentScore(
                memory_id="m2", claim_id="c1",
                entailment=0.7, contradiction=0.1, neutral=0.2,
                label="entailment", confidence=0.7,
            ),
        ]
        attributions = [
            Attribution(
                claim_id="c1", memory_id="m1", mas_score=0.3,
                entailment_score=0.8, contribution_type="supporting",
            ),
            Attribution(
                claim_id="c1", memory_id="m2", mas_score=0.3,
                entailment_score=0.7, contribution_type="supporting",
            ),
        ]

        result = self.detector.detect_from_entailments(
            memories, claims, entailments, attributions
        )
        assert len(result) == 0

    def test_low_mas_not_flagged(self):
        """Memories with low MAS shouldn't trigger contradiction."""
        memories = [
            Memory(id="m1", content="A"),
            Memory(id="m2", content="B"),
        ]
        claims = [Claim(id="c1", text="test", source_response="resp")]
        entailments = [
            EntailmentScore(
                memory_id="m1", claim_id="c1",
                entailment=0.8, contradiction=0.1, neutral=0.1,
                label="entailment", confidence=0.8,
            ),
            EntailmentScore(
                memory_id="m2", claim_id="c1",
                entailment=0.05, contradiction=0.85, neutral=0.1,
                label="contradiction", confidence=0.85,
            ),
        ]
        # m2 has very low MAS — below 0.05 significance threshold
        attributions = [
            Attribution(
                claim_id="c1", memory_id="m1", mas_score=0.6,
                entailment_score=0.8, contribution_type="supporting",
            ),
            Attribution(
                claim_id="c1", memory_id="m2", mas_score=0.02,
                entailment_score=0.05, contribution_type="ghost",
            ),
        ]

        result = self.detector.detect_from_entailments(
            memories, claims, entailments, attributions
        )
        # m2's MAS is 0.02 < 0.05 threshold, so it's not "significant"
        assert len(result) == 0

    def test_deduplication(self):
        """Same pair shouldn't appear twice across different claims."""
        memories = [
            Memory(id="m1", content="A"),
            Memory(id="m2", content="B"),
        ]
        claims = [
            Claim(id="c1", text="test1", source_response="resp"),
            Claim(id="c2", text="test2", source_response="resp"),
        ]
        entailments = [
            EntailmentScore(
                memory_id="m1", claim_id="c1",
                entailment=0.8, contradiction=0.1, neutral=0.1,
                label="entailment", confidence=0.8,
            ),
            EntailmentScore(
                memory_id="m2", claim_id="c1",
                entailment=0.05, contradiction=0.85, neutral=0.1,
                label="contradiction", confidence=0.85,
            ),
            EntailmentScore(
                memory_id="m1", claim_id="c2",
                entailment=0.8, contradiction=0.1, neutral=0.1,
                label="entailment", confidence=0.8,
            ),
            EntailmentScore(
                memory_id="m2", claim_id="c2",
                entailment=0.05, contradiction=0.85, neutral=0.1,
                label="contradiction", confidence=0.85,
            ),
        ]
        attributions = [
            Attribution(claim_id="c1", memory_id="m1", mas_score=0.4, entailment_score=0.8, contribution_type="supporting"),
            Attribution(claim_id="c1", memory_id="m2", mas_score=0.3, entailment_score=0.05, contribution_type="contradicting"),
            Attribution(claim_id="c2", memory_id="m1", mas_score=0.4, entailment_score=0.8, contribution_type="supporting"),
            Attribution(claim_id="c2", memory_id="m2", mas_score=0.3, entailment_score=0.05, contribution_type="contradicting"),
        ]

        result = self.detector.detect_from_entailments(
            memories, claims, entailments, attributions
        )
        # Should deduplicate: m1 vs m2 only once
        assert len(result) == 1

    def test_empty_inputs(self):
        result = self.detector.detect_from_entailments([], [], [], [])
        assert result == []


class TestContradictionPairwise:
    def setup_method(self):
        self.detector = ContradictionDetector(contradiction_threshold=0.7)

    def test_with_score_fn(self):
        memories = [
            Memory(id="m1", content="Free shipping over $50"),
            Memory(id="m2", content="Free shipping over $75"),
        ]

        def mock_score(text1, text2):
            return (0.9, 0.05, 0.05)  # strong contradiction

        result = self.detector.detect_pairwise(memories, score_fn=mock_score)
        assert len(result) == 1
        assert result[0].severity >= 0.7

    def test_no_contradiction_pairwise(self):
        memories = [
            Memory(id="m1", content="A"),
            Memory(id="m2", content="B"),
        ]

        def mock_score(text1, text2):
            return (0.1, 0.1, 0.8)  # neutral

        result = self.detector.detect_pairwise(memories, score_fn=mock_score)
        assert len(result) == 0

    def test_no_score_fn(self):
        memories = [Memory(id="m1", content="A"), Memory(id="m2", content="B")]
        result = self.detector.detect_pairwise(memories, score_fn=None)
        assert result == []

    def test_single_memory(self):
        memories = [Memory(id="m1", content="A")]
        result = self.detector.detect_pairwise(memories, score_fn=lambda a, b: (0.9, 0.0, 0.1))
        assert result == []
