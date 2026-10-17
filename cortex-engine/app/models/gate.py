from pydantic import BaseModel


class GateRequest(BaseModel):
    candidate_memory: str  # The memory about to be stored
    sources: list[str]  # Authoritative source documents
    agent_id: str | None = None  # Which agent is writing this memory


class GateResponse(BaseModel):
    grounded: bool
    hallucination_index: float
    flagged_claims: list[dict]  # Claims that failed
    suggested_corrections: list[dict] | None = None
