"""
DeBERTa-v3 NLI entailment scoring for CAMA.

Singleton model loading (loaded once, reused across requests).
Batch inference for efficiency — all (premise, hypothesis) pairs
are scored in a single forward pass.

Scoring formula: max(0, P(entailment) - P(contradiction))
Label indices read dynamically from model.config.label2id.
"""

from __future__ import annotations

import threading
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

_NLI_MODEL = "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli"

_lock = threading.Lock()


@lru_cache(maxsize=1)
def _load_nli_model(model_name: str = _NLI_MODEL):
    """Load NLI model and tokenizer (singleton via lru_cache).

    Thread-safe: uses a lock to prevent concurrent loading.
    Returns (model, tokenizer, device, entailment_idx, contradiction_idx).
    """
    with _lock:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        import torch

        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)
        model.eval()

        # Use MPS if available (Apple Silicon), else CPU
        if torch.backends.mps.is_available():
            device = torch.device("mps")
        elif torch.cuda.is_available():
            device = torch.device("cuda")
        else:
            device = torch.device("cpu")

        model = model.to(device)

        # Read label indices from model config — don't hardcode
        label2id = model.config.label2id
        # Normalize keys to lowercase for safe lookup
        label2id_lower = {k.lower(): v for k, v in label2id.items()}

        entailment_idx = label2id_lower.get("entailment", 2)
        contradiction_idx = label2id_lower.get("contradiction", 0)

        return model, tokenizer, device, entailment_idx, contradiction_idx


def batch_entailment(
    premises: list[str],
    hypotheses: list[str],
    model_name: str = _NLI_MODEL,
    batch_size: int = 32,
) -> list[float]:
    """Compute attribution score for each (premise, hypothesis) pair.

    Score = max(0, P(entailment) - P(contradiction))

    This penalizes contradicted claims even if they have moderate entailment,
    and separates truly supported claims from merely not-refuted ones.

    Args:
        premises: list of premise strings (memory content)
        hypotheses: list of hypothesis strings (claims)
        model_name: HuggingFace model name for NLI
        batch_size: batch size for inference

    Returns:
        List of attribution scores, one per pair
    """
    if not premises:
        return []

    assert len(premises) == len(hypotheses), (
        f"premises ({len(premises)}) and hypotheses ({len(hypotheses)}) must have same length"
    )

    import torch

    model, tokenizer, device, ent_idx, contra_idx = _load_nli_model(model_name)

    all_scores: list[float] = []

    for start in range(0, len(premises), batch_size):
        batch_premises = premises[start:start + batch_size]
        batch_hypotheses = hypotheses[start:start + batch_size]

        inputs = tokenizer(
            batch_premises,
            batch_hypotheses,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        ).to(device)

        with torch.no_grad():
            logits = model(**inputs).logits  # (batch, num_labels)

        probs = torch.softmax(logits, dim=-1)
        p_ent = probs[:, ent_idx].cpu().numpy()
        p_contra = probs[:, contra_idx].cpu().numpy()

        # Score = max(0, P(entailment) - P(contradiction))
        scores = np.maximum(0.0, p_ent - p_contra).tolist()
        all_scores.extend(scores)

    return all_scores


def score_claim_memory_pairs(
    claims: list[str],
    candidate_memories: list[list[str]],
    memory_contents: dict[str, str],
    model_name: str = _NLI_MODEL,
) -> tuple[list[dict[str, float]], int]:
    """Score all (claim, memory) pairs after the similarity gate.

    For each claim, we have a list of candidate memory IDs. We build
    all (memory_content, claim) pairs, run batch NLI, then reshape
    back to per-claim dicts.

    Args:
        claims: list of claim strings
        candidate_memories: candidates[i] = list of memory_ids for claim i
        memory_contents: memory_id → content text
        model_name: NLI model name

    Returns:
        (entailment_scores, num_nli_calls) where:
        - entailment_scores[i] = {memory_id: score} for claim i
        - num_nli_calls = total number of NLI inference pairs
    """
    # Flatten all (premise, hypothesis) pairs
    all_premises: list[str] = []
    all_hypotheses: list[str] = []
    pair_map: list[tuple[int, str]] = []  # (claim_index, memory_id)

    for claim_idx, mem_ids in enumerate(candidate_memories):
        for mem_id in mem_ids:
            content = memory_contents.get(mem_id, "")
            if content:
                all_premises.append(content)
                all_hypotheses.append(claims[claim_idx])
                pair_map.append((claim_idx, mem_id))

    num_nli_calls = len(all_premises)

    if num_nli_calls == 0:
        return [{} for _ in claims], 0

    # Batch inference
    scores = batch_entailment(all_premises, all_hypotheses, model_name=model_name)

    # Reshape back to per-claim dicts
    results: list[dict[str, float]] = [{} for _ in claims]
    for idx, (claim_idx, mem_id) in enumerate(pair_map):
        results[claim_idx][mem_id] = scores[idx]

    return results, num_nli_calls
