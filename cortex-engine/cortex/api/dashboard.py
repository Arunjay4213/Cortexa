"""Dashboard aggregate endpoints — shape matches frontend AgentSummary."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.database import get_session
from cortex.db.tables import (
    attribution_scores,
    contradictions,
    memories,
    transactions,
)
from cortex.metrics.calculator import gini_coefficient, snr_db, token_waste_rate
from cortex.models import AgentSummary, DashboardOverview

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/overview", response_model=DashboardOverview)
async def dashboard_overview(db: AsyncSession = Depends(get_session)):
    # Distinct agent IDs
    agent_ids_result = await db.execute(
        select(distinct(memories.c.agent_id)).where(memories.c.deleted_at.is_(None))
    )
    agent_ids = [r[0] for r in agent_ids_result.all()]

    # Also include agents that only have transactions
    txn_agent_result = await db.execute(select(distinct(transactions.c.agent_id)))
    for r in txn_agent_result.all():
        if r[0] not in agent_ids:
            agent_ids.append(r[0])

    agents: list[AgentSummary] = []
    all_scores: list[float] = []
    all_token_counts: list[int] = []

    for aid in agent_ids:
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

        # Attribution scores for this agent's memories
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

        all_scores.extend(agent_scores)
        all_token_counts.extend(agent_tokens)

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

        agents.append(
            AgentSummary(
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
        )

    # Totals
    total_mem = sum(a.total_memories for a in agents)
    total_txn = sum(a.total_transactions for a in agents)
    total_attr = (
        await db.execute(select(func.count()).select_from(attribution_scores))
    ).scalar() or 0

    return DashboardOverview(
        agents=agents,
        total_memories=total_mem,
        total_transactions=total_txn,
        total_attributions=total_attr,
        overall_gini=gini_coefficient(all_scores) if all_scores else 0.0,
        overall_snr_db=snr_db(all_scores) if all_scores else 0.0,
        overall_waste_rate=token_waste_rate(all_scores, all_token_counts) if all_scores else 0.0,
    )
