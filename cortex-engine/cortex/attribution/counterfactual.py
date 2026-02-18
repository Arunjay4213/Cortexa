"""Counterfactual Memory Staging — "git diff" for memory management.

Before any memory change hits production, simulate its impact across
recent transactions in <1s. Re-runs compute_eas() with modified memory
sets against stored transaction embeddings — zero LLM calls needed.

Pure computation engine — no DB, no IO. Accepts arrays, returns dicts.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np

from cortex.attribution.eas import compute_eas
from cortex.attribution.contradiction import (
    _find_candidate_pairs,
    classify_contradiction_with_probability,
)

# Lazy import NLI to avoid loading heavy torch models at import time
_nli_available: bool | None = None


def _check_nli_available() -> bool:
    """Pre-check whether the NLI model can be loaded safely."""
    global _nli_available
    if _nli_available is not None:
        return _nli_available
    try:
        import importlib
        importlib.import_module("sentence_transformers")
        # Model import is possible — but we still need to catch
        # load-time crashes (torchvision etc.)
        _nli_available = True
        return True
    except Exception:
        _nli_available = False
        return False


def _try_classify_nli(text_a: str, text_b: str) -> dict[str, float] | None:
    """Attempt NLI classification, return None if model unavailable."""
    global _nli_available
    if _nli_available is False:
        return None
    try:
        from cortex.attribution.contradiction import _classify_nli
        result = _classify_nli(text_a, text_b)
        _nli_available = True
        return result
    except Exception:
        _nli_available = False
        return None
from cortex.attribution.coverage import _cosine_similarity_matrix
from cortex.metrics.health import compute_chi, CHIWeights, batch_staleness
from cortex.metrics.calculator import token_waste_rate, memory_pnl
from cortex.metrics.financial import compute_portfolio_roi
from cortex.models import TokenCostConfig


# ── Dataclasses ──────────────────────────────────────────────────────

@dataclass
class MemoryRecord:
    """Lightweight memory representation for counterfactual computation."""
    id: str
    content: str
    embedding: np.ndarray
    tokens: int
    tier: str = "warm"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_accessed: datetime | None = None
    agent_id: str = "default"
    retrieval_count: int = 0
    total_attribution: float = 0.0


@dataclass
class TransactionRecord:
    """Lightweight transaction representation for counterfactual computation."""
    id: str
    query_text: str
    query_embedding: np.ndarray
    response_embedding: np.ndarray
    retrieved_memory_ids: list[str]
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ChangeSpec:
    """A single proposed memory change."""
    action: str  # "add" | "remove" | "edit"
    memory_id: str | None = None    # required for remove/edit
    content: str | None = None      # required for add/edit
    embedding: np.ndarray | None = None  # required for add/edit
    tokens: int | None = None       # optional


# ── Core Pipeline ────────────────────────────────────────────────────

def build_counterfactual_memory_set(
    current_memories: list[MemoryRecord],
    changes: list[ChangeSpec],
) -> tuple[dict[str, MemoryRecord], dict[str, MemoryRecord]]:
    """Clone current memories and apply add/remove/edit changes.

    Returns (before_dict, after_dict) where both map memory_id -> MemoryRecord.
    """
    before_dict = {m.id: m for m in current_memories}

    # Deep copy so mutations don't affect the original
    after_dict: dict[str, MemoryRecord] = {}
    for m in current_memories:
        after_dict[m.id] = MemoryRecord(
            id=m.id,
            content=m.content,
            embedding=m.embedding.copy(),
            tokens=m.tokens,
            tier=m.tier,
            created_at=m.created_at,
            last_accessed=m.last_accessed,
            agent_id=m.agent_id,
            retrieval_count=m.retrieval_count,
            total_attribution=m.total_attribution,
        )

    add_counter = 0
    for change in changes:
        if change.action == "remove":
            if change.memory_id and change.memory_id in after_dict:
                del after_dict[change.memory_id]

        elif change.action == "edit":
            if change.memory_id and change.memory_id in after_dict:
                mem = after_dict[change.memory_id]
                if change.content is not None:
                    mem.content = change.content
                if change.embedding is not None:
                    mem.embedding = change.embedding.copy()
                if change.tokens is not None:
                    mem.tokens = change.tokens

        elif change.action == "add":
            add_counter += 1
            new_id = change.memory_id or f"staged-{add_counter}"
            # Estimate tokens if not provided.  chars/4 matches OpenAI's
            # recommended heuristic and works across prose and code.
            tokens = change.tokens or (len(change.content) // 4 if change.content else 0)
            after_dict[new_id] = MemoryRecord(
                id=new_id,
                content=change.content or "",
                embedding=change.embedding.copy() if change.embedding is not None else np.zeros(1),
                tokens=tokens,
                agent_id=current_memories[0].agent_id if current_memories else "default",
            )

    return before_dict, after_dict


def _compute_attribution_for_set(
    memory_dict: dict[str, MemoryRecord],
    transaction: TransactionRecord,
    sim_threshold: float = 0.7,
) -> dict[str, float]:
    """Compute EAS scores for a transaction against a memory set.

    For the "before" state, uses only the originally retrieved memories.
    For the "after" state, includes any new/edited memories that rank
    highly enough (cosine sim with query > threshold relative to original set).
    """
    # Determine which memories to include in this transaction's retrieval set
    retrieved_ids = [
        mid for mid in transaction.retrieved_memory_ids
        if mid in memory_dict
    ]

    # Check if any new memories (not in original retrieved set) should be included
    all_ids = list(memory_dict.keys())
    new_ids = [mid for mid in all_ids if mid not in transaction.retrieved_memory_ids]

    if new_ids:
        # Compute cosine similarity between new memories and query
        new_embs = np.array([memory_dict[mid].embedding for mid in new_ids])
        q = np.asarray(transaction.query_embedding, dtype=np.float64)

        # Normalize
        norms = np.linalg.norm(new_embs, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        new_embs_norm = new_embs / norms

        q_norm = q / max(np.linalg.norm(q), 1e-10)
        sims = new_embs_norm @ q_norm

        # Include new memories that have reasonable similarity
        # Use a relative threshold: include if sim is above coverage_threshold
        for i, mid in enumerate(new_ids):
            if sims[i] >= sim_threshold * 0.5:  # more permissive for counterfactual
                retrieved_ids.append(mid)

    if not retrieved_ids:
        return {}

    # Build embedding matrix for retrieved memories
    mem_embs = np.array([memory_dict[mid].embedding for mid in retrieved_ids])
    eas_result = compute_eas(
        mem_embs,
        transaction.query_embedding,
        transaction.response_embedding,
    )

    scores = eas_result["scores"]
    return {retrieved_ids[i]: float(scores[i]) for i in range(len(retrieved_ids))}


def _compute_contradiction_delta(
    before_dict: dict[str, MemoryRecord],
    after_dict: dict[str, MemoryRecord],
    existing_contradictions: list[tuple[str, str, float]] | None,
    sim_threshold: float,
    use_nli: bool = True,
    nli_threshold: float = 0.7,
) -> dict:
    """Compute new/resolved contradictions between before and after states.

    When use_nli=True, runs bidirectional NLI on candidate pairs from the
    CHANGED portion of the memory set (new + edited memories only) to avoid
    false positives. Unchanged pairs are inherited from existing_contradictions.
    """
    after_ids = list(after_dict.keys())
    if len(after_ids) < 2:
        return {
            "new_contradictions": [],
            "resolved_contradictions": [],
            "net_change": 0,
        }

    # Identify which memory IDs are new or edited vs. the before set
    changed_ids = set()
    for mid in after_dict:
        if mid not in before_dict:
            changed_ids.add(mid)  # new memory
        elif not np.array_equal(after_dict[mid].embedding, before_dict[mid].embedding):
            changed_ids.add(mid)  # edited embedding
        elif after_dict[mid].content != before_dict[mid].content:
            changed_ids.add(mid)  # edited content

    # Build embedding matrix and find candidate pairs
    after_embs = np.array([after_dict[mid].embedding for mid in after_ids])
    candidate_pairs = _find_candidate_pairs(after_embs, threshold=sim_threshold)

    # Only NLI-classify pairs that involve at least one changed memory
    after_contradictions = []
    for i, j in candidate_pairs:
        ma = after_dict[after_ids[i]]
        mb = after_dict[after_ids[j]]

        pair_involves_change = (ma.id in changed_ids) or (mb.id in changed_ids)
        if not pair_involves_change:
            continue  # unchanged pair — use existing_contradictions

        if use_nli and ma.content and mb.content:
            # Asymmetric bidirectional NLI (matches detect_contradictions logic)
            nli_ab = _try_classify_nli(ma.content, mb.content)
            nli_ba = _try_classify_nli(mb.content, ma.content)
            if nli_ab is not None and nli_ba is not None:
                max_contra = max(nli_ab["contradiction"], nli_ba["contradiction"])
                mean_contra = (nli_ab["contradiction"] + nli_ba["contradiction"]) / 2
                max_entail = max(nli_ab["entailment"], nli_ba["entailment"])
                if (max_contra >= nli_threshold
                        and mean_contra >= nli_threshold * 0.7
                        and max_entail < 0.5):
                    confidence = mean_contra
                else:
                    continue  # NLI says not a contradiction
            else:
                confidence = 0.0
        else:
            confidence = 0.0

        if confidence > 0:
            result = classify_contradiction_with_probability(
                ma.created_at, mb.created_at,
                ma.agent_id, mb.agent_id,
                nli_confidence=confidence,
            )
            after_contradictions.append({
                "memory_id_1": ma.id,
                "memory_id_2": mb.id,
                "type": result["type"],
                "probability": result["probability"],
                "nli_confidence": round(confidence, 4),
            })

    # Diff against existing
    existing_set = set()
    if existing_contradictions:
        for m1, m2, conf in existing_contradictions:
            existing_set.add((min(m1, m2), max(m1, m2)))

    after_set = set()
    # Carry forward existing contradictions ONLY for unchanged pairs.
    # If either memory was changed (edited/added), the contradiction was
    # already re-checked by NLI above — don't blindly carry it forward.
    for m1, m2, conf in (existing_contradictions or []):
        if m1 in after_dict and m2 in after_dict:
            if m1 not in changed_ids and m2 not in changed_ids:
                after_set.add((min(m1, m2), max(m1, m2)))

    # Add newly detected contradictions
    for c in after_contradictions:
        pair = (min(c["memory_id_1"], c["memory_id_2"]),
                max(c["memory_id_1"], c["memory_id_2"]))
        after_set.add(pair)

    new_pairs = after_set - existing_set
    resolved_pairs = existing_set - after_set

    new_contradictions = [
        c for c in after_contradictions
        if (min(c["memory_id_1"], c["memory_id_2"]),
            max(c["memory_id_1"], c["memory_id_2"])) in new_pairs
    ]
    resolved_contradictions = [
        {"memory_id_1": p[0], "memory_id_2": p[1]}
        for p in resolved_pairs
    ]

    return {
        "new_contradictions": new_contradictions,
        "resolved_contradictions": resolved_contradictions,
        "net_change": len(new_contradictions) - len(resolved_contradictions),
    }


def _compute_coverage_delta(
    before_dict: dict[str, MemoryRecord],
    after_dict: dict[str, MemoryRecord],
    transactions: list[TransactionRecord],
    coverage_threshold: float,
) -> dict:
    """Compute coverage gap changes between before and after memory sets."""
    if not transactions:
        return {"gaps_before": 0, "gaps_after": 0, "gap_change": 0}

    query_embs = np.array([t.query_embedding for t in transactions])

    def _count_gaps(mem_dict: dict[str, MemoryRecord]) -> int:
        if not mem_dict:
            return len(transactions)
        mem_embs = np.array([m.embedding for m in mem_dict.values()])
        sim_matrix = _cosine_similarity_matrix(query_embs, mem_embs)
        max_sims = sim_matrix.max(axis=1)
        return int((max_sims < coverage_threshold).sum())

    gaps_before = _count_gaps(before_dict)
    gaps_after = _count_gaps(after_dict)

    return {
        "gaps_before": gaps_before,
        "gaps_after": gaps_after,
        "gap_change": gaps_after - gaps_before,
    }


def _compute_chi_delta(
    before_dict: dict[str, MemoryRecord],
    after_dict: dict[str, MemoryRecord],
    before_scores: list[dict[str, float]],
    after_scores: list[dict[str, float]],
    transactions: list[TransactionRecord],
    coverage_threshold: float,
) -> dict:
    """Compute CHI delta between before and after states."""
    def _chi_for_state(
        mem_dict: dict[str, MemoryRecord],
        score_list: list[dict[str, float]],
    ) -> float:
        # Accuracy: mean attribution score
        all_scores = [s for scores in score_list for s in scores.values()]
        accuracy = float(np.mean(all_scores)) if all_scores else 0.5

        # Freshness: 1 - mean staleness
        last_accessed = [m.last_accessed for m in mem_dict.values()]
        if last_accessed:
            staleness_vals = batch_staleness(last_accessed)
            freshness = 1.0 - (sum(staleness_vals) / len(staleness_vals))
        else:
            freshness = 0.0

        # Coverage
        if transactions and mem_dict:
            query_embs = np.array([t.query_embedding for t in transactions])
            mem_embs = np.array([m.embedding for m in mem_dict.values()])
            sim_matrix = _cosine_similarity_matrix(query_embs, mem_embs)
            coverage = float(np.mean(sim_matrix.max(axis=1) > coverage_threshold))
        else:
            coverage = 0.0

        # Consistency (simplified — count potential contradictions)
        if len(mem_dict) >= 2:
            embs = np.array([m.embedding for m in mem_dict.values()])
            pairs = _find_candidate_pairs(embs, threshold=0.7)
            contradiction_rate = min(1.0, len(pairs) / max(len(mem_dict), 1))
            consistency = 1.0 - contradiction_rate
        else:
            consistency = 1.0

        # Efficiency
        token_counts = [m.tokens for m in mem_dict.values()]
        attr_scores = [s for scores in score_list for s in scores.values()]
        if attr_scores and token_counts:
            # Align lengths
            tc = token_counts[:len(attr_scores)] if len(token_counts) > len(attr_scores) else token_counts
            sc = attr_scores[:len(tc)]
            waste = token_waste_rate(sc, tc)
            efficiency = 1.0 - waste / 100.0
        else:
            efficiency = 0.5

        chi = compute_chi(accuracy, freshness, coverage, consistency, efficiency)
        return chi.score

    before_chi = _chi_for_state(before_dict, before_scores)
    after_chi = _chi_for_state(after_dict, after_scores)

    return {
        "before": round(before_chi, 4),
        "after": round(after_chi, 4),
        "delta": round(after_chi - before_chi, 4),
    }


def _compute_financial_delta(
    before_dict: dict[str, MemoryRecord],
    after_dict: dict[str, MemoryRecord],
    before_scores: list[dict[str, float]],
    after_scores: list[dict[str, float]],
    cost_config: TokenCostConfig,
    agent_id: str,
) -> dict:
    """Compute financial delta (portfolio ROI) between before and after."""
    def _portfolio_for_state(
        mem_dict: dict[str, MemoryRecord],
        score_list: list[dict[str, float]],
    ) -> tuple[float, float]:
        # Aggregate total attribution per memory
        total_attr: dict[str, float] = {}
        for scores in score_list:
            for mid, score in scores.items():
                total_attr[mid] = total_attr.get(mid, 0.0) + score

        memory_data = []
        total_cost = 0.0
        for mid, mem in mem_dict.items():
            pnl = memory_pnl(
                memory_id=mid,
                total_attribution=total_attr.get(mid, mem.total_attribution),
                retrieval_count=max(mem.retrieval_count, 1),
                tokens=mem.tokens,
                config=cost_config,
            )
            memory_data.append({
                "memory_id": mid,
                "revenue": pnl.revenue,
                "cost": pnl.cost,
                "tokens": mem.tokens,
                "roi": pnl.roi,
            })
            total_cost += pnl.cost

        portfolio = compute_portfolio_roi(agent_id, memory_data)
        return portfolio.weighted_roi, total_cost

    before_roi, before_cost = _portfolio_for_state(before_dict, before_scores)
    after_roi, after_cost = _portfolio_for_state(after_dict, after_scores)

    # Estimated monthly savings from cost delta
    monthly_savings = max(0.0, (before_cost - after_cost) * 30)

    return {
        "portfolio_roi_before": round(before_roi, 4),
        "portfolio_roi_after": round(after_roi, 4),
        "estimated_monthly_savings": round(monthly_savings, 6),
    }


# ── Main Entry Point ─────────────────────────────────────────────────

def run_counterfactual(
    current_memories: list[MemoryRecord],
    changes: list[ChangeSpec],
    transactions: list[TransactionRecord],
    existing_contradictions: list[tuple[str, str, float]] | None = None,
    cost_config: TokenCostConfig | None = None,
    include_analysis: set[str] | None = None,
    sim_threshold: float = 0.7,
    coverage_threshold: float = 0.4,
) -> dict:
    """Run counterfactual impact analysis.

    Simulates the effect of proposed memory changes on recent transactions
    by re-running EAS attribution with the modified memory set.

    Args:
        current_memories: Current active memories for the agent
        changes: Proposed changes (add/remove/edit)
        transactions: Recent transactions to replay
        existing_contradictions: Known contradiction pairs [(id1, id2, confidence)]
        cost_config: Token pricing for financial analysis
        include_analysis: Which analyses to run. Default: all.
            Options: "attribution", "contradictions", "coverage", "chi", "financial"
        sim_threshold: Cosine similarity threshold for candidate pair detection
        coverage_threshold: Minimum similarity for a query to be "covered"

    Returns:
        dict with keys: attribution_deltas, summary, contradictions, coverage,
        chi, financial, compute_time_ms
    """
    t0 = time.perf_counter()

    if include_analysis is None:
        include_analysis = {"attribution", "contradictions", "coverage", "chi", "financial"}

    # Step 1: Build before/after memory sets
    before_dict, after_dict = build_counterfactual_memory_set(current_memories, changes)

    # Step 2: Compute attribution for each transaction in both states
    attribution_deltas = []
    before_scores_all = []
    after_scores_all = []
    transactions_affected = 0
    total_score_delta = 0.0
    max_score_delta = 0.0
    new_in_top3 = 0

    for txn in transactions:
        before_scores = _compute_attribution_for_set(before_dict, txn, sim_threshold)
        after_scores = _compute_attribution_for_set(after_dict, txn, sim_threshold)

        before_scores_all.append(before_scores)
        after_scores_all.append(after_scores)

        # Compute delta
        all_mids = set(before_scores.keys()) | set(after_scores.keys())
        txn_max_delta = 0.0
        for mid in all_mids:
            delta = abs(after_scores.get(mid, 0.0) - before_scores.get(mid, 0.0))
            txn_max_delta = max(txn_max_delta, delta)

        # Check if top memory changed
        before_top = max(before_scores, key=before_scores.get) if before_scores else None
        after_top = max(after_scores, key=after_scores.get) if after_scores else None
        top_changed = before_top != after_top

        if txn_max_delta > 1e-6:
            transactions_affected += 1

        total_score_delta += txn_max_delta
        max_score_delta = max(max_score_delta, txn_max_delta)

        # Check if new memories appear in top 3
        if after_scores:
            sorted_after = sorted(after_scores.items(), key=lambda x: x[1], reverse=True)
            top3_ids = [mid for mid, _ in sorted_after[:3]]
            for mid in top3_ids:
                if mid not in before_scores:
                    new_in_top3 += 1

        if "attribution" in include_analysis:
            attribution_deltas.append({
                "transaction_id": txn.id,
                "query_text": txn.query_text,
                "before": before_scores,
                "after": after_scores,
                "top_memory_changed": top_changed,
                "max_score_delta": round(txn_max_delta, 6),
            })

    # Step 3: Build summary
    avg_delta = total_score_delta / len(transactions) if transactions else 0.0
    summary = {
        "transactions_affected": transactions_affected,
        "avg_score_delta": round(avg_delta, 6),
        "max_score_delta": round(max_score_delta, 6),
        "new_memories_in_top3": new_in_top3,
    }

    # Step 4: Optional analyses
    contradictions_result = None
    if "contradictions" in include_analysis:
        contradictions_result = _compute_contradiction_delta(
            before_dict, after_dict, existing_contradictions, sim_threshold,
        )

    coverage_result = None
    if "coverage" in include_analysis:
        coverage_result = _compute_coverage_delta(
            before_dict, after_dict, transactions, coverage_threshold,
        )

    chi_result = None
    if "chi" in include_analysis:
        chi_result = _compute_chi_delta(
            before_dict, after_dict,
            before_scores_all, after_scores_all,
            transactions, coverage_threshold,
        )

    financial_result = None
    if "financial" in include_analysis:
        if cost_config is None:
            cost_config = TokenCostConfig(
                input_token_cost=0.00001,
                output_token_cost=0.00003,
            )
        agent_id = current_memories[0].agent_id if current_memories else "default"
        financial_result = _compute_financial_delta(
            before_dict, after_dict,
            before_scores_all, after_scores_all,
            cost_config, agent_id,
        )

    elapsed_ms = (time.perf_counter() - t0) * 1000

    return {
        "attribution_deltas": attribution_deltas if "attribution" in include_analysis else None,
        "summary": summary,
        "contradictions": contradictions_result,
        "coverage": coverage_result,
        "chi": chi_result,
        "financial": financial_result,
        "compute_time_ms": round(elapsed_ms, 2),
    }
