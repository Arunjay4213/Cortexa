"""Contamination Detector — Hallucination-in-Memory Defense.

Combines grounding scores with counterfactual analysis to identify
memories that are likely hallucinated, outdated, or actively harmful.

Three detection modes:

1. SCAN — batch assessment of all memories, ranked by contamination risk
2. GATE — check a single memory before it gets stored (write-path defense)
3. QUARANTINE — isolate suspect memories and measure system improvement

This is the defense against the hallucination contamination problem
identified in HaluMem (arxiv:2511.03506): hallucinations stored as
memories propagate errors to all future retrievals.

Pure computation engine — no DB, no IO.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np

from cortex.attribution.grounding import (
    MemoryForGrounding,
    TransactionForGrounding,
    GroundingWeights,
    GroundingResult,
    compute_grounding_scores,
)
from cortex.attribution.counterfactual import (
    MemoryRecord,
    TransactionRecord,
    ChangeSpec,
    run_counterfactual,
)
from cortex.attribution.eas import compute_eas
from cortex.attribution.coverage import _cosine_similarity_matrix


_nli_checked = False
_nli_available = False


def _try_nli_contradiction(text_a: str, text_b: str, threshold: float = 0.6) -> bool:
    """Try NLI contradiction detection. Returns True if contradiction found.

    Safe wrapper: returns False (not a contradiction) if NLI model is unavailable.
    Checks both directions — both must show contradiction signal for confidence.
    """
    global _nli_checked, _nli_available

    if _nli_checked and not _nli_available:
        return False

    try:
        from cortex.attribution.contradiction import _classify_nli
        _nli_checked = True
        _nli_available = True

        # Forward direction
        fwd = _classify_nli(text_a, text_b)
        if fwd["contradiction"] < threshold:
            return False

        # Reverse direction — both must agree
        rev = _classify_nli(text_b, text_a)
        return rev["contradiction"] >= threshold

    except Exception:
        _nli_checked = True
        _nli_available = False
        return False


# ── Dataclasses ──────────────────────────────────────────────────────

@dataclass
class ContaminationFlag:
    """A single contamination detection result."""
    memory_id: str
    risk_level: str           # "trusted" | "uncertain" | "suspect" | "contaminated"
    grounding_score: float    # overall grounding ∈ [0, 1]
    contamination_score: float  # 1 - grounding_score (higher = more likely contaminated)
    reasons: list[str]        # human-readable explanations
    recommended_action: str   # "keep" | "review" | "quarantine" | "remove"
    impact_if_removed: dict   # counterfactual impact summary


@dataclass
class ScanResult:
    """Result of a full contamination scan."""
    total_memories: int
    trusted: int
    uncertain: int
    suspect: int
    contaminated: int
    flags: list[ContaminationFlag]
    system_contamination_rate: float  # fraction of suspect + contaminated
    compute_time_ms: float


@dataclass
class GateResult:
    """Result of a write-path gate check on a new memory."""
    should_store: bool
    grounding_score: float
    risk_level: str
    reasons: list[str]
    contradicts_existing: list[str]  # IDs of contradicted memories
    redundant_with: list[str]        # IDs of near-duplicate memories


# ── Reason Generation ────────────────────────────────────────────────

def _generate_reasons(grounding: GroundingResult) -> list[str]:
    """Generate human-readable reasons for a grounding assessment."""
    reasons = []

    # Provenance
    if grounding.provenance_score < 0.3:
        reasons.append("No traceable source — origin unknown")
    elif grounding.provenance_score < 0.5:
        reasons.append(f"Weak provenance (source: {grounding.signals.get('source_type', 'unknown')})")

    # Corroboration
    if grounding.corroboration_score < 0.3:
        reasons.append("Contradicted by other memories")
    elif grounding.corroboration_score < 0.5:
        reasons.append("No corroborating evidence from other memories")

    # Empirical
    if grounding.signals.get("retrieval_count", 0) == 0:
        reasons.append("Never retrieved — unvalidated by use")
    elif grounding.empirical_score < 0.3:
        reasons.append("Retrieved but low attribution — possibly noise")

    # Counterfactual
    if grounding.counterfactual_score < 0.3:
        reasons.append("Removing this memory improves system quality")
    elif grounding.counterfactual_score < 0.5:
        reasons.append("Minimal positive impact on transaction quality")

    if not reasons:
        reasons.append("All signals positive — memory appears well-grounded")

    return reasons


def _recommend_action(grounding: GroundingResult) -> str:
    """Determine recommended action based on grounding assessment."""
    if grounding.risk_level == "contaminated":
        return "remove"
    elif grounding.risk_level == "suspect":
        return "quarantine"
    elif grounding.risk_level == "uncertain":
        return "review"
    else:
        return "keep"


# ── SCAN: Batch Assessment ───────────────────────────────────────────

def scan_contamination(
    memories: list[MemoryForGrounding],
    transactions: list[TransactionForGrounding],
    contradiction_pairs: set[tuple[str, str]] | None = None,
    grounding_weights: GroundingWeights | None = None,
) -> ScanResult:
    """Scan all memories for contamination risk.

    Computes grounding scores and generates contamination flags
    with recommended actions. Returns results sorted by risk
    (most contaminated first).

    Args:
        memories: All active memories
        transactions: Recent transactions for empirical signals
        contradiction_pairs: Known contradiction pairs
        grounding_weights: Weights for grounding components

    Returns:
        ScanResult with per-memory contamination flags
    """
    t0 = time.perf_counter()

    # Compute grounding scores
    grounding_results = compute_grounding_scores(
        memories, transactions, contradiction_pairs, grounding_weights,
    )

    # Build flags
    flags: list[ContaminationFlag] = []
    counts = {"trusted": 0, "uncertain": 0, "suspect": 0, "contaminated": 0}

    for gr in grounding_results:
        reasons = _generate_reasons(gr)
        action = _recommend_action(gr)

        counts[gr.risk_level] = counts.get(gr.risk_level, 0) + 1

        flags.append(ContaminationFlag(
            memory_id=gr.memory_id,
            risk_level=gr.risk_level,
            grounding_score=gr.grounding_score,
            contamination_score=round(1.0 - gr.grounding_score, 4),
            reasons=reasons,
            recommended_action=action,
            impact_if_removed={
                "provenance": gr.provenance_score,
                "corroboration": gr.corroboration_score,
                "empirical": gr.empirical_score,
                "counterfactual": gr.counterfactual_score,
            },
        ))

    total = len(memories)
    contamination_rate = (counts["suspect"] + counts["contaminated"]) / total if total > 0 else 0.0

    elapsed_ms = (time.perf_counter() - t0) * 1000

    return ScanResult(
        total_memories=total,
        trusted=counts["trusted"],
        uncertain=counts["uncertain"],
        suspect=counts["suspect"],
        contaminated=counts["contaminated"],
        flags=flags,
        system_contamination_rate=round(contamination_rate, 4),
        compute_time_ms=round(elapsed_ms, 2),
    )


# ── GATE: Write-Path Defense ─────────────────────────────────────────

def gate_memory(
    candidate: MemoryForGrounding,
    existing_memories: list[MemoryForGrounding],
    recent_transactions: list[TransactionForGrounding],
    sim_threshold: float = 0.85,
    contradiction_threshold: float = 0.7,
) -> GateResult:
    """Check a candidate memory before storage.

    Write-path defense: called before inserting a new memory to detect:
    1. Is it redundant with existing memories? (near-duplicate)
    2. Does it contradict existing memories? (conflict)
    3. Does it have reasonable grounding? (not hallucinated)

    Args:
        candidate: The memory to check
        existing_memories: Current active memories
        recent_transactions: Recent transactions for context
        sim_threshold: Cosine similarity threshold for redundancy
        contradiction_threshold: Embedding similarity threshold for contradiction check

    Returns:
        GateResult with storage recommendation
    """
    redundant_with: list[str] = []
    contradicts_existing: list[str] = []

    if existing_memories:
        # Check for near-duplicates
        existing_embs = np.array([m.embedding for m in existing_memories])
        cand_emb = candidate.embedding.reshape(1, -1)
        sims = _cosine_similarity_matrix(cand_emb, existing_embs)[0]

        for i, sim in enumerate(sims):
            if sim >= sim_threshold:
                redundant_with.append(existing_memories[i].id)

        # Check for contradictions (high similarity — potential conflict)
        # Use NLI when available for accurate detection, fall back to heuristic
        for i, sim in enumerate(sims):
            if sim >= contradiction_threshold and sim < sim_threshold:
                # High similarity but not duplicate — possible contradiction
                if _try_nli_contradiction(candidate.content, existing_memories[i].content):
                    contradicts_existing.append(existing_memories[i].id)
                else:
                    # NLI didn't fire (unavailable or not a contradiction) —
                    # fall back to content divergence heuristic
                    from cortex.attribution.statement import _token_overlap_score
                    overlap = _token_overlap_score(
                        candidate.content, existing_memories[i].content,
                    )
                    if overlap < 0.3:  # tightened from 0.5 — divergent content is suspicious
                        contradicts_existing.append(existing_memories[i].id)

    # Build contradiction pairs set from detected contradictions
    # so the grounding scorer knows about them
    detected_contradictions: set[tuple[str, str]] | None = None
    if contradicts_existing:
        detected_contradictions = set()
        for cid in contradicts_existing:
            pair = (min(candidate.id, cid), max(candidate.id, cid))
            detected_contradictions.add(pair)

    # Compute grounding for the candidate in context of existing memories
    all_mems = existing_memories + [candidate]
    grounding_results = compute_grounding_scores(
        all_mems, recent_transactions, detected_contradictions,
    )

    # Find the candidate's result
    candidate_grounding = next(
        (gr for gr in grounding_results if gr.memory_id == candidate.id),
        None,
    )

    if candidate_grounding is None:
        return GateResult(
            should_store=True,
            grounding_score=0.5,
            risk_level="uncertain",
            reasons=["Could not compute grounding"],
            contradicts_existing=contradicts_existing,
            redundant_with=redundant_with,
        )

    reasons = _generate_reasons(candidate_grounding)

    # Decision: should we store?
    # A memory that contradicts existing knowledge must clear a HIGHER bar.
    # Without contradictions: blocked only if contaminated (< 0.3).
    # With contradictions: blocked unless grounding is strong (>= 0.65).
    should_store = True
    if candidate_grounding.risk_level == "contaminated":
        should_store = False
        reasons.insert(0, "BLOCKED: Memory appears contaminated")
    elif redundant_with:
        should_store = False
        reasons.insert(0, f"BLOCKED: Redundant with {len(redundant_with)} existing memories")
    elif contradicts_existing and candidate_grounding.grounding_score < 0.65:
        should_store = False
        reasons.insert(
            0,
            "BLOCKED: Contradicts existing memories without strong grounding "
            f"({candidate_grounding.grounding_score:.2f} < 0.65)",
        )

    return GateResult(
        should_store=should_store,
        grounding_score=candidate_grounding.grounding_score,
        risk_level=candidate_grounding.risk_level,
        reasons=reasons,
        contradicts_existing=contradicts_existing,
        redundant_with=redundant_with,
    )


# ── QUARANTINE: Isolate and Measure ──────────────────────────────────

def simulate_quarantine(
    suspect_ids: list[str],
    all_memories: list[MemoryForGrounding],
    transactions: list[TransactionForGrounding],
) -> dict:
    """Simulate quarantining suspect memories and measure system improvement.

    Runs counterfactual analysis: what happens if we remove all suspect
    memories at once? Reports impact on attribution quality, coverage,
    and contradiction rate.

    Args:
        suspect_ids: Memory IDs to quarantine
        all_memories: All active memories
        transactions: Recent transactions

    Returns:
        dict with before/after metrics and improvement scores
    """
    t0 = time.perf_counter()

    if not suspect_ids or not transactions:
        return {
            "quarantined_count": len(suspect_ids),
            "improvement": 0.0,
            "details": "No memories or transactions to evaluate",
            "compute_time_ms": 0.0,
        }

    # Convert to counterfactual types
    cf_memories = [
        MemoryRecord(
            id=m.id, content=m.content, embedding=m.embedding,
            tokens=m.tokens, retrieval_count=m.retrieval_count,
            total_attribution=m.total_attribution,
        )
        for m in all_memories
    ]
    cf_transactions = [
        TransactionRecord(
            id=t.id, query_text=t.query_text,
            query_embedding=t.query_embedding,
            response_embedding=t.response_embedding,
            retrieved_memory_ids=t.retrieved_memory_ids,
        )
        for t in transactions
    ]

    # Build removal changes for all suspect memories
    changes = [
        ChangeSpec(action="remove", memory_id=mid)
        for mid in suspect_ids
    ]

    result = run_counterfactual(
        current_memories=cf_memories,
        changes=changes,
        transactions=cf_transactions,
        include_analysis={"attribution", "coverage", "chi"},
    )

    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Interpret: positive CHI delta = quarantine improved health
    chi_improvement = 0.0
    if result.get("chi"):
        chi_improvement = result["chi"]["delta"]

    coverage_change = 0
    if result.get("coverage"):
        coverage_change = result["coverage"]["gap_change"]

    return {
        "quarantined_count": len(suspect_ids),
        "chi_before": result["chi"]["before"] if result.get("chi") else None,
        "chi_after": result["chi"]["after"] if result.get("chi") else None,
        "chi_improvement": round(chi_improvement, 4),
        "health_improved": chi_improvement > 0,
        "coverage_gap_change": coverage_change,
        "transactions_affected": result["summary"]["transactions_affected"],
        "avg_score_delta": result["summary"]["avg_score_delta"],
        "recommendation": (
            "Quarantine recommended — system health improves"
            if chi_improvement > 0
            else "Quarantine not recommended — system health degrades"
        ),
        "compute_time_ms": round(elapsed_ms, 2),
    }
