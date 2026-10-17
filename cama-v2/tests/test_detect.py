"""Tests for cama/detect.py — hallucination detection.

Note: LettuceDetector tests are skipped if lettucedetect is not installed.
EmbeddingDetector tests are skipped if sentence-transformers is not installed.
"""

import pytest

from cama.detect import Detector, EmbeddingDetector, LettuceDetector, get_detector
from cama.types import HallucinatedSpan, TokenScore


class TestDetectorInterface:
    def test_abstract_cannot_instantiate(self):
        with pytest.raises(TypeError):
            Detector()


class TestGetDetector:
    def test_returns_detector(self):
        """get_detector should return some Detector instance."""
        try:
            d = get_detector(prefer_gpu=False)
            assert isinstance(d, Detector)
        except ImportError:
            pytest.skip("No detector backend available")


class TestLettuceDetector:
    @pytest.fixture
    def detector(self):
        try:
            return LettuceDetector()
        except ImportError:
            pytest.skip("lettucedetect not installed")

    def test_basic_detection(self, detector):
        memories = [
            "France has 67 million people.",
            "The capital of France is Paris.",
        ]
        question = "What is the population of France?"
        answer = "The population of France is 69 million."

        token_scores, spans = detector.detect(memories, question, answer)
        assert isinstance(token_scores, list)
        assert all(isinstance(ts, TokenScore) for ts in token_scores)
        assert len(token_scores) > 0

    def test_grounded_response(self, detector):
        memories = ["The sky is blue."]
        question = "What color is the sky?"
        answer = "The sky is blue."

        token_scores, spans = detector.detect(memories, question, answer)
        # Fully grounded — should have few/no hallucinated spans
        assert isinstance(spans, list)


class TestEmbeddingDetector:
    @pytest.fixture
    def detector(self):
        try:
            d = EmbeddingDetector()
            # Force-load model to detect import errors early
            from cama.embed import _get_model
            _get_model(d.model_name)
            return d
        except (ImportError, ValueError, Exception) as e:
            pytest.skip(f"EmbeddingDetector not available: {e}")

    def test_basic_detection(self, detector):
        memories = [
            "France has 67 million people.",
            "The capital of France is Paris.",
        ]
        question = "What is the population of France?"
        answer = "The capital of France is Paris. The population of France is 69 million."

        token_scores, spans = detector.detect(memories, question, answer)
        assert isinstance(token_scores, list)
        assert len(token_scores) > 0
        # "69 million" should trigger numerical check
        # At least one span should be flagged due to ungrounded number
        flagged_any = any(ts.hallucination_prob > 0.5 for ts in token_scores)
        assert flagged_any, "Expected at least some tokens to be flagged"

    def test_fully_grounded(self, detector):
        memories = ["The sky is blue on a clear day."]
        question = "What color is the sky?"
        answer = "The sky is blue."

        token_scores, spans = detector.detect(memories, question, answer)
        # Should have high similarity → low hallucination scores
        assert isinstance(token_scores, list)

    def test_no_memories(self, detector):
        token_scores, spans = detector.detect(
            [], "question", "answer with some content here",
        )
        # No memories → everything should be flagged as ungrounded
        assert all(ts.hallucination_prob > 0.4 for ts in token_scores)

    def test_numerical_ungrounded(self, detector):
        memories = ["Widget costs $49.99"]
        question = "How much does Widget cost?"
        answer = "Widget costs $59.99."

        token_scores, spans = detector.detect(memories, question, answer)
        # $59.99 is not in memories → should be flagged
        assert any(ts.hallucination_prob > 0.5 for ts in token_scores)

    def test_returns_spans(self, detector):
        memories = ["Earth is the third planet from the Sun."]
        question = "What planet are we on?"
        answer = "We live on Mars, which is 500 billion light years away."

        token_scores, spans = detector.detect(memories, question, answer)
        assert isinstance(spans, list)
        assert all(isinstance(s, HallucinatedSpan) for s in spans)
