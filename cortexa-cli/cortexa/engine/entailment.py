"""NLI entailment scoring — Tier 3 of the CAMA pipeline.

Three backends (tried in order):
1. Local: DeBERTa-v3-base NLI model (transformers/ONNX). Lazy-loaded.
2. API: Claude Haiku when local model unavailable.
3. TF-IDF: Cosine similarity fallback — no API key, no model download.

Implements SummaC-style sentence-level scoring: for long memories, split into
sentences, compute entailment for each sentence vs. each claim, take MAX.
"""

import logging
import re

from cortexa.engine.exceptions import EntailmentError
from cortexa.engine.models import Claim, EntailmentScore, Memory

logger = logging.getLogger(__name__)

# Simple sentence splitter for SummaC
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

# Label mapping for cross-encoder/nli-deberta-v3-base
# id2label: 0=contradiction, 1=entailment, 2=neutral
_LABEL_ORDER = ["contradiction", "entailment", "neutral"]


def _split_memory_sentences(content: str) -> list[str]:
    """Split memory content into sentences for SummaC-style scoring."""
    sentences = _SENTENCE_RE.split(content)
    return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]


class LocalEntailmentBackend:
    """NLI scoring using a local DeBERTa model."""

    def __init__(self, model_name: str = "cross-encoder/nli-deberta-v3-base") -> None:
        self.model_name = model_name
        self._tokenizer = None
        self._model = None
        self._session = None  # ONNX session
        self._use_onnx = False

    def _load_model(self) -> None:
        """Lazy-load the model on first use."""
        if self._tokenizer is not None:
            return

        # Try ONNX first for speed
        try:
            from optimum.onnxruntime import ORTModelForSequenceClassification
            from transformers import AutoTokenizer

            logger.info("Loading NLI model with ONNX runtime: %s", self.model_name)
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = ORTModelForSequenceClassification.from_pretrained(
                self.model_name, export=True
            )
            self._use_onnx = True
            logger.info("ONNX model loaded successfully")
            return
        except ImportError:
            logger.debug("optimum not available, trying PyTorch")
        except Exception as e:
            logger.warning("ONNX load failed: %s, trying PyTorch", e)

        # Fall back to PyTorch
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            logger.info("Loading NLI model with PyTorch: %s", self.model_name)
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self._model.eval()
            logger.info("PyTorch model loaded successfully")
        except ImportError:
            raise EntailmentError(
                "Neither optimum nor transformers installed. "
                "Install with: pip install cortexa[nli]"
            )
        except Exception as e:
            raise EntailmentError(f"Failed to load NLI model: {e}")

    def score_pairs(
        self, pairs: list[tuple[str, str]]
    ) -> list[tuple[float, float, float]]:
        """Score a batch of (premise, hypothesis) pairs.

        Returns list of (contradiction, entailment, neutral) probabilities.
        """
        self._load_model()

        import numpy as np

        inputs = self._tokenizer(
            [p[0] for p in pairs],
            [p[1] for p in pairs],
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="np" if self._use_onnx else "pt",
        )

        # DeBERTa only takes input_ids + attention_mask (NO token_type_ids)
        model_inputs = {
            "input_ids": inputs["input_ids"],
            "attention_mask": inputs["attention_mask"],
        }

        if self._use_onnx:
            logits = self._model(**model_inputs).logits
            if not isinstance(logits, np.ndarray):
                logits = np.array(logits)
        else:
            import torch

            with torch.no_grad():
                model_inputs = {k: v for k, v in model_inputs.items()}
                logits = self._model(**model_inputs).logits.numpy()

        # Softmax
        exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)

        # Return as (contradiction, entailment, neutral) tuples
        return [(float(p[0]), float(p[1]), float(p[2])) for p in probs]


class ApiEntailmentBackend:
    """NLI scoring using Claude Haiku as fallback."""

    def score_pairs(
        self, pairs: list[tuple[str, str]]
    ) -> list[tuple[float, float, float]]:
        """Score (premise, hypothesis) pairs via Claude API."""
        try:
            import anthropic
        except ImportError:
            raise EntailmentError(
                "anthropic package not installed. Install with: pip install anthropic"
            )

        client = anthropic.Anthropic()
        results = []

        # Batch into a single API call for efficiency
        pairs_text = "\n".join(
            f"{i+1}. Premise: {p[0]}\n   Hypothesis: {p[1]}"
            for i, p in enumerate(pairs)
        )

        try:
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "For each premise-hypothesis pair, determine the NLI relationship. "
                            "Return ONLY a JSON array of objects with keys: "
                            '"entailment" (float 0-1), "contradiction" (float 0-1), '
                            '"neutral" (float 0-1). The three values must sum to 1.0.\n\n'
                            f"{pairs_text}"
                        ),
                    }
                ],
            )

            import json

            raw = message.content[0].text.strip()
            # Find JSON array
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                items = json.loads(match.group())
                for item in items:
                    e = float(item.get("entailment", 0.33))
                    c = float(item.get("contradiction", 0.33))
                    n = float(item.get("neutral", 0.34))
                    total = e + c + n
                    results.append((c / total, e / total, n / total))
            else:
                raise EntailmentError("API returned unparseable NLI response")

        except EntailmentError:
            raise
        except Exception as e:
            raise EntailmentError(f"API entailment failed: {e}") from e

        return results


class TfidfFallbackBackend:
    """TF-IDF cosine similarity — no API key, no model download.

    Uses scikit-learn TfidfVectorizer + cosine_similarity to compute
    text similarity, then maps to pseudo-entailment triples so the
    downstream attribution pipeline produces differentiated MAS scores.
    """

    def score_pairs(
        self, pairs: list[tuple[str, str]]
    ) -> list[tuple[float, float, float]]:
        """Score (premise, hypothesis) pairs using TF-IDF cosine similarity.

        Maps cosine sim → (contradiction, entailment, neutral):
          ent = sim, cont = 0.05, neut = remainder
        """
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
        except ImportError:
            raise EntailmentError(
                "scikit-learn not installed. Install with: pip install scikit-learn"
            )

        results = []
        for premise, hypothesis in pairs:
            try:
                vectorizer = TfidfVectorizer()
                tfidf = vectorizer.fit_transform([premise, hypothesis])
                sim = float(cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0])
            except ValueError:
                sim = 0.0

            # Clamp and map to pseudo-entailment triple
            sim = max(0.0, min(0.95, sim))
            ent = sim
            cont = 0.05
            neut = 1.0 - ent - cont
            results.append((cont, ent, neut))

        return results


class EntailmentScorer:
    """NLI entailment scorer with SummaC-style sentence-level aggregation.

    Falls back to TF-IDF cosine similarity when the primary backend fails.
    """

    def __init__(self, backend: str = "local", model_name: str | None = None) -> None:
        """Initialize entailment scorer.

        Args:
            backend: "local" for DeBERTa, "api" for Claude Haiku, "tfidf" for fallback.
            model_name: Override default model name (local backend only).
        """
        if backend == "local":
            name = model_name or "cross-encoder/nli-deberta-v3-base"
            self._backend = LocalEntailmentBackend(model_name=name)
        elif backend == "api":
            self._backend = ApiEntailmentBackend()
        elif backend == "tfidf":
            self._backend = TfidfFallbackBackend()
        else:
            raise ValueError(f"Unknown backend: {backend}. Use 'local', 'api', or 'tfidf'.")
        self._fallback = TfidfFallbackBackend()

    def score(self, memory: Memory, claim: Claim) -> EntailmentScore:
        """Score a single (memory, claim) pair with SummaC aggregation."""
        results = self.score_batch([claim], [memory])
        return results[0]

    def score_batch(
        self, claims: list[Claim], memories: list[Memory]
    ) -> list[EntailmentScore]:
        """Score all (memory, claim) pairs with SummaC-style aggregation.

        For each (memory, claim) pair:
        - Split memory into sentences
        - Score each sentence against the claim
        - Take MAX entailment across sentences (SummaC approach)
        """
        # Build all (sentence, claim) pairs
        pair_map: list[tuple[int, int, str, str]] = []  # (mem_idx, claim_idx, premise, hyp)

        for mi, memory in enumerate(memories):
            sentences = _split_memory_sentences(memory.content)
            if not sentences:
                sentences = [memory.content]

            for ci, claim in enumerate(claims):
                for sentence in sentences:
                    pair_map.append((mi, ci, sentence, claim.text))

        if not pair_map:
            return []

        # Batch score all pairs — fallback to TF-IDF if primary backend fails
        raw_pairs = [(p[2], p[3]) for p in pair_map]
        try:
            raw_scores = self._backend.score_pairs(raw_pairs)
        except Exception as e:
            logger.warning("Primary NLI backend failed: %s — using TF-IDF fallback", e)
            raw_scores = self._fallback.score_pairs(raw_pairs)

        # Aggregate: for each (memory, claim), take MAX entailment across sentences
        best: dict[tuple[int, int], tuple[float, float, float]] = {}

        for (mi, ci, _, _), (cont, ent, neut) in zip(pair_map, raw_scores):
            key = (mi, ci)
            if key not in best or ent > best[key][1]:
                best[key] = (cont, ent, neut)

        # Build EntailmentScore objects
        results = []
        for mi, memory in enumerate(memories):
            for ci, claim in enumerate(claims):
                key = (mi, ci)
                if key in best:
                    cont, ent, neut = best[key]
                else:
                    cont, ent, neut = 0.1, 0.1, 0.8

                probs = {"entailment": ent, "contradiction": cont, "neutral": neut}
                label = max(probs, key=probs.get)
                confidence = max(cont, ent, neut)

                results.append(
                    EntailmentScore(
                        memory_id=memory.id,
                        claim_id=claim.id,
                        entailment=ent,
                        contradiction=cont,
                        neutral=neut,
                        label=label,
                        confidence=confidence,
                    )
                )

        return results
