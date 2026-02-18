"""Dashboard aggregate endpoints — shape matches frontend AgentSummary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.database import get_session
from cortex.db.tables import (
    agent_cost_configs,
    attribution_scores,
    contradictions,
    health_snapshots,
    memories,
    memory_profiles,
    transactions,
)
from cortex.config import settings
from cortex.metrics.calculator import gini_coefficient, snr_db, token_waste_rate
from cortex.models import (
    AgentSummary,
    CostSummaryResponse,
    DashboardOverview,
    TimeSeriesBucket,
    TimeSeriesResponse,
    TopMemoryResponse,
)

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


@router.get("/dashboard/metrics/timeseries", response_model=TimeSeriesResponse)
async def get_timeseries(
    agent_id: str | None = None,
    metric: str = Query("contradiction_rate", description="Metric name from health_snapshots"),
    days: int = Query(7, ge=1, le=90),
    bucket: str = Query("day", description="Bucket size: hour, day"),
    db: AsyncSession = Depends(get_session),
):
    """Time-bucketed health metrics for charting."""
    cutoff = datetime.now(UTC) - timedelta(days=days)

    q = select(health_snapshots).where(health_snapshots.c.timestamp >= cutoff)
    if agent_id:
        q = q.where(health_snapshots.c.agent_id == agent_id)
    q = q.order_by(health_snapshots.c.timestamp.asc())

    rows = (await db.execute(q)).all()

    # Group by bucket
    bucket_size = timedelta(hours=1) if bucket == "hour" else timedelta(days=1)
    buckets: list[TimeSeriesBucket] = []
    bucket_map: dict[str, list[float]] = {}

    valid_metrics = {"contradiction_rate", "retrieval_efficiency", "semantic_drift", "memory_quality"}
    metric_name = metric if metric in valid_metrics else "contradiction_rate"

    for row in rows:
        ts = row.timestamp
        bucket_key = ts.replace(
            minute=0, second=0, microsecond=0
        ) if bucket == "hour" else ts.replace(hour=0, minute=0, second=0, microsecond=0)
        key = bucket_key.isoformat()

        if key not in bucket_map:
            bucket_map[key] = []
        bucket_map[key].append(getattr(row, metric_name, 0.0))

    for key, values in sorted(bucket_map.items()):
        buckets.append(TimeSeriesBucket(
            timestamp=datetime.fromisoformat(key),
            value=sum(values) / len(values),
            count=len(values),
        ))

    return TimeSeriesResponse(
        metric=metric_name,
        agent_id=agent_id,
        buckets=buckets,
        days=days,
    )


@router.get("/dashboard/top-memories", response_model=list[TopMemoryResponse])
async def get_top_memories(
    agent_id: str | None = None,
    n: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
):
    """Top N memories by total_attribution from memory_profiles."""
    q = (
        select(memory_profiles, memories.c.content, memories.c.agent_id, memories.c.tier)
        .join(memories, memory_profiles.c.memory_id == memories.c.id)
        .where(memories.c.deleted_at.is_(None))
    )
    if agent_id:
        q = q.where(memories.c.agent_id == agent_id)
    q = q.order_by(memory_profiles.c.total_attribution.desc()).limit(n)

    rows = (await db.execute(q)).all()
    return [
        TopMemoryResponse(
            memory_id=r.memory_id,
            content=r.content,
            agent_id=r.agent_id,
            total_attribution=r.total_attribution,
            mean_attribution=r.mean_attribution,
            retrieval_count=r.retrieval_count,
            tier=r.tier,
        )
        for r in rows
    ]


@router.get("/dashboard/cost-summary", response_model=list[CostSummaryResponse])
async def get_cost_summary(
    agent_id: str | None = None,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_session),
):
    """Aggregated cost across agents."""
    cutoff = datetime.now(UTC) - timedelta(days=days)

    # Get all agent IDs
    q_agents = select(distinct(transactions.c.agent_id)).where(
        transactions.c.created_at >= cutoff
    )
    if agent_id:
        q_agents = q_agents.where(transactions.c.agent_id == agent_id)

    agent_ids = [r[0] for r in (await db.execute(q_agents)).all()]

    results: list[CostSummaryResponse] = []
    for aid in agent_ids:
        # Get cost config
        config_row = (
            await db.execute(
                select(agent_cost_configs).where(agent_cost_configs.c.agent_id == aid)
            )
        ).first()

        input_price = config_row.input_token_cost if config_row else settings.default_input_token_cost
        output_price = config_row.output_token_cost if config_row else settings.default_output_token_cost

        # Sum tokens
        token_result = await db.execute(
            select(
                func.coalesce(func.sum(transactions.c.input_tokens), 0),
                func.coalesce(func.sum(transactions.c.output_tokens), 0),
                func.count(),
            )
            .select_from(transactions)
            .where(
                transactions.c.agent_id == aid,
                transactions.c.created_at >= cutoff,
            )
        )
        row = token_result.first()
        input_tok = row[0]
        output_tok = row[1]
        txn_count = row[2]

        input_cost = input_tok * input_price
        output_cost = output_tok * output_price
        total_cost = input_cost + output_cost

        results.append(CostSummaryResponse(
            agent_id=aid,
            total_cost=total_cost,
            input_cost=input_cost,
            output_cost=output_cost,
            transaction_count=txn_count,
            avg_cost_per_transaction=total_cost / txn_count if txn_count > 0 else 0.0,
        ))

    return results
