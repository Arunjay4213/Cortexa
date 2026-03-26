"""NLI model wrapper using sentence-transformers CrossEncoder.

Returns RAW logits [contradiction, entailment, neutral] — NOT softmax probabilities.
This preserves meaningful score differences across many memories.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

# Label indices for cross-encoder/nli-deberta-v3-xsmall
# Order: [contradiction, entailment, neutral]
LABEL_CONTRADICTION = 0
LABEL_ENTAILMENT = 1
LABEL_NEUTRAL = 2


class NLIModel:
    """Cross-encoder NLI model for memory attribution.

    Uses sentence-transformers CrossEncoder which returns raw logits,
    preserving meaningful score differences even with 50+ memories.
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/nli-deberta-v3-xsmall",
        device: str | None = None,
    ):
        self.model_name = model_name
        self._device = device
        self._model = None

    def _load(self):
        if self._model is not None:
            return

        from sentence_transformers import CrossEncoder

        device = self._device
        if device is None:
            import torch
            if torch.backends.mps.is_available():
                # MPS can be flaky with DeBERTa — use CPU for reliability
                device = "cpu"
            elif torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"

        logger.info("Loading NLI model %s on %s", self.model_name, device)
        self._model = CrossEncoder(
            self.model_name,
            device=device,
            max_length=512,
        )

    def predict(self, premise: str, hypothesis: str) -> dict[str, float]:
        """Score a single (premise, hypothesis) pair.

        Returns raw logits (NOT probabilities) as:
        {"contradiction": float, "entailment": float, "neutral": float}
        """
        self._load()
        scores = self._model.predict([(premise, hypothesis)])[0]
        return {
            "contradiction": float(scores[LABEL_CONTRADICTION]),
            "entailment": float(scores[LABEL_ENTAILMENT]),
            "neutral": float(scores[LABEL_NEUTRAL]),
        }

    def predict_batch(
        self,
        pairs: list[tuple[str, str]],
        batch_size: int = 64,
    ) -> list[dict[str, float]]:
        """Score multiple pairs efficiently with batched inference.

        Returns raw logits for each pair.
        """
        self._load()

        if not pairs:
            return []

        # CrossEncoder.predict handles batching internally
        all_scores = self._model.predict(
            pairs,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        # all_scores shape: (N, 3) — [contradiction, entailment, neutral] per pair
        results = []
        for scores in all_scores:
            results.append({
                "contradiction": float(scores[LABEL_CONTRADICTION]),
                "entailment": float(scores[LABEL_ENTAILMENT]),
                "neutral": float(scores[LABEL_NEUTRAL]),
            })
        return results

    def predict_batch_softmax(
        self,
        pairs: list[tuple[str, str]],
        batch_size: int = 64,
    ) -> list[dict[str, float]]:
        """Like predict_batch but returns softmax probabilities.

        Use this when you need calibrated probabilities (0-1).
        Use predict_batch when you need raw scores for ranking.
        """
        raw = self.predict_batch(pairs, batch_size)
        results = []
        for scores in raw:
            vals = np.array([scores["contradiction"], scores["entailment"], scores["neutral"]])
            probs = np.exp(vals - vals.max()) / np.exp(vals - vals.max()).sum()
            results.append({
                "contradiction": float(probs[0]),
                "entailment": float(probs[1]),
                "neutral": float(probs[2]),
            })
        return results

    def is_contradiction(
        self,
        text_a: str,
        text_b: str,
        threshold: float = 0.8,
    ) -> tuple[bool, float]:
        """Check if two texts contradict each other.

        Uses softmax probabilities for the threshold comparison.
        """
        probs = self.predict_batch_softmax([(text_a, text_b)])[0]
        contra_prob = probs["contradiction"]
        return contra_prob > threshold, contra_prob
