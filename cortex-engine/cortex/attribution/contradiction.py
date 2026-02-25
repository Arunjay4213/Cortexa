"""NLI-based contradiction detection engine.

Two-stage pipeline:
1. Candidate generation (fast): cosine similarity > threshold on embeddings
2. NLI classification (accurate): cross-encoder DeBERTa-v3-small (~140MB, CPU)
3. Bidirectional check (paper §4.1): both directions must exceed threshold

Eliminates false positives from embedding heuristics — "user prefers Python"
and "user prefers Rust" have HIGH embedding similarity but are contradictory.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.db.tables import contradictions, memories

if TYPE_CHECKING:
    pass


@lru_cache(maxsize=1)
def _load_nli_model():
    """Lazy-load the cross-encoder NLI model (~140MB, CPU, ~10ms/pair).

    Returns (model, label_names) where label_names[i] is the lowercase
    label for logit index i (read from model config, not hardcoded).
    """
    from sentence_transformers import CrossEncoder

    model = CrossEncoder("cross-encoder/nli-deberta-v3-small")
    # Read label names from the underlying model config
    try:
        id2label = model.model.config.id2label
        label_names = [id2label[i].lower() for i in range(len(id2label))]
    except Exception:
        # Fallback for cross-encoder/nli-deberta-v3-small:
        # 0=contradiction, 1=entailment, 2=neutral
        label_names = ["contradiction", "entailment", "neutral"]
    return model, label_names


def _find_candidate_pairs(
    embeddings: np.ndarray,
    threshold: float = 0.7,
) -> list[tuple[int, int]]:
    """Find candidate pairs via cosine similarity > threshold.

    Reduces O(n^2) NLI calls to O(n * g_bar) where g_bar is the average
    number of similar memories per memory.
    """
    if embeddings.shape[0] < 2:
        return []

    # Normalize embeddings
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    normed = embeddings / norms

    # Cosine similarity matrix
    sim_matrix = normed @ normed.T

    pairs: list[tuple[int, int]] = []
    n = embeddings.shape[0]
    for i in range(n):
        for j in range(i + 1, n):
            if sim_matrix[i, j] >= threshold:
                pairs.append((i, j))

    return pairs


def _classify_nli(text_a: str, text_b: str) -> dict[str, float]:
    """Run NLI classification on a text pair.

    Returns {entailment, neutral, contradiction} probabilities.
    Label indices read from model.config.id2label (not hardcoded).
    """
    model, label_names = _load_nli_model()
    scores = model.predict([(text_a, text_b)])

    probs = _softmax(scores[0])

    # Build dict using dynamically-read label names (already lowercase)
    return {label_names[i]: float(probs[i]) for i in range(len(label_names))}


def _softmax(x: np.ndarray) -> np.ndarray:
    """Numerically stable softmax."""
    e_x = np.exp(x - np.max(x))
    return e_x / e_x.sum()


def _classify_contradiction_type(
    mem_a_created: datetime | None,
    mem_b_created: datetime | None,
    mem_a_agent: str,
    mem_b_agent: str,
) -> str:
    """Classify the type of contradiction.

    - temporal_update: timestamps differ significantly (>24h)
    - concurrent_conflict: same agent, within 1 hour
    - logical: same timeframe, direct contradiction
    - ambiguous: cannot determine
    """
    if mem_a_created is None or mem_b_created is None:
        return "ambiguous"

    time_diff = abs((mem_a_created - mem_b_created).total_seconds())

    if time_diff > 86400:  # >24 hours
        return "temporal_update"

    if mem_a_agent == mem_b_agent and time_diff < 3600:  # same agent, <1h
        return "concurrent_conflict"

    if time_diff <= 86400:  # within 24 hours
        return "logical"

    return "ambiguous"


def classify_contradiction_with_probability(
    mem_a_created: datetime | None,
    mem_b_created: datetime | None,
    mem_a_agent: str,
    mem_b_agent: str,
    nli_confidence: float = 0.0,
) -> dict:
    """Enhanced contradiction classification with probability scores (§4.1).

    Returns dict with type, probability, temporal_marker, and metadata.
    Probability reflects confidence that this contradiction type is correct,
    accounting for temporal distance, agent context, and NLI confidence.
    """
    import math

    base_type = _classify_contradiction_type(
        mem_a_created, mem_b_created, mem_a_agent, mem_b_agent,
    )

    if mem_a_created is None or mem_b_created is None:
        return {
            "type": "ambiguous",
            "probability": 0.5,
            "temporal_marker": "unknown",
            "time_delta_hours": None,
            "is_superseded": False,
            "resolution_hint": "manual_review",
        }

    time_diff_s = abs((mem_a_created - mem_b_created).total_seconds())
    time_diff_h = time_diff_s / 3600.0
    newer = mem_a_created if mem_a_created > mem_b_created else mem_b_created

    # Temporal marker: how to interpret the time relationship
    if time_diff_h < 1:
        temporal_marker = "simultaneous"
    elif time_diff_h < 24:
        temporal_marker = "same_day"
    elif time_diff_h < 168:  # 7 days
        temporal_marker = "same_week"
    elif time_diff_h < 720:  # 30 days
        temporal_marker = "same_month"
    else:
        temporal_marker = "distant"

    # Probability scoring: sigmoid-based confidence
    # For temporal_update: confidence increases with time gap
    # For concurrent_conflict: confidence is high when same agent, close time
    # For logical: confidence from NLI score
    if base_type == "temporal_update":
        # P(temporal) = sigmoid(time_diff_days - 1) * nli_factor
        days = time_diff_s / 86400.0
        prob = 1.0 / (1.0 + math.exp(-(days - 1.0)))
        prob *= max(0.5, nli_confidence)
        is_superseded = True  # newer memory likely supersedes older
    elif base_type == "concurrent_conflict":
        # High confidence when same agent produces contradicting memories quickly
        hours = time_diff_s / 3600.0
        prob = (1.0 - hours) * 0.9  # decays with time within the hour
        prob = max(0.3, prob) * max(0.5, nli_confidence)
        is_superseded = False
    elif base_type == "logical":
        # Logical contradictions rely heavily on NLI confidence
        prob = nli_confidence * 0.95
        is_superseded = False
    else:
        prob = 0.5
        is_superseded = False

    # Resolution hint based on type
    if base_type == "temporal_update":
        resolution_hint = "keep_newer"
    elif base_type == "concurrent_conflict":
        resolution_hint = "merge_or_resolve"
    elif base_type == "logical":
        resolution_hint = "investigate"
    else:
        resolution_hint = "manual_review"

    return {
        "type": base_type,
        "probability": round(min(1.0, max(0.0, prob)), 4),
        "temporal_marker": temporal_marker,
        "time_delta_hours": round(time_diff_h, 2),
        "is_superseded": is_superseded,
        "newer_memory_created": newer.isoformat(),
        "resolution_hint": resolution_hint,
    }


async def detect_contradictions(
    db: AsyncSession,
    agent_id: str | None = None,
    sim_threshold: float = 0.7,
    nli_threshold: float = 0.7,
) -> list[dict]:
    """Run full contradiction detection pipeline.

    1. Fetch non-deleted memories
    2. Cosine similarity candidate generation
    3. Bidirectional NLI classification
    4. Filter by threshold
    """
    # Fetch memories
    q = select(memories).where(memories.c.deleted_at.is_(None))
    if agent_id:
        q = q.where(memories.c.agent_id == agent_id)
    q = q.order_by(memories.c.id)

    rows = (await db.execute(q)).all()
    if len(rows) < 2:
        return []

    # Build embedding matrix
    mem_with_embeddings = [(r, np.array(r.embedding)) for r in rows if r.embedding]
    if len(mem_with_embeddings) < 2:
        return []

    embeddings = np.array([e for _, e in mem_with_embeddings])
    mem_rows = [r for r, _ in mem_with_embeddings]

    # Stage 1: Candidate generation
    candidate_pairs = _find_candidate_pairs(embeddings, threshold=sim_threshold)

    # Stage 2 + 3: Bidirectional NLI classification
    detected: list[dict] = []
    for i, j in candidate_pairs:
        mem_a = mem_rows[i]
        mem_b = mem_rows[j]

        # Asymmetric bidirectional check (§4.1 refined).
        # Old rule: both directions must exceed threshold — too strict,
        # rejects temporal updates where A→B contradicts but B→A is neutral.
        # New rule:
        #   1) At least one direction strongly contradicts (>= threshold)
        #   2) Mean contradiction exceeds a lower bar (>= threshold * 0.7)
        #   3) Neither direction shows strong entailment (< 0.5) — that's
        #      subsumption/refinement, not contradiction
        nli_ab = _classify_nli(mem_a.content, mem_b.content)
        nli_ba = _classify_nli(mem_b.content, mem_a.content)

        max_contra = max(nli_ab["contradiction"], nli_ba["contradiction"])
        mean_contra = (nli_ab["contradiction"] + nli_ba["contradiction"]) / 2
        max_entail = max(nli_ab["entailment"], nli_ba["entailment"])

        if (max_contra >= nli_threshold
                and mean_contra >= nli_threshold * 0.7
                and max_entail < 0.5):
            confidence = mean_contra
            contra_type = _classify_contradiction_type(
                mem_a.created_at, mem_b.created_at,
                mem_a.agent_id, mem_b.agent_id,
            )

            detected.append({
                "memory_id_1": mem_a.id,
                "memory_id_2": mem_b.id,
                "type": contra_type,
                "confidence": confidence,
                "nli_scores_ab": nli_ab,
                "nli_scores_ba": nli_ba,
            })

    return detected


async def run_detection_batch(
    db: AsyncSession,
    agent_id: str | None = None,
    sim_threshold: float = 0.7,
    nli_threshold: float = 0.7,
) -> tuple[int, list[dict]]:
    """Run detection and store new contradictions. Returns (count, contradictions)."""
    detected = await detect_contradictions(db, agent_id, sim_threshold, nli_threshold)

    stored: list[dict] = []
    for c in detected:
        # Check if this pair already exists
        existing = (
            await db.execute(
                select(contradictions).where(
                    contradictions.c.memory_id_1 == c["memory_id_1"],
                    contradictions.c.memory_id_2 == c["memory_id_2"],
                )
            )
        ).first()

        if existing:
            continue

        # Also check reverse order
        existing_rev = (
            await db.execute(
                select(contradictions).where(
                    contradictions.c.memory_id_1 == c["memory_id_2"],
                    contradictions.c.memory_id_2 == c["memory_id_1"],
                )
            )
        ).first()

        if existing_rev:
            continue

        contra_id = str(uuid.uuid4())
        await db.execute(
            contradictions.insert().values(
                id=contra_id,
                memory_id_1=c["memory_id_1"],
                memory_id_2=c["memory_id_2"],
                type=c["type"],
                confidence=c["confidence"],
                detected_at=datetime.now(UTC),
                resolved=False,
            )
        )
        stored.append({
            "id": contra_id,
            "memory_id_1": c["memory_id_1"],
            "memory_id_2": c["memory_id_2"],
            "type": c["type"],
            "confidence": c["confidence"],
        })

    if stored:
        await db.commit()

    return len(stored), stored
