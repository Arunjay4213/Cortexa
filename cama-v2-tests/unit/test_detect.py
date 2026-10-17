"""Hostile tests for cama/detect.py — REAL ML inference, not mocks.

Every test in this file uses the actual EmbeddingDetector with the loaded
all-MiniLM-L6-v2 model. If these pass, the detection pipeline works for real.
"""

from __future__ import annotations

import pytest

from cama.types import HallucinatedSpan, TokenScore


class TestEmbeddingDetectorObviousHallucination:
    """The detector MUST flag clear hallucinations."""

    def test_fabricated_number(self, embedding_detector):
        """Answer invents a number not in any memory."""
        memories = ["Widget Pro costs $49.99."]
        question = "How much does Widget Pro cost?"
        answer = "Widget Pro costs $199.99."

        token_scores, spans = embedding_detector.detect(memories, question, answer)
        assert len(token_scores) > 0
        # The fabricated price should trigger hallucination
        flagged = [ts for ts in token_scores if ts.hallucination_prob > 0.5]
        assert len(flagged) > 0, "Fabricated $199.99 should be flagged"

    def test_completely_fabricated_response(self, embedding_detector):
        """Answer has nothing to do with memories — should flag everything."""
        memories = [
            "Widget Pro costs $49.99.",
            "Return policy: 30 days.",
        ]
        question = "What is the return policy?"
        answer = "The moon is made of green cheese and elephants can fly."

        token_scores, spans = embedding_detector.detect(memories, question, answer)
        flagged_ratio = sum(1 for ts in token_scores if ts.hallucination_prob > 0.5) / max(len(token_scores), 1)
        assert flagged_ratio > 0.5, f"Complete fabrication should flag >50% of tokens, got {flagged_ratio:.1%}"

    def test_invented_claim_not_in_context(self, embedding_detector):
        """Response adds a claim not present in any memory."""
        memories = [
            "Standard shipping takes 5-7 business days.",
            "Express shipping takes 2 business days.",
        ]
        question = "What are the shipping options?"
        answer = "Standard shipping takes 5-7 days. Express takes 2 days. We also offer overnight drone delivery."

        token_scores, spans = embedding_detector.detect(memories, question, answer)
        # At least the drone delivery sentence should be flagged
        assert len(spans) >= 1, "Invented drone delivery should produce at least 1 span"


class TestEmbeddingDetectorFullySupported:
    """The detector should NOT flag responses fully grounded in memories."""

    def test_exact_paraphrase(self, embedding_detector):
        """Answer is a direct paraphrase of memory — minimal hallucination."""
        memories = ["Widget Pro costs $49.99 with free standard shipping on orders over $25."]
        question = "How much does Widget Pro cost?"
        answer = "Widget Pro costs $49.99."

        token_scores, spans = embedding_detector.detect(memories, question, answer)
        # All tokens should have LOW hallucination probability
        if token_scores:
            max_prob = max(ts.hallucination_prob for ts in token_scores)
            assert max_prob < 0.8, f"Exact paraphrase got max_prob={max_prob}"

    def test_verbatim_copy(self, embedding_detector):
        """Answer is verbatim from memory — should score very low."""
        memories = ["The early termination fee is $500."]
        question = "What is the termination fee?"
        answer = "The early termination fee is $500."

        token_scores, spans = embedding_detector.detect(memories, question, answer)
        if token_scores:
            avg_prob = sum(ts.hallucination_prob for ts in token_scores) / len(token_scores)
            assert avg_prob < 0.5, f"Verbatim copy should have low avg_prob, got {avg_prob:.3f}"


class TestEmbeddingDetectorPartialHallucination:
    """Some sentences supported, some hallucinated."""

    def test_mixed_response(self, embedding_detector):
        """First sentence grounded, second fabricated."""
        memories = ["Widget Pro costs $49.99."]
        question = "Tell me about Widget Pro."
        answer = "Widget Pro costs $49.99. It also comes with a lifetime warranty and free helicopter delivery."

        token_scores, spans = embedding_detector.detect(memories, question, answer)
        # Should have at least one span (the fabricated sentence)
        assert len(spans) >= 1
        # But not ALL tokens should be flagged (first sentence is grounded)
        flagged_ratio = sum(1 for ts in token_scores if ts.hallucination_prob > 0.5) / max(len(token_scores), 1)
        assert flagged_ratio < 1.0, "Not all tokens should be flagged in mixed response"


class TestEmbeddingDetectorNumericalGrounding:
    """The numerical gate should catch ungrounded numbers."""

    def test_wrong_price(self, embedding_detector):
        """Memory says $49.99, response says $99.99."""
        memories = ["Widget Pro costs $49.99."]
        question = "What is the price?"
        answer = "The price is $99.99."

        token_scores, spans = embedding_detector.detect(memories, question, answer)
        flagged = [ts for ts in token_scores if ts.hallucination_prob >= 0.7]
        assert len(flagged) > 0, "Ungrounded $99.99 should trigger numerical gate (prob >= 0.7)"

    def test_correct_price(self, embedding_detector):
        """Memory says $49.99, response says $49.99 — should NOT trigger numerical gate."""
        memories = ["Widget Pro costs $49.99."]
        question = "What is the price?"
        answer = "The price is $49.99."

        token_scores, spans = embedding_detector.detect(memories, question, answer)
        # All tokens should have prob < 0.7 (no ungrounded numbers)
        high_prob = [ts for ts in token_scores if ts.hallucination_prob >= 0.7]
        assert len(high_prob) == 0, f"Correct price flagged with prob >= 0.7: {[(t.token, t.hallucination_prob) for t in high_prob]}"


class TestEmbeddingDetectorEdgeCases:
    """Edge cases that shouldn't crash."""

    def test_empty_memories(self, embedding_detector):
        """No memories at all — everything is ungrounded."""
        token_scores, spans = embedding_detector.detect([], "q", "Some answer text.")
        assert len(token_scores) > 0
        # With no memories, similarity is 0 → prob should be high
        avg_prob = sum(ts.hallucination_prob for ts in token_scores) / len(token_scores)
        assert avg_prob > 0.5, "No memories should mean high hallucination prob"

    def test_empty_answer(self, embedding_detector):
        """Empty answer string — should return empty results."""
        token_scores, spans = embedding_detector.detect(
            ["some memory"], "question", ""
        )
        assert token_scores == []
        assert spans == []

    def test_empty_question(self, embedding_detector):
        """Empty question — should still work (detection is answer vs memories)."""
        token_scores, spans = embedding_detector.detect(
            ["Widget Pro costs $49.99."], "", "Widget Pro costs $49.99."
        )
        assert len(token_scores) > 0  # Doesn't crash

    def test_very_long_answer(self, embedding_detector):
        """Answer with 50+ sentences — should not crash or timeout."""
        memories = ["The product costs $10."]
        answer = " ".join(f"Sentence number {i} about various things." for i in range(50))
        token_scores, spans = embedding_detector.detect(memories, "q", answer)
        assert len(token_scores) > 0

    def test_single_word_answer(self, embedding_detector):
        """Single-word answer."""
        token_scores, spans = embedding_detector.detect(
            ["Yes, the product is available."], "Is it available?", "Yes."
        )
        assert len(token_scores) >= 1

    def test_unicode_content(self, embedding_detector):
        """Non-ASCII content — should not crash."""
        memories = ["Prix: 49,99 EUR pour le Widget Pro."]
        question = "Combien coute le Widget Pro?"
        answer = "Le Widget Pro coute 49,99 euros."
        token_scores, spans = embedding_detector.detect(memories, question, answer)
        assert isinstance(token_scores, list)

    def test_special_characters(self, embedding_detector):
        """HTML, SQL injection-like strings — should not crash."""
        memories = ["<script>alert('xss')</script>"]
        answer = "The answer is <b>bold</b> & 'quoted'."
        token_scores, spans = embedding_detector.detect(memories, "q", answer)
        assert isinstance(token_scores, list)


class TestEmbeddingDetectorDeterminism:
    """Same input should produce same output."""

    def test_deterministic_scores(self, embedding_detector):
        """Run the same detection twice — scores should be identical."""
        memories = ["Widget Pro costs $49.99."]
        question = "How much?"
        answer = "Widget Pro costs $49.99."

        scores1, spans1 = embedding_detector.detect(memories, question, answer)
        scores2, spans2 = embedding_detector.detect(memories, question, answer)

        assert len(scores1) == len(scores2)
        for s1, s2 in zip(scores1, scores2):
            assert abs(s1.hallucination_prob - s2.hallucination_prob) < 1e-6, \
                f"Non-deterministic: {s1.hallucination_prob} vs {s2.hallucination_prob}"


class TestEmbeddingDetectorOutputShape:
    """Validate the shape and types of detector output."""

    def test_token_scores_are_tokenscore_objects(self, embedding_detector):
        scores, spans = embedding_detector.detect(
            ["Some memory."], "q", "Some answer."
        )
        for ts in scores:
            assert isinstance(ts, TokenScore)
            assert isinstance(ts.token, str)
            assert isinstance(ts.index, int)
            assert isinstance(ts.hallucination_prob, float)
            assert ts.index >= 0

    def test_spans_are_hallucinatedspan_objects(self, embedding_detector):
        scores, spans = embedding_detector.detect(
            ["Memory content."], "q",
            "Completely fabricated claim about unicorns."
        )
        for span in spans:
            assert isinstance(span, HallucinatedSpan)
            assert isinstance(span.text, str)
            assert len(span.text) > 0
            assert span.start_char >= 0
            assert span.end_char > span.start_char
            assert 0.0 <= span.score <= 1.0
            assert len(span.token_scores) > 0

    def test_token_indices_are_sequential(self, embedding_detector):
        scores, _ = embedding_detector.detect(
            ["Memory."], "q", "A short answer."
        )
        indices = [ts.index for ts in scores]
        assert indices == list(range(len(indices)))

    def test_one_score_per_word(self, embedding_detector):
        """EmbeddingDetector creates one TokenScore per word."""
        answer = "Three word answer."
        scores, _ = embedding_detector.detect(["mem"], "q", answer)
        # split_sentences then splits words — "Three word answer." → 3 words
        # But only if it's one sentence (which it is)
        assert len(scores) == 3
