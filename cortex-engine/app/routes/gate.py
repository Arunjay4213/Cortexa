import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from app.auth import require_auth
from app.events import event_bus
from app.limiter import limiter
from app.models.check import CheckRequest
from app.models.gate import GateRequest, GateResponse
from app.services.checker import run_check

router = APIRouter()

GATE_THRESHOLD = 0.3


@router.post("/v1/gate", response_model=GateResponse)
@limiter.limit("120/minute")
async def gate_memory(
    request: Request,
    body: GateRequest,
    api_key_id: str | None = Depends(require_auth),
):
    nli_service = request.app.state.nli
    settings = request.app.state.settings
    attributor = getattr(request.app.state, "attributor", None)

    # Internally, run check on candidate_memory against sources
    check_request = CheckRequest(
        response=body.candidate_memory,
        sources=body.sources,
    )
    result = await run_check(check_request, nli_service, settings, attributor)

    # Build flagged claims and suggested corrections
    flagged_claims = []
    suggested_corrections = []

    for claim in result.claims:
        if not claim.grounded and claim.verdict != "OPINION":
            flagged = {
                "text": claim.text,
                "verdict": claim.verdict,
                "reason": claim.reason,
            }
            flagged_claims.append(flagged)

            if claim.verdict == "NUM_MISMATCH":
                suggested_corrections.append(
                    {
                        "claim": claim.text,
                        "issue": claim.reason,
                        "suggestion": "Replace with numbers found in source documents",
                    }
                )

    gate_result = GateResponse(
        grounded=result.hallucination_index <= GATE_THRESHOLD,
        hallucination_index=result.hallucination_index,
        flagged_claims=flagged_claims,
        suggested_corrections=suggested_corrections if suggested_corrections else None,
    )

    # Publish gate event to SSE stream (fire and forget)
    asyncio.create_task(event_bus.publish({
        "type": "gate",
        "ts": datetime.now(timezone.utc).isoformat(),
        "grounded": gate_result.grounded,
        "hi": gate_result.hallucination_index,
        "flagged": len(flagged_claims),
        "latency_ms": result.latency_ms,
        "api_key_id": api_key_id,
        "agent_id": body.agent_id or "unknown",
        "candidate_preview": body.candidate_memory[:200],
        "total_claims": result.total_claims,
        "verdicts": [c.verdict for c in result.claims],
        "flagged_claims": flagged_claims,
        "suggested_corrections": gate_result.suggested_corrections,
        "claims": [
            {
                "text": c.text,
                "verdict": c.verdict,
                "grounded": c.grounded,
                "confidence": c.confidence,
                "reason": c.reason,
                "source_quote": c.source_quote,
                "attribution": c.attribution,
                "primary_source_index": c.primary_source_index,
            }
            for c in result.claims
        ],
    }))

    return gate_result
