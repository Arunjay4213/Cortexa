"""Stage 1: Hallucination detection.

Two detectors:
- LettuceDetector: GPU-based, uses fine-tuned ModernBERT token classifier
- EmbeddingDetector: CPU fallback, uses sentence-transformers cosine similarity
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from cama.text import split_sentences, extract_numbers
from cama.types import HallucinatedSpan, TokenScore

logger = logging.getLogger(__name__)


class Detector(ABC):
    """Base class for hallucination detectors."""

    @abstractmethod
    def detect(
        self,
        memories: list[str],
        question: str,
        answer: str,
    ) -> tuple[list[TokenScore], list[HallucinatedSpan]]:
        """Run detection and return per-token scores + merged hallucinated spans."""


class LettuceDetector(Detector):
    """Primary detector using LettuceDetect (fine-tuned ModernBERT).

    Requires: pip install cama-v2[gpu]
    """

    def __init__(
        self,
        model_name: str = "KRLabsOrg/lettucedect-base-modernbert-en-v1",
        threshold: float = 0.5,
    ):
        self.threshold = threshold
        try:
            from lettucedetect.models.inference import HallucinationDetector
        except ImportError:
            raise ImportError(
                "lettucedetect is required for GPU detection. "
                "Install with: pip install cama-v2[gpu]"
            )

        logger.info("Loading LettuceDetect model: %s", model_name)
        self._detector = HallucinationDetector(
            method="transformer",
            model_path=model_name,
        )

    def detect(
        self,
        memories: list[str],
        question: str,
        answer: str,
    ) -> tuple[list[TokenScore], list[HallucinatedSpan]]:
        # LettuceDetect expects contexts as list[str], question, answer
        predictions = self._detector.predict(
            context=memories,
            question=question,
            answer=answer,
            output_format="tokens",
        )

        # predictions is a list of dicts: {'token': str, 'pred': int, 'prob': float}
        # pred=0 → supported, pred=1 → hallucinated; prob = hallucination probability
        token_scores: list[TokenScore] = []
        for idx, pred in enumerate(predictions):
            token_scores.append(TokenScore(
                token=pred.get("token", ""),
                index=idx,
                hallucination_prob=pred.get("prob", 0.0),
            ))

        spans = self._merge_spans(token_scores, answer)
        return token_scores, spans

    def _merge_spans(
        self,
        token_scores: list[TokenScore],
        answer: str,
    ) -> list[HallucinatedSpan]:
        """Merge consecutive tokens above threshold into HallucinatedSpan objects."""
        spans: list[HallucinatedSpan] = []
        current_tokens: list[TokenScore] = []

        for ts in token_scores:
            if ts.hallucination_prob > self.threshold:
                current_tokens.append(ts)
            else:
                if current_tokens:
                    span = self._tokens_to_span(current_tokens, answer)
                    if span:
                        spans.append(span)
                    current_tokens = []

        if current_tokens:
            span = self._tokens_to_span(current_tokens, answer)
            if span:
                spans.append(span)

        return spans

    def _tokens_to_span(
        self,
        tokens: list[TokenScore],
        answer: str,
    ) -> HallucinatedSpan | None:
        """Convert a group of token scores to a HallucinatedSpan."""
        # Reconstruct span text from tokens
        span_text = ''.join(
            t.token.replace('Ġ', ' ').replace('▁', ' ')
            for t in tokens
        ).strip()

        if not span_text:
            return None

        avg_score = sum(t.hallucination_prob for t in tokens) / len(tokens)

        # Try to find in original answer
        start = answer.lower().find(span_text.lower())
        if start == -1:
            # Fallback: try first few words
            words = span_text.split()[:2]
            if words:
                search = words[0]
                start = answer.lower().find(search.lower())
            if start == -1:
                start = 0

        end = start + len(span_text)
        actual_text = answer[start:end] if end <= len(answer) else span_text

        return HallucinatedSpan(
            text=actual_text,
            start_char=start,
            end_char=end,
            score=avg_score,
            token_scores=tokens,
        )


class EmbeddingDetector(Detector):
    """CPU fallback detector using sentence-level embedding similarity.

    Requires: pip install cama-v2[cpu]
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        sim_threshold: float = 0.5,
        hallucination_threshold: float = 0.5,
    ):
        self.model_name = model_name
        self.sim_threshold = sim_threshold
        self.hallucination_threshold = hallucination_threshold

    def detect(
        self,
        memories: list[str],
        question: str,
        answer: str,
    ) -> tuple[list[TokenScore], list[HallucinatedSpan]]:
        from cama.embed import embed_texts, max_similarity

        # Split answer into sentences
        sentences = split_sentences(answer)
        if not sentences:
            return [], []

        # Embed sentences and memories
        sentence_texts = [s[0] for s in sentences]
        sent_embeddings = embed_texts(sentence_texts, self.model_name)
        mem_embeddings = embed_texts(memories, self.model_name) if memories else None

        # Compute similarity scores
        if mem_embeddings is not None and mem_embeddings.size > 0:
            max_sims = max_similarity(sent_embeddings, mem_embeddings)
        else:
            # No memories → everything is ungrounded
            import numpy as np
            max_sims = np.zeros(len(sentences), dtype=np.float32)

        # Numerical grounding check
        memory_numbers = set()
        for mem in memories:
            for _, val, _, _ in extract_numbers(mem):
                memory_numbers.add(val)

        # Build per-token scores (sentence-level granularity)
        all_token_scores: list[TokenScore] = []
        all_spans: list[HallucinatedSpan] = []
        token_idx = 0

        for i, (sent_text, start_char, end_char) in enumerate(sentences):
            sim = float(max_sims[i])
            base_score = max(0.0, min(1.0, 1.0 - sim))

            # Check for ungrounded numbers in this sentence
            sent_numbers = extract_numbers(sent_text)
            has_ungrounded_number = False
            for _, val, _, _ in sent_numbers:
                if val not in memory_numbers:
                    has_ungrounded_number = True
                    break

            if has_ungrounded_number:
                base_score = max(base_score, 0.7)

            # Create token scores (one per word as approximation)
            words = sent_text.split()
            span_tokens: list[TokenScore] = []
            for word in words:
                ts = TokenScore(
                    token=word,
                    index=token_idx,
                    hallucination_prob=base_score,
                )
                all_token_scores.append(ts)
                span_tokens.append(ts)
                token_idx += 1

            # Create span if above threshold
            if base_score > self.hallucination_threshold:
                all_spans.append(HallucinatedSpan(
                    text=sent_text,
                    start_char=start_char,
                    end_char=end_char,
                    score=base_score,
                    token_scores=span_tokens,
                ))

        return all_token_scores, all_spans


def get_detector(prefer_gpu: bool = True) -> Detector:
    """Auto-detect and return the best available detector."""
    if prefer_gpu:
        try:
            return LettuceDetector()
        except ImportError:
            logger.info("LettuceDetect not available, falling back to EmbeddingDetector")
    return EmbeddingDetector()
