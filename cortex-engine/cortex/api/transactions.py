"""Transaction endpoints — the critical path: embed → EAS → store → update profiles.

Supports two modes:
  1. Single-shot: POST /transactions (query + response together)
  2. Two-phase:   POST /transactions/initiate → POST /transactions/{id}/complete
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.attribution import embed
from cortex.attribution.eas import compute_eas
from cortex.config import settings
from cortex.database import get_session
from cortex.db.tables import (
    agent_cost_configs,
    attribution_scores as scores_table,
    memories,
    memory_profiles,
    transactions,
)
from cortex.metrics.calculator import transaction_cost
from cortex.models import (
    AttributionMethod,
    AttributionScore,
    PaginatedResponse,
    TokenCostConfig,
    Transaction,
    TransactionComplete,
    TransactionCreate,
    TransactionInitiate,
    TransactionStatus,
    TransactionWithScores,
)

router = APIRouter(tags=["transactions"])


def _row_to_txn(row) -> Transaction:
    return Transaction(
        id=row.id,
        query_text=row.query_text,
        query_embedding=row.query_embedding or [],
        response_text=row.response_text,
        response_embedding=row.response_embedding or [],
        retrieved_memory_ids=row.retrieved_memory_ids or [],
        agent_id=row.agent_id,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        model=row.model,
        status=row.status,
        created_at=row.created_at,
    )


async def _get_cost_config(db: AsyncSession, agent_id: str) -> TokenCostConfig:
    """Look up per-agent pricing, fall back to global defaults."""
    row = (
        await db.execute(
            select(agent_cost_configs).where(agent_cost_configs.c.agent_id == agent_id)
        )
    ).first()
    if row:
        return TokenCostConfig(
            input_token_cost=row.input_token_cost,
            output_token_cost=row.output_token_cost,
        )
    return TokenCostConfig(
        input_token_cost=settings.default_input_token_cost,
        output_token_cost=settings.default_output_token_cost,
    )


async def _run_eas_and_store(
    db: AsyncSession,
    txn_id: str,
    q_emb: list[float],
    r_emb: list[float],
    retrieved_memory_ids: list[str],
    *,
    snapshot: bool = False,
) -> list[AttributionScore]:
    """Fetch memories, compute EAS, store scores, update profiles atomically.

    When *snapshot* is True (two-phase complete), the memory IDs were captured
    at initiate time and are treated as an immutable set — we skip the
    deleted_at filter so scores stay identical regardless of deletions that
    happen between initiate and complete.
    """
    mem_rows = []
    if retrieved_memory_ids:
        q = select(memories).where(memories.c.id.in_(retrieved_memory_ids))
        if not snapshot:
            q = q.where(memories.c.deleted_at.is_(None))
        # Deterministic ordering: scores are assigned by position, so row order
        # must be stable across separate queries (single-shot vs two-phase).
        q = q.order_by(memories.c.id)
        result = await db.execute(q)
        mem_rows = result.all()

    # Compute EAS — zero LLM calls
    eas_result = {"scores": np.array([]), "raw_scores": np.array([]), "compute_ms": 0.0}
    if mem_rows:
        mem_embeddings = np.array([r.embedding for r in mem_rows if r.embedding])
        if mem_embeddings.size > 0:
            eas_result = compute_eas(mem_embeddings, q_emb, r_emb)

    # Store attribution scores
    score_objs: list[AttributionScore] = []
    mem_with_embeddings = [r for r in mem_rows if r.embedding]
    for i, mem_row in enumerate(mem_with_embeddings):
        score_val = float(eas_result["scores"][i]) if i < len(eas_result["scores"]) else 0.0
        raw_val = float(eas_result["raw_scores"][i]) if i < len(eas_result["raw_scores"]) else 0.0
        score_id = str(uuid.uuid4())

        await db.execute(
            scores_table.insert().values(
                id=score_id,
                memory_id=mem_row.id,
                transaction_id=txn_id,
                score=score_val,
                raw_score=raw_val,
                method=AttributionMethod.eas.value,
                confidence=1.0,
                compute_time_ms=eas_result["compute_ms"],
            )
        )
        score_objs.append(
            AttributionScore(
                id=score_id,
                memory_id=mem_row.id,
                transaction_id=txn_id,
                score=score_val,
                raw_score=raw_val,
                method=AttributionMethod.eas,
                confidence=1.0,
                compute_time_ms=eas_result["compute_ms"],
            )
        )

    # Atomic Welford UPSERT — no race conditions under concurrent writes.
    # The entire mean/m2/count update happens in a single SQL statement.
    now = datetime.now(UTC)
    for score_obj in score_objs:
        await db.execute(
            text("""
                INSERT INTO memory_profiles (memory_id, mean_attribution, m2, retrieval_count, total_attribution, trend, updated_at)
                VALUES (:mem_id, :score, 0, 1, :score, 'stable', :now)
                ON CONFLICT (memory_id) DO UPDATE SET
                    retrieval_count = memory_profiles.retrieval_count + 1,
                    total_attribution = memory_profiles.total_attribution + :score,
                    mean_attribution = memory_profiles.mean_attribution +
                        (:score - memory_profiles.mean_attribution) / (memory_profiles.retrieval_count + 1),
                    m2 = memory_profiles.m2 +
                        (:score - memory_profiles.mean_attribution) *
                        (:score - (memory_profiles.mean_attribution +
                            (:score - memory_profiles.mean_attribution) / (memory_profiles.retrieval_count + 1))),
                    trend = CASE
                        WHEN :score > memory_profiles.mean_attribution * 1.1 THEN 'up'
                        WHEN :score < memory_profiles.mean_attribution * 0.9 THEN 'down'
                        ELSE 'stable'
                    END,
                    updated_at = :now
            """),
            {"mem_id": score_obj.memory_id, "score": score_obj.score, "now": now},
        )

        # Bump retrieval_count + last_accessed on the memory itself
        await db.execute(
            update(memories)
            .where(memories.c.id == score_obj.memory_id)
            .values(
                retrieval_count=memories.c.retrieval_count + 1,
                last_accessed=now,
            )
        )

    return score_objs


# ── Single-shot (complete transaction in one call) ─────────────────────

@router.post("/transactions", response_model=TransactionWithScores, status_code=201)
async def create_transaction(
    body: TransactionCreate,
    db: AsyncSession = Depends(get_session),
):
    # 1. Embed query + response in a single batch call (not two sequential)
    texts_to_embed = []
    embed_indices: dict[str, int] = {}
    if not body.query_embedding:
        embed_indices["query"] = len(texts_to_embed)
        texts_to_embed.append(body.query_text)
    if not body.response_embedding:
        embed_indices["response"] = len(texts_to_embed)
        texts_to_embed.append(body.response_text)

    embeddings = embed(texts_to_embed) if texts_to_embed else []

    q_emb = body.query_embedding or embeddings[embed_indices["query"]]
    r_emb = body.response_embedding or embeddings[embed_indices["response"]]

    input_tokens = body.input_tokens or len(body.query_text.split())
    output_tokens = body.output_tokens or len(body.response_text.split())

    # 2. Store transaction (completed)
    txn_id = str(uuid.uuid4())
    await db.execute(
        transactions.insert().values(
            id=txn_id,
            query_text=body.query_text,
            query_embedding=q_emb,
            response_text=body.response_text,
            response_embedding=r_emb,
            retrieved_memory_ids=body.retrieved_memory_ids,
            agent_id=body.agent_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=body.model,
            status=TransactionStatus.completed.value,
            created_at=datetime.now(UTC),
        )
    )

    # 3. EAS + store scores + atomic Welford
    score_objs = await _run_eas_and_store(
        db, txn_id, q_emb, r_emb, body.retrieved_memory_ids
    )
    await db.commit()

    # 4. Build response with per-agent cost config
    config = await _get_cost_config(db, body.agent_id)
    cost = transaction_cost(input_tokens, output_tokens, config, txn_id)

    txn_row = (await db.execute(select(transactions).where(transactions.c.id == txn_id))).first()
    return TransactionWithScores(
        transaction=_row_to_txn(txn_row),
        scores=score_objs,
        cost=cost,
    )


# ── Two-phase protocol ────────────────────────────────────────────────

@router.post("/transactions/initiate", status_code=201)
async def initiate_transaction(
    body: TransactionInitiate,
    db: AsyncSession = Depends(get_session),
):
    """Phase 1: Create a pending transaction at search time.

    Returns a transaction_id that the caller uses in report_response().
    The transaction has query + memory IDs but no response or attribution yet.
    """
    # Embed query if not provided
    q_emb = body.query_embedding
    if not q_emb:
        q_emb = embed([body.query_text])[0]

    txn_id = str(uuid.uuid4())
    await db.execute(
        transactions.insert().values(
            id=txn_id,
            query_text=body.query_text,
            query_embedding=q_emb,
            response_text=None,
            response_embedding=None,
            retrieved_memory_ids=body.retrieved_memory_ids,
            agent_id=body.agent_id,
            input_tokens=0,
            output_tokens=0,
            model=body.model,
            status=TransactionStatus.pending.value,
            created_at=datetime.now(UTC),
        )
    )
    await db.commit()

    return {"transaction_id": txn_id, "status": "pending"}


@router.post("/transactions/{txn_id}/complete", response_model=TransactionWithScores)
async def complete_transaction(
    txn_id: str,
    body: TransactionComplete,
    db: AsyncSession = Depends(get_session),
):
    """Phase 2: Complete a pending transaction with the response, triggering EAS."""
    txn_row = (
        await db.execute(select(transactions).where(transactions.c.id == txn_id))
    ).first()
    if not txn_row:
        raise HTTPException(404, "Transaction not found")
    if txn_row.status != TransactionStatus.pending.value:
        raise HTTPException(409, "Transaction is not in pending state")

    # Embed response
    r_emb = body.response_embedding
    if not r_emb:
        r_emb = embed([body.response_text])[0]

    input_tokens = body.input_tokens or len(txn_row.query_text.split())
    output_tokens = body.output_tokens or len(body.response_text.split())

    # Update transaction with response
    await db.execute(
        update(transactions)
        .where(transactions.c.id == txn_id)
        .values(
            response_text=body.response_text,
            response_embedding=r_emb,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            status=TransactionStatus.completed.value,
        )
    )

    # Run EAS + store scores + atomic Welford
    # snapshot=True: honor the memory set captured at initiate time, even if
    # memories were soft-deleted between initiate and complete.
    q_emb = txn_row.query_embedding or []
    score_objs = await _run_eas_and_store(
        db, txn_id, q_emb, r_emb, txn_row.retrieved_memory_ids or [],
        snapshot=True,
    )
    await db.commit()

    # Build response
    config = await _get_cost_config(db, txn_row.agent_id)
    cost = transaction_cost(input_tokens, output_tokens, config, txn_id)

    txn_row = (await db.execute(select(transactions).where(transactions.c.id == txn_id))).first()
    return TransactionWithScores(
        transaction=_row_to_txn(txn_row),
        scores=score_objs,
        cost=cost,
    )


# ── Read endpoints ────────────────────────────────────────────────────

@router.get("/transactions", response_model=PaginatedResponse)
async def list_transactions(
    agent_id: str | None = None,
    status: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
):
    q = select(transactions)
    count_q = select(func.count()).select_from(transactions)

    if agent_id:
        q = q.where(transactions.c.agent_id == agent_id)
        count_q = count_q.where(transactions.c.agent_id == agent_id)
    if status:
        q = q.where(transactions.c.status == status)
        count_q = count_q.where(transactions.c.status == status)

    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(q.order_by(transactions.c.created_at.desc()).offset(offset).limit(limit))).all()

    return PaginatedResponse(
        items=[_row_to_txn(r) for r in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/transactions/{txn_id}")
async def get_transaction(
    txn_id: str,
    db: AsyncSession = Depends(get_session),
):
    txn_row = (await db.execute(select(transactions).where(transactions.c.id == txn_id))).first()
    if not txn_row:
        raise HTTPException(404, "Transaction not found")

    score_rows = (
        await db.execute(
            select(scores_table).where(scores_table.c.transaction_id == txn_id)
        )
    ).all()

    scores = [
        AttributionScore(
            id=r.id,
            memory_id=r.memory_id,
            transaction_id=r.transaction_id,
            score=r.score,
            raw_score=r.raw_score,
            method=r.method,
            confidence=r.confidence,
            compute_time_ms=r.compute_time_ms,
        )
        for r in score_rows
    ]

    return {"transaction": _row_to_txn(txn_row), "scores": scores}
