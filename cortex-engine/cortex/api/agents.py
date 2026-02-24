"""Agent fleet management endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import distinct, func, select
from cortex.api.websocket import manager
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.database import get_session
from cortex.db.tables import (
    agent_cost_configs,
    attribution_scores,
    contradictions,
    memories,
    transactions,
)
from cortex.metrics.calculator import gini_coefficient, snr_db, token_waste_rate
from cortex.models import AgentCostConfig, AgentDetail, AgentSummary

router = APIRouter(tags=["agents"])


async def _build_agent_summary(db: AsyncSession, aid: str) -> AgentSummary:
    """Build an AgentSummary for a single agent."""
    # Memory count + tier distribution
    mem_rows = (
        await db.execute(
            select(memories).where(
                memories.c.agent_id == aid,
                memories.c.deleted_at.is_(None),
            )
        )
    ).all()
    total_memories = len(mem_rows)
    tier_dist = {"hot": 0, "warm": 0, "cold": 0}
    for mr in mem_rows:
        tier_dist[mr.tier] = tier_dist.get(mr.tier, 0) + 1

    # Transaction count
    txn_count = (
        await db.execute(
            select(func.count())
            .select_from(transactions)
            .where(transactions.c.agent_id == aid)
        )
    ).scalar() or 0

    # Token usage
    token_result = await db.execute(
        select(
            func.coalesce(func.sum(transactions.c.input_tokens), 0),
            func.coalesce(func.sum(transactions.c.output_tokens), 0),
        ).where(transactions.c.agent_id == aid)
    )
    token_row = token_result.first()
    input_tok = token_row[0] if token_row else 0
    output_tok = token_row[1] if token_row else 0

    # Attribution scores
    mem_ids = [mr.id for mr in mem_rows]
    agent_scores: list[float] = []
    agent_tokens: list[int] = []
    if mem_ids:
        score_rows = (
            await db.execute(
                select(attribution_scores).where(
                    attribution_scores.c.memory_id.in_(mem_ids)
                )
            )
        ).all()
        for sr in score_rows:
            agent_scores.append(sr.score)
            mem_match = next((m for m in mem_rows if m.id == sr.memory_id), None)
            agent_tokens.append(mem_match.tokens if mem_match else 0)

    avg_attr = sum(agent_scores) / len(agent_scores) if agent_scores else 0.0

    # Contradiction count
    contra_count = 0
    if mem_ids:
        contra_count = (
            await db.execute(
                select(func.count())
                .select_from(contradictions)
                .where(
                    contradictions.c.memory_id_1.in_(mem_ids)
                    | contradictions.c.memory_id_2.in_(mem_ids),
                    contradictions.c.resolved.is_(False),
                )
            )
        ).scalar() or 0

    # Last active
    last_txn = (
        await db.execute(
            select(transactions.c.created_at)
            .where(transactions.c.agent_id == aid)
            .order_by(transactions.c.created_at.desc())
            .limit(1)
        )
    ).scalar()

    return AgentSummary(
        agent_id=aid,
        total_memories=total_memories,
        total_transactions=txn_count,
        avg_attribution=avg_attr,
        tier_distribution=tier_dist,
        token_usage={"input": input_tok, "output": output_tok},
        gini_coefficient=gini_coefficient(agent_scores) if agent_scores else 0.0,
        snr_db=snr_db(agent_scores) if agent_scores else 0.0,
        waste_rate=token_waste_rate(agent_scores, agent_tokens) if agent_scores else 0.0,
        contradiction_count=contra_count,
        last_active=last_txn,
    )


@router.get("/agents", response_model=list[AgentSummary])
async def list_agents(db: AsyncSession = Depends(get_session)):
    """List all agents with summary stats."""
    # Collect agent IDs from memories and transactions
    mem_agent_result = await db.execute(
        select(distinct(memories.c.agent_id)).where(memories.c.deleted_at.is_(None))
    )
    agent_ids = [r[0] for r in mem_agent_result.all()]

    txn_agent_result = await db.execute(select(distinct(transactions.c.agent_id)))
    for r in txn_agent_result.all():
        if r[0] not in agent_ids:
            agent_ids.append(r[0])

    agents = []
    for aid in agent_ids:
        agents.append(await _build_agent_summary(db, aid))

    return agents


@router.get("/agents/{agent_id}", response_model=AgentDetail)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_session)):
    """Detailed agent view with cost config and recent transactions."""
    summary = await _build_agent_summary(db, agent_id)

    # Get cost config
    config_row = (
        await db.execute(
            select(agent_cost_configs).where(agent_cost_configs.c.agent_id == agent_id)
        )
    ).first()

    cost_config = None
    if config_row:
        cost_config = AgentCostConfig(
            agent_id=config_row.agent_id,
            input_token_cost=config_row.input_token_cost,
            output_token_cost=config_row.output_token_cost,
            provider=config_row.provider,
            model_id=config_row.model_id,
            updated_at=config_row.updated_at,
        )

    # Recent transactions
    recent_rows = (
        await db.execute(
            select(transactions)
            .where(transactions.c.agent_id == agent_id)
            .order_by(transactions.c.created_at.desc())
            .limit(10)
        )
    ).all()

    from cortex.api.transactions import _row_to_txn

    return AgentDetail(
        agent_id=summary.agent_id,
        total_memories=summary.total_memories,
        total_transactions=summary.total_transactions,
        avg_attribution=summary.avg_attribution,
        tier_distribution=summary.tier_distribution,
        token_usage=summary.token_usage,
        gini_coefficient=summary.gini_coefficient,
        snr_db=summary.snr_db,
        waste_rate=summary.waste_rate,
        contradiction_count=summary.contradiction_count,
        last_active=summary.last_active,
        cost_config=cost_config,
        recent_transactions=[_row_to_txn(r) for r in recent_rows],
    )


@router.put("/agents/{agent_id}/cost-config", response_model=AgentCostConfig)
async def upsert_cost_config(
    agent_id: str,
    body: AgentCostConfig,
    db: AsyncSession = Depends(get_session),
):
    """Create or update agent cost configuration."""
    existing = (
        await db.execute(
            select(agent_cost_configs).where(agent_cost_configs.c.agent_id == agent_id)
        )
    ).first()

    now = datetime.now(UTC)
    if existing:
        from sqlalchemy import update
        await db.execute(
            update(agent_cost_configs)
            .where(agent_cost_configs.c.agent_id == agent_id)
            .values(
                input_token_cost=body.input_token_cost,
                output_token_cost=body.output_token_cost,
                provider=body.provider,
                model_id=body.model_id,
                updated_at=now,
            )
        )
    else:
        await db.execute(
            agent_cost_configs.insert().values(
                agent_id=agent_id,
                input_token_cost=body.input_token_cost,
                output_token_cost=body.output_token_cost,
                provider=body.provider,
                model_id=body.model_id,
                updated_at=now,
            )
        )

    await db.commit()
    await manager.broadcast("dashboard", {"type": "agent_updated", "agent_id": agent_id})

    return AgentCostConfig(
        agent_id=agent_id,
        input_token_cost=body.input_token_cost,
        output_token_cost=body.output_token_cost,
        provider=body.provider,
        model_id=body.model_id,
        updated_at=now,
    )


@router.get("/agents/{agent_id}/cost-config")
async def get_cost_config(agent_id: str, db: AsyncSession = Depends(get_session)):
    """Get agent cost configuration."""
    row = (
        await db.execute(
            select(agent_cost_configs).where(agent_cost_configs.c.agent_id == agent_id)
        )
    ).first()

    if not row:
        raise HTTPException(404, "Cost config not found for this agent")

    return AgentCostConfig(
        agent_id=row.agent_id,
        input_token_cost=row.input_token_cost,
        output_token_cost=row.output_token_cost,
        provider=row.provider,
        model_id=row.model_id,
        updated_at=row.updated_at,
    )
