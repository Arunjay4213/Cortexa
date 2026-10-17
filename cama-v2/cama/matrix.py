"""NLIPairMatrix — SummaC-inspired direct NLI attribution for CAMAv3.

Builds an N×M×3 logit tensor (response_sentences × memories × [contra, entail, neutral]).
No hallucination detector needed — attribution is direct.
"""

from __future__ import annotations

import logging

import numpy as np

from cama.nli import NLIModel
from cama.text import split_sentences
from cama.types import (
    HallucinatedSpan,
    Memory,
    MemoryAttribution,
    SpanAttribution,
    TokenScore,
)

logger = logging.getLogger(__name__)


class NLIPairMatrix:
    """Build sentence×memory NLI matrix and produce SpanAttributions.

    Stage 1 (bi-encoder pre-filter): embed sentences and memories, select top-K
    per sentence by cosine similarity to reduce NLI pairs.
    Stage 2 (cross-encoder): run NLI on top-K pairs, build N×M×3 logit tensor.
    Stage 3 (attribution): classify direction, rank, find culprits.
    """

    def __init__(
        self,
        top_k: int = 10,
        model_name: str = "cross-encoder/nli-deberta-v3-xsmall",
        direction_threshold: float = 0.5,
        culprit_contra_threshold: float = 0.0,
    ):
        self.top_k = top_k
        self.model_name = model_name
        self.direction_threshold = direction_threshold
        self.culprit_contra_threshold = culprit_contra_threshold
        self.nli = NLIModel(model_name=model_name)

    def _prefilter(
        self,
        sentence_texts: list[str],
        mem_texts: list[str],
    ) -> dict[int, list[int]]:
        """Stage 1: bi-encoder pre-filter.

        Returns {sentence_idx: [memory_indices]} — top-K per sentence.
        """
        if len(mem_texts) <= self.top_k:
            all_idx = list(range(len(mem_texts)))
            return {si: all_idx for si in range(len(sentence_texts))}

        try:
            from cama.embed import cosine_similarity_matrix, embed_texts

            sent_emb = embed_texts(sentence_texts)
            mem_emb = embed_texts(mem_texts)
            sim = cosine_similarity_matrix(sent_emb, mem_emb)

            return {
                si: np.argsort(sim[si])[-self.top_k :][::-1].tolist()
                for si in range(len(sentence_texts))
            }
        except Exception as exc:
            logger.warning("Embedding pre-filter failed (%s), using all memories", exc)
            all_idx = list(range(len(mem_texts)))
            return {si: all_idx for si in range(len(sentence_texts))}

    def build(
        self,
        response: str,
        memories: list[Memory],
    ) -> dict:
        """Build NLI pair matrix and return span_attributions.

        Returns {"span_attributions": list[SpanAttribution]}.
        """
        sentence_tuples = split_sentences(response)
        if not sentence_tuples or not memories:
            return {"span_attributions": []}

        # Unpack — split_sentences returns list[tuple[str, int, int]]
        sentence_texts = [text for text, _, _ in sentence_tuples]
        mem_texts = [m.content for m in memories]

        # Stage 1: pre-filter
        span_top_k = self._prefilter(sentence_texts, mem_texts)

        # Stage 2: build NLI pairs (only top-K per sentence)
        pairs: list[tuple[str, str]] = []
        pair_index: list[tuple[int, int]] = []
        for si in range(len(sentence_texts)):
            for mi in span_top_k[si]:
                pairs.append((mem_texts[mi], sentence_texts[si]))
                pair_index.append((si, mi))

        all_scores = self.nli.predict_batch(pairs)

        # Map (sentence_idx, mem_idx) → raw logit scores
        score_map: dict[tuple[int, int], dict[str, float]] = {}
        for (si, mi), scores in zip(pair_index, all_scores):
            score_map[(si, mi)] = scores

        # Stage 3: build SpanAttributions
        span_attributions: list[SpanAttribution] = []
        for si, (sent_text, start_char, end_char) in enumerate(sentence_tuples):
            top_k_set = set(span_top_k[si])

            # Dummy span — v3 doesn't use a hallucination detector
            words = sent_text.split()
            dummy_token = TokenScore(
                token=words[0] if words else sent_text,
                index=si,
                hallucination_prob=0.0,
            )
            span = HallucinatedSpan(
                text=sent_text,
                start_char=start_char,
                end_char=end_char,
                score=0.0,
                token_scores=[dummy_token],
            )

            attributions: list[MemoryAttribution] = []
            for mi, mem in enumerate(memories):
                if mi in top_k_set:
                    scores = score_map[(si, mi)]
                    raw_contra = scores["contradiction"]
                    raw_entail = scores["entailment"]
                    raw_neutral = scores["neutral"]

                    # Direction: neutral-dominant → ghost
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

                    # Softmax neutral_prob for ghost score
                    logits = np.array([raw_contra, raw_entail, raw_neutral])
                    shifted = logits - logits.max()
                    probs = np.exp(shifted) / np.exp(shifted).sum()
                    neutral_prob = float(probs[2])
                    relevance = max(raw_entail, raw_contra)
                else:
                    # Not in top-K: treat as irrelevant ghost
                    raw_contra = -10.0
                    raw_entail = -10.0
                    raw_neutral = 10.0
                    neutral_prob = 1.0
                    relevance = 0.0
                    direction = "ghost"

                attributions.append(
                    MemoryAttribution(
                        memory_id=mem.id,
                        mas=relevance,
                        delta=raw_entail - raw_contra,
                        direction=direction,
                        neutral_score=neutral_prob,
                        raw_contradiction=raw_contra,
                        raw_entailment=raw_entail,
                    )
                )

            # Normalize MAS among top-K members
            top_k_ids = {memories[mi].id for mi in top_k_set}
            top_k_rel = sum(a.mas for a in attributions if a.memory_id in top_k_ids)
            if top_k_rel > 0:
                for a in attributions:
                    if a.mas > 0:
                        a.mas = a.mas / top_k_rel

            # Rank: causing (by raw_contradiction desc) > supporting > ghost
            def _sort_key(a: MemoryAttribution) -> tuple:
                if a.direction == "causing":
                    return (2, a.raw_contradiction)
                elif a.direction == "supporting":
                    return (1, a.raw_entailment)
                return (0, 0.0)

            attributions.sort(key=_sort_key, reverse=True)

            # Culprit determination
            culprit = None
            diagnosis = "supported"
            causing = [
                a
                for a in attributions
                if a.direction == "causing"
                and a.raw_contradiction > self.culprit_contra_threshold
            ]
            if causing:
                culprit = causing[0].memory_id
                diagnosis = "wrong_memory"
            elif all(a.direction == "ghost" for a in attributions[:5]):
                diagnosis = "fabricated"

            span_attributions.append(
                SpanAttribution(
                    span=span,
                    attributions=attributions,
                    diagnosis=diagnosis,
                    culprit_memory_id=culprit,
                )
            )

        logger.info(
            "NLIPairMatrix: %d sentences × %d memories → %d attributions",
            len(sentence_texts),
            len(memories),
            len(span_attributions),
        )
        return {"span_attributions": span_attributions}
