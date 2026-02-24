"""Phase 3 Lifecycle API — memory optimization recommendations and execution."""

from fastapi import APIRouter, HTTPException, Query

from cortex.api.websocket import manager
from cortex.database import engine
from cortex.models import (
    BudgetOptimization,
    ExecuteRecommendationsRequest,
    LifecycleRecommendations,
)
from cortex.attribution.lifecycle import (
    get_lifecycle_recommendations,
    compute_budget_optimization,
    execute_archive,
    execute_tier_changes,
    execute_consolidation,
)

router = APIRouter(prefix="/lifecycle", tags=["lifecycle"])


@router.get("/{agent_id}/recommendations", response_model=LifecycleRecommendations)
async def recommendations(agent_id: str):
    """Get lifecycle optimization recommendations for an agent."""
    async with engine.connect() as conn:
        result = await get_lifecycle_recommendations(agent_id, conn)
        return result


@router.post("/{agent_id}/execute")
async def execute(agent_id: str, req: ExecuteRecommendationsRequest):
    """Execute selected lifecycle recommendations."""
    async with engine.begin() as conn:
        archived = 0
        tier_changed = 0
        consolidated = 0

        if req.archive_memory_ids:
            archived = await execute_archive(agent_id, req.archive_memory_ids, conn)

        if req.tier_changes:
            tier_changed = await execute_tier_changes(agent_id, req.tier_changes, conn)

        if req.consolidate_groups:
            consolidated = await execute_consolidation(agent_id, req.consolidate_groups, conn)

        await manager.broadcast("dashboard", {"type": "lifecycle_executed", "agent_id": agent_id, "actions": archived + tier_changed + consolidated})

        return {
            "agent_id": agent_id,
            "archived": archived,
            "tier_changed": tier_changed,
            "consolidated": consolidated,
            "total_actions": archived + tier_changed + consolidated,
        }


@router.get("/{agent_id}/budget", response_model=BudgetOptimization)
async def budget(agent_id: str, budget_tokens: int = Query(default=100000, ge=0)):
    """Compute optimal memory selection under a token budget."""
    async with engine.connect() as conn:
        result = await compute_budget_optimization(agent_id, conn, budget_tokens)
        return result
