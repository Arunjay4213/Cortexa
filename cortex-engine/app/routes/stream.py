"""SSE stream endpoint for real-time verification events."""

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.auth import require_auth
from app.events import event_bus
from app.limiter import limiter

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/v1/stream")
@limiter.limit("10/minute")
async def stream_events(
    request: Request,
    api_key_id: str | None = Depends(require_auth),
):
    """
    Server-Sent Events stream of all verification events.

    Connect with:
        curl -N https://api.cortexa.ink/v1/stream
    """

    async def generate():
        q = await event_bus.subscribe()
        try:
            # Send connected event immediately
            yield f"data: {json.dumps({'type': 'connected', 'ts': _now()})}\n\n"

            while True:
                try:
                    # Wait for event, heartbeat every 15s
                    payload = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat', 'ts': _now()})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await event_bus.unsubscribe(q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
