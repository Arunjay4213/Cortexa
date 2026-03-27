"""Tests for cortexa.engine.entailment."""

from unittest.mock import MagicMock, patch

import pytest

from cortexa.engine.entailment import (
    EntailmentScorer,
    TfidfFallbackBackend,
    _split_memory_sentences,
)
from cortexa.engine.exceptions import EntailmentError
from cortexa.engine.models import Claim, EntailmentScore, Memory


class TestSplitMemorySentences:
    def test_single_sentence(self):
        result = _split_memory_sentences("Free shipping on orders over $50")
        assert len(result) == 1

    def test_multiple_sentences(self):
        text = "Free shipping on orders over $50. Returns accepted within 30 days. Contact support for help."
        result = _split_memory_sentences(text)
        assert len(result) == 3

    def test_short_fragments_filtered(self):
        text = "OK. Hi. This is a real sentence."
        result = _split_memory_sentences(text)
        # "OK" and "Hi" are <= 5 chars, should be filtered
        assert all(len(s) > 5 for s in result)

    def test_empty_string(self):
        result = _split_memory_sentences("")
        assert result == []


class TestEntailmentScorerInit:
    def test_api_backend(self):
        scorer = EntailmentScorer(backend="api")
        assert scorer._backend is not None

    def test_invalid_backend(self):
        import pytest
        with pytest.raises(ValueError, match="Unknown backend"):
            EntailmentScorer(backend="invalid")


class TestEntailmentScorerWithMock:
    """Test EntailmentScorer with mocked backend to avoid loading real models."""

    def setup_method(self):
        self.scorer = EntailmentScorer(backend="api")
        # Replace backend with a mock
        self.mock_backend = MagicMock()
        self.scorer._backend = self.mock_backend

    def test_score_single_pair(self):
        self.mock_backend.score_pairs.return_value = [(0.1, 0.8, 0.1)]

        memory = Memory(id="m1", content="The price is $49.99")
        claim = Claim(id="c1", text="Price is $49.99", source_response="resp")

        result = self.scorer.score(memory, claim)
        assert isinstance(result, EntailmentScore)
        assert result.memory_id == "m1"
        assert result.claim_id == "c1"
        assert result.entailment == 0.8
        assert result.label == "entailment"

    def test_score_batch(self):
        # 2 memories x 1 claim = 2 pairs
        self.mock_backend.score_pairs.return_value = [
            (0.1, 0.8, 0.1),  # m1 entails c1
            (0.7, 0.1, 0.2),  # m2 contradicts c1
        ]

        memories = [
            Memory(id="m1", content="Price is $49.99"),
            Memory(id="m2", content="Price is $199.99"),
        ]
        claims = [Claim(id="c1", text="Costs $49.99", source_response="resp")]

        results = self.scorer.score_batch(claims, memories)
        assert len(results) == 2
        assert results[0].label == "entailment"
        assert results[1].label == "contradiction"

    def test_summac_max_aggregation(self):
        """Multi-sentence memory should take MAX entailment across sentences."""
        # Memory has 2 sentences: first irrelevant, second entails
        memory = Memory(
            id="m1",
            content="We have a great selection. The premium plan costs $49.99 per month."
        )
        claim = Claim(id="c1", text="Price is $49.99", source_response="resp")

        # Two sentence-claim pairs: sentence1 vs claim, sentence2 vs claim
        self.mock_backend.score_pairs.return_value = [
            (0.1, 0.2, 0.7),  # sentence 1: neutral
            (0.1, 0.9, 0.0),  # sentence 2: strong entailment
        ]

        results = self.scorer.score_batch([claim], [memory])
        assert len(results) == 1
        # Should take MAX entailment = 0.9
        assert results[0].entailment == 0.9
        assert results[0].label == "entailment"

    def test_empty_inputs(self):
        results = self.scorer.score_batch([], [])
        assert results == []

    def test_confidence_is_max_prob(self):
        self.mock_backend.score_pairs.return_value = [(0.1, 0.3, 0.6)]

        memory = Memory(id="m1", content="Something")
        claim = Claim(id="c1", text="Something", source_response="resp")
        result = self.scorer.score(memory, claim)
        assert result.confidence == 0.6  # max of (0.1, 0.3, 0.6)


class TestTfidfFallbackBackend:
    """Test the TF-IDF cosine similarity fallback."""

    def setup_method(self):
        self.backend = TfidfFallbackBackend()

    def test_high_similarity_pair(self):
        """Nearly identical text should produce high entailment."""
        pairs = [("Express shipping costs $9.99", "Shipping costs $9.99")]
        results = self.backend.score_pairs(pairs)
        assert len(results) == 1
        cont, ent, neut = results[0]
        assert ent > 0.5  # high similarity → high entailment
        assert abs(cont + ent + neut - 1.0) < 0.01  # sums to ~1

    def test_low_similarity_pair(self):
        """Unrelated text should produce low entailment."""
        pairs = [("The weather is sunny today", "Express shipping costs $9.99")]
        results = self.backend.score_pairs(pairs)
        cont, ent, neut = results[0]
        assert ent < 0.3  # low similarity → low entailment
        assert neut > ent  # mostly neutral

    def test_differentiated_scores(self):
        """Different pairs should produce different scores — not uniform."""
        pairs = [
            ("Express shipping costs $9.99", "Shipping costs $9.99"),
            ("The premium plan costs $49.99 per month", "Shipping costs $9.99"),
            ("Returns accepted within 30 days", "Shipping costs $9.99"),
        ]
        results = self.backend.score_pairs(pairs)
        ent_scores = [r[1] for r in results]

        # The first pair should have highest entailment (most similar)
        assert ent_scores[0] > ent_scores[1]
        assert ent_scores[0] > ent_scores[2]
        # Scores should NOT all be equal (the whole point of the fix)
        assert len(set(round(s, 4) for s in ent_scores)) > 1

    def test_probabilities_sum_to_one(self):
        """All output triples should sum to ~1.0."""
        pairs = [
            ("Test premise", "Test hypothesis"),
            ("Another premise entirely", "Different hypothesis"),
        ]
        results = self.backend.score_pairs(pairs)
        for cont, ent, neut in results:
            assert abs(cont + ent + neut - 1.0) < 0.01
            assert cont >= 0 and ent >= 0 and neut >= 0

    def test_empty_text(self):
        """Empty or very short text should not crash."""
        pairs = [("", "test"), ("test", "")]
        results = self.backend.score_pairs(pairs)
        assert len(results) == 2
        for cont, ent, neut in results:
            assert abs(cont + ent + neut - 1.0) < 0.01

    def test_identical_text(self):
        """Identical text should produce near-max entailment."""
        pairs = [("The price is forty nine dollars", "The price is forty nine dollars")]
        results = self.backend.score_pairs(pairs)
        _, ent, _ = results[0]
        assert ent >= 0.9  # identical text → very high similarity


class TestEntailmentScorerFallback:
    """Test that EntailmentScorer falls back to TF-IDF when primary fails."""

    def test_fallback_on_api_failure(self):
        """When API backend raises, should fall back to TF-IDF."""
        scorer = EntailmentScorer(backend="api")
        # Make the API backend always raise
        scorer._backend = MagicMock()
        scorer._backend.score_pairs.side_effect = EntailmentError("no API key")

        memories = [
            Memory(id="m1", content="Express shipping costs $9.99"),
            Memory(id="m2", content="Returns accepted within 30 days"),
        ]
        claims = [Claim(id="c1", text="Shipping costs $9.99", source_response="resp")]

        results = scorer.score_batch(claims, memories)
        assert len(results) == 2
        # m1 should have higher entailment than m2 (more similar to claim)
        m1_score = next(r for r in results if r.memory_id == "m1")
        m2_score = next(r for r in results if r.memory_id == "m2")
        assert m1_score.entailment > m2_score.entailment

    def test_tfidf_backend_option(self):
        """Can explicitly create scorer with tfidf backend."""
        scorer = EntailmentScorer(backend="tfidf")
        memories = [Memory(id="m1", content="Test content")]
        claims = [Claim(id="c1", text="Test content", source_response="resp")]
        results = scorer.score_batch(claims, memories)
        assert len(results) == 1
        assert results[0].entailment > 0.5  # similar text

    def test_fallback_produces_differentiated_mas(self):
        """End-to-end: fallback scores feed into attribution and produce varied MAS."""
        from cortexa.engine.attribution import AttributionComputer

        scorer = EntailmentScorer(backend="tfidf")
        attrib = AttributionComputer()

        memories = [
            Memory(id="m1", content="Express shipping costs $9.99"),
            Memory(id="m2", content="The premium plan costs $49.99 per month"),
            Memory(id="m3", content="Free shipping on orders over $50"),
            Memory(id="m4", content="Returns accepted within 30 days"),
            Memory(id="m5", content="Contact support at help@example.com"),
        ]
        claims = [Claim(id="c1", text="Shipping costs $9.99", source_response="resp")]

        entailments = scorer.score_batch(claims, memories)
        attributions = attrib.compute(claims, memories, entailments)

        mas_scores = [a.mas_score for a in attributions]
        # Scores should NOT all be 0.20 (1/5 = uniform) — that was the bug
        assert len(set(round(s, 2) for s in mas_scores)) > 1
        # Memory about shipping should have highest MAS
        m1_mas = next(a.mas_score for a in attributions if a.memory_id == "m1")
        assert m1_mas == max(mas_scores)
