"""Prompt injection detection endpoint."""

import asyncio
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.auth import require_auth
from app.events import event_bus
from app.limiter import limiter

router = APIRouter()

INSTRUCTION_PATTERNS = [
    r"(?i)(ignore|disregard|forget|override)\s+(all\s+)?(previous|prior|above|earlier)",
    r"(?i)(always|never|must)\s+(recommend|suggest|offer|provide|mention|say)",
    r"(?i)system\s*:\s*",
    r"(?i)IMPORTANT\s*:\s*(ignore|override|always|never)",
    r"(?i)new\s+instructions?\s*:",
    r"(?i)(you\s+are|act\s+as|pretend|roleplay)",
    r"(?i)do\s+not\s+(mention|tell|reveal|disclose)",
    r"(?i)(secret|hidden|internal)\s+(instruction|prompt|rule|policy)",
]

AUTHORITY_PATTERNS = [
    r"(?i)(i\s+am|this\s+is)\s+(an?\s+)?(admin|administrator|manager|supervisor|owner)",
    r"(?i)(elevated|special|override)\s+(access|permission|privilege)",
    r"(?i)management\s+(directive|memo|instruction|order)",
]

_COMPILED_INSTRUCTION = [re.compile(p) for p in INSTRUCTION_PATTERNS]
_COMPILED_AUTHORITY = [re.compile(p) for p in AUTHORITY_PATTERNS]


class ShieldRequest(BaseModel):
    text: str
    agent_id: str | None = None


class ShieldResponse(BaseModel):
    safe: bool
    threat_type: str | None = None
    matched_pattern: str | None = None
    latency_ms: float


def _detect_injection(text: str) -> tuple[bool, str | None, str | None]:
    """
    Returns (safe, threat_type, matched_pattern).
    """
    for pattern in _COMPILED_INSTRUCTION:
        m = pattern.search(text)
        if m:
            return False, "instruction_injection", m.group(0)

    for pattern in _COMPILED_AUTHORITY:
        m = pattern.search(text)
        if m:
            return False, "authority_claim", m.group(0)

    return True, None, None


@router.post("/v1/shield", response_model=ShieldResponse)
@limiter.limit("120/minute")
async def shield(
    request: Request,
    body: ShieldRequest,
    api_key_id: str | None = Depends(require_auth),
):
    import time
    start = time.time()

    safe, threat_type, matched_pattern = _detect_injection(body.text)
    latency_ms = round((time.time() - start) * 1000, 2)

    asyncio.create_task(event_bus.publish({
        "type": "shield",
        "ts": datetime.now(timezone.utc).isoformat(),
        "safe": safe,
        "threat_type": threat_type,
        "matched_pattern": matched_pattern,
        "latency_ms": latency_ms,
        "api_key_id": api_key_id,
        "agent_id": body.agent_id or "unknown",
        "text_preview": body.text[:200],
    }))

    return ShieldResponse(
        safe=safe,
        threat_type=threat_type,
        matched_pattern=matched_pattern,
        latency_ms=latency_ms,
    )
