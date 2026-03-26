"""Stage 2: Memory attribution.

Two attributors:
- LOODetectorAttributor: Leave-one-out via detector (original method)
- NLICrossEncoderAttributor: Direct NLI scoring per (memory, span) pair
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from cama.detect import Detector
from cama.types import (
    HallucinatedSpan,
    Memory,
    MemoryAttribution,
    SpanAttribution,
    TokenScore,
)

logger = logging.getLogger(__name__)


class Attributor(ABC):
    """Base class for memory attribution."""

    @abstractmethod
    def attribute(
        self,
        memories: list[Memory],
        question: str,
        answer: str,
        baseline_scores: list[TokenScore],
        spans: list[HallucinatedSpan],
    ) -> list[SpanAttribution]:
        """Compute per-memory attribution for each hallucinated span."""


class LOODetectorAttributor(Attributor):
    """Leave-One-Out via Detector.

    For each memory m_i:
      1. Remove m_i from the context
      2. Re-run the detector on (remaining memories, question, answer)
      3. Compare hallucination scores with vs without m_i
      4. The delta tells us m_i's causal contribution

    delta > 0 → removing m_i INCREASED hallucination → m_i was supporting
    delta < 0 → removing m_i DECREASED hallucination → m_i was causing
    delta ≈ 0 → m_i is irrelevant (ghost candidate)
    """

    def __init__(self, detector: Detector, max_loo_memories: int = 20):
        self.detector = detector
        self.max_loo_memories = max_loo_memories

    def attribute(
        self,
        memories: list[Memory],
        question: str,
        answer: str,
        baseline_scores: list[TokenScore],
        spans: list[HallucinatedSpan],
    ) -> list[SpanAttribution]:
        if not spans or not memories:
            return []

        baseline_map = {ts.index: ts.hallucination_prob for ts in baseline_scores}

        # If too many memories, pre-filter to top candidates per span
        loo_memories = memories
        if len(memories) > self.max_loo_memories:
            loo_memories = self._prefilter_memories(memories, spans, answer)
            logger.info(
                "Pre-filtered %d → %d memories for LOO",
                len(memories), len(loo_memories),
            )

        # Compute ablated scores for each memory
        deltas: dict[str, dict[int, float]] = {}
        loo_ids = {m.id for m in loo_memories}

        for i, mem in enumerate(loo_memories):
            ablated_texts = [m.content for m in loo_memories if m.id != mem.id]
            # Also include memories not in LOO set
            ablated_texts += [m.content for m in memories if m.id not in loo_ids]

            ablated_scores, _ = self.detector.detect(ablated_texts, question, answer)
            ablated_map = {ts.index: ts.hallucination_prob for ts in ablated_scores}

            deltas[mem.id] = {}
            for idx in baseline_map:
                ablated_val = ablated_map.get(idx, baseline_map[idx])
                deltas[mem.id][idx] = ablated_val - baseline_map[idx]

        # For memories not in LOO set, assign zero deltas
        for mem in memories:
            if mem.id not in deltas:
                deltas[mem.id] = {idx: 0.0 for idx in baseline_map}

        # Aggregate per span
        results: list[SpanAttribution] = []
        for span in spans:
            span_token_indices = [ts.index for ts in span.token_scores]

            attributions: list[MemoryAttribution] = []
            for mem in memories:
                # Mean delta across span tokens
                span_deltas = [deltas[mem.id].get(idx, 0.0) for idx in span_token_indices]
                mean_delta = sum(span_deltas) / max(len(span_deltas), 1)

                # Classify direction
                if mean_delta > 0.02:
                    direction = "supporting"
                elif mean_delta < -0.02:
                    direction = "causing"
                else:
                    direction = "ghost"

                attributions.append(MemoryAttribution(
                    memory_id=mem.id,
                    mas=0.0,  # normalized below
                    delta=mean_delta,
                    direction=direction,
                ))

            # Normalize MAS
            total_abs = sum(abs(a.delta) for a in attributions) + 1e-8
            for a in attributions:
                a.mas = abs(a.delta) / total_abs

            # Sort by |delta| descending
            attributions.sort(key=lambda a: abs(a.delta), reverse=True)

            # Determine diagnosis
            culprit = None
            diagnosis = "supported"
            causing = [a for a in attributions if a.direction == "causing"]

            if causing:
                culprit = causing[0].memory_id
                # Check staleness
                culprit_mem = next((m for m in memories if m.id == culprit), None)
                if (
                    culprit_mem
                    and culprit_mem.source_updated_at
                    and culprit_mem.created_at
                    and culprit_mem.source_updated_at > culprit_mem.created_at
                ):
                    diagnosis = "stale_memory"
                else:
                    diagnosis = "wrong_memory"
            elif span.score > 0.7 and all(a.direction == "ghost" for a in attributions):
                diagnosis = "fabricated"

            results.append(SpanAttribution(
                span=span,
                attributions=attributions,
                diagnosis=diagnosis,
                culprit_memory_id=culprit,
            ))

        return results

    def _prefilter_memories(
        self,
        memories: list[Memory],
        spans: list[HallucinatedSpan],
        answer: str,
    ) -> list[Memory]:
        """Pre-filter to top-N most relevant memories using embedding similarity."""
        try:
            from cama.embed import embed_texts, cosine_similarity_matrix

            span_texts = [s.text for s in spans]
            mem_texts = [m.content for m in memories]

            span_emb = embed_texts(span_texts)
            mem_emb = embed_texts(mem_texts)
            sim = cosine_similarity_matrix(span_emb, mem_emb)

            # Union of top-K per span
            import numpy as np
            selected_indices: set[int] = set()
            for row in sim:
                top_k = np.argsort(row)[-self.max_loo_memories:]
                selected_indices.update(top_k.tolist())

            return [memories[i] for i in sorted(selected_indices)]
        except ImportError:
            # No sentence-transformers → just take first N
            return memories[:self.max_loo_memories]


class NLICrossEncoderAttributor(Attributor):
    """Two-stage memory attribution: bi-encoder recall + cross-encoder precision.

    Stage 1: Embed all memories and spans, select top-K memories per span by cosine similarity.
    Stage 2: Run NLI cross-encoder on top-K pairs, use RAW logits for ranking.

    This follows the standard retrieve-then-rerank pattern used in production IR systems.
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/nli-deberta-v3-xsmall",
        top_k: int = 10,
        culprit_contra_threshold: float = 0.0,  # Raw logit threshold (not probability)
        direction_threshold: float = 0.5,  # Raw logit difference for direction
    ):
        self.model_name = model_name
        self.top_k = top_k
        self.culprit_contra_threshold = culprit_contra_threshold
        self.direction_threshold = direction_threshold
        self._nli = None

    def _get_nli(self):
        if self._nli is None:
            from cama.nli import NLIModel
            self._nli = NLIModel(model_name=self.model_name)
        return self._nli

    def _select_top_k(
        self,
        memories: list[Memory],
        spans: list[HallucinatedSpan],
    ) -> dict[int, list[int]]:
        """Stage 1: Bi-encoder pre-filtering.

        For each span, select the top-K most similar memories by embedding cosine similarity.
        Returns {span_index: [memory_indices]}.
        """
        if len(memories) <= self.top_k:
            all_idx = list(range(len(memories)))
            return {si: all_idx for si in range(len(spans))}

        try:
            from cama.embed import embed_texts, cosine_similarity_matrix
            import numpy as np

            span_texts = [s.text for s in spans]
            mem_texts = [m.content for m in memories]

            span_emb = embed_texts(span_texts)
            mem_emb = embed_texts(mem_texts)
            sim = cosine_similarity_matrix(span_emb, mem_emb)

            result: dict[int, list[int]] = {}
            for si in range(len(spans)):
                top_idx = np.argsort(sim[si])[-self.top_k:][::-1].tolist()
                result[si] = top_idx

            logger.info(
                "Pre-filter: %d memories → top-%d per span (%d NLI pairs total, was %d)",
                len(memories), self.top_k,
                self.top_k * len(spans),
                len(memories) * len(spans),
            )
            return result

        except (ImportError, Exception) as e:
            logger.warning("Embedding pre-filter failed (%s), using all memories", e)
            all_idx = list(range(len(memories)))
            return {si: all_idx for si in range(len(spans))}

    def attribute(
        self,
        memories: list[Memory],
        question: str,
        answer: str,
        baseline_scores: list[TokenScore],
        spans: list[HallucinatedSpan],
    ) -> list[SpanAttribution]:
        if not spans or not memories:
            return []

        nli = self._get_nli()

        # Stage 1: Pre-filter to top-K per span
        span_top_k = self._select_top_k(memories, spans)

        # Stage 2: Build pairs for batch NLI (only top-K per span)
        pairs: list[tuple[str, str]] = []
        pair_index: list[tuple[int, int]] = []  # (span_idx, mem_idx)
        for si, span in enumerate(spans):
            for mi in span_top_k[si]:
                pairs.append((memories[mi].content, span.text))
                pair_index.append((si, mi))

        # Batch NLI inference — returns RAW logits
        all_scores = nli.predict_batch(pairs)

        # Organize scores
        score_map: dict[tuple[int, int], dict[str, float]] = {}
        for (si, mi), scores in zip(pair_index, all_scores):
            score_map[(si, mi)] = scores

        # Build attributions per span
        results: list[SpanAttribution] = []
        for si, span in enumerate(spans):
            attributions: list[MemoryAttribution] = []
            top_k_set = set(span_top_k[si])

            for mi, mem in enumerate(memories):
                if mi in top_k_set:
                    scores = score_map[(si, mi)]
                    raw_contra = scores["contradiction"]
                    raw_entail = scores["entailment"]
                    raw_neutral = scores["neutral"]

                    # Direction: neutral-dominant pairs are always ghost
                    if raw_neutral > max(raw_contra, raw_entail):
                        direction = "ghost"
                    else:
                        diff = raw_entail - raw_contra
                        if diff > self.direction_threshold:
                            direction = "supporting"
                        elif diff < -self.direction_threshold:
                            direction = "causing"
                        else:
                            direction = "ghost"

                    # MAS = max(entailment, contradiction) for display (normalized later)
                    relevance = max(raw_entail, raw_contra)

                    # Compute softmax neutral for ghost detection
                    import numpy as np
                    logits = np.array([raw_contra, raw_entail, raw_neutral])
                    probs = np.exp(logits - logits.max()) / np.exp(logits - logits.max()).sum()
                    neutral_prob = float(probs[2])

                else:
                    # Not in top-K: ghost by default
                    raw_contra = -10.0  # Very negative raw logit
                    raw_entail = -10.0
                    raw_neutral = 10.0  # High neutral
                    neutral_prob = 1.0
                    relevance = 0.0
                    direction = "ghost"

                attributions.append(MemoryAttribution(
                    memory_id=mem.id,
                    mas=relevance,  # Will normalize below for display
                    delta=raw_entail - raw_contra,  # Signed direction signal
                    direction=direction,
                    neutral_score=neutral_prob,
                    raw_contradiction=raw_contra,
                    raw_entailment=raw_entail,
                ))

            # Normalize MAS for display (sums to ~1 among top-K)
            top_k_ids = {memories[mi].id for mi in top_k_set}
            top_k_relevance = sum(
                a.mas for a in attributions if a.memory_id in top_k_ids
            )
            if top_k_relevance > 0:
                for a in attributions:
                    if a.mas > 0:
                        a.mas = a.mas / top_k_relevance

            # RANK by raw scores, NOT normalized MAS
            # Priority: causing (by raw_contradiction desc) > supporting (by raw_entailment desc) > ghost
            def _sort_key(a: MemoryAttribution) -> tuple:
                if a.direction == "causing":
                    return (2, a.raw_contradiction)
                elif a.direction == "supporting":
                    return (1, a.raw_entailment)
                return (0, 0.0)

            attributions.sort(key=_sort_key, reverse=True)

            # Determine culprit: highest raw contradiction score that's actually "causing"
            culprit = None
            diagnosis = "supported"

            causing = [
                a for a in attributions
                if a.direction == "causing" and a.raw_contradiction > self.culprit_contra_threshold
            ]

            if causing:
                culprit = causing[0].memory_id
                culprit_mem = next((m for m in memories if m.id == culprit), None)
                if (
                    culprit_mem and culprit_mem.source_updated_at
                    and culprit_mem.created_at
                    and culprit_mem.source_updated_at > culprit_mem.created_at
                ):
                    diagnosis = "stale_memory"
                else:
                    diagnosis = "wrong_memory"
            elif span.score > 0.7 and all(a.direction == "ghost" for a in attributions[:5]):
                diagnosis = "fabricated"

            results.append(SpanAttribution(
                span=span,
                attributions=attributions,
                diagnosis=diagnosis,
                culprit_memory_id=culprit,
            ))

        return results
