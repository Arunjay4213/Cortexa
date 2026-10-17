import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from app.auth import require_auth
from app.events import event_bus
from app.limiter import limiter
from app.models.check import CheckRequest, CheckResponse
from app.services.checker import run_check

router = APIRouter()


@router.post("/v1/check", response_model=CheckResponse)
@limiter.limit("60/minute")
async def check_response(
    request: Request,
    body: CheckRequest,
    api_key_id: str | None = Depends(require_auth),
):
    nli_service = request.app.state.nli
    settings = request.app.state.settings
    attributor = getattr(request.app.state, "attributor", None)

    result = await run_check(body, nli_service, settings, attributor)

    # Publish check event to SSE stream (fire and forget)
    asyncio.create_task(event_bus.publish({
        "type": "check",
        "ts": datetime.now(timezone.utc).isoformat(),
        "hi": result.hallucination_index,
        "total_claims": result.total_claims,
        "grounded": result.grounded_count,
        "hallucinated": result.hallucinated_count,
        "opinion_count": result.opinion_count,
        "latency_ms": result.latency_ms,
        "verdicts": [c.verdict for c in result.claims],
        "api_key_id": api_key_id,
        "agent_id": body.agent_id or "unknown",
        "response_preview": body.response[:200],
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

    # Log to database if available
    db_factory = getattr(request.app.state, "db", None)
    if db_factory is not None:
        try:
            from app.db.tables import verification_logs
            from sqlalchemy import insert

            sources_hash = hashlib.sha256(
                json.dumps(body.sources, sort_keys=True).encode()
            ).hexdigest()[:16]

            async with db_factory() as session:
                await session.execute(
                    insert(verification_logs).values(
                        id=str(uuid.uuid4()),
                        response_text=body.response,
                        sources_hash=sources_hash,
                        hallucination_index=result.hallucination_index,
                        total_claims=result.total_claims,
                        grounded_count=result.grounded_count,
                        hallucinated_count=result.hallucinated_count,
                        claims=json.loads(result.model_dump_json())["claims"],
                        latency_ms=result.latency_ms,
                        api_key_id=api_key_id,
                    )
                )
                await session.commit()
        except Exception:
            pass  # Don't fail the request if logging fails

    return result
