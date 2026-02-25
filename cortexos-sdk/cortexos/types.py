"""Public data models returned by the CortexOS SDK."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Memory(BaseModel):
    """A single memory unit stored in the CortexOS engine."""

    id: str
    content: str
    agent_id: str
    tier: str = "warm"
    importance: float = Field(alias="criticality", default=0.5)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    retrieval_count: int = 0
    created_at: datetime
    last_accessed: datetime | None = None

    model_config = {"populate_by_name": True}

    @classmethod
    def _from_api(cls, data: dict) -> "Memory":
        """Construct from raw API response dict (handles metadata→tags extraction)."""
        raw_meta: dict = data.get("metadata", {}) or {}
        tags = raw_meta.pop("_tags", [])
        return cls(
            id=data["id"],
            content=data["content"],
            agent_id=data["agent_id"],
            tier=data.get("tier", "warm"),
            criticality=data.get("criticality", 0.5),
            tags=tags,
            metadata=raw_meta,
            retrieval_count=data.get("retrieval_count", 0),
            created_at=data["created_at"],
            last_accessed=data.get("last_accessed"),
        )


class EASScore(BaseModel):
    """Attribution score for a single memory."""

    memory_id: str
    score: float


class Attribution(BaseModel):
    """Result of an attribution (EAS) computation."""

    transaction_id: str
    query: str
    response: str
    scores: dict[str, float]  # memory_id → score

    @classmethod
    def _from_api(cls, data: dict, query: str, response: str) -> "Attribution":
        scores = {s["memory_id"]: s["score"] for s in data.get("scores", [])}
        # Server wraps transaction under a "transaction" key
        txn = data.get("transaction", data)
        return cls(
            transaction_id=txn["id"],
            query=query,
            response=response,
            scores=scores,
        )


class CAMAClaimSource(BaseModel):
    """A single memory's contribution to a claim."""

    memory_id: str
    shapley_value: float
    entailment: float


class CAMAClaim(BaseModel):
    """Analysis of a single claim extracted from the response."""

    claim: str
    claim_type: str  # "factual" | "synthesis" | "opinion"
    support_type: str  # "essential" | "redundant" | "unsupported"
    sources: list[CAMAClaimSource] = Field(default_factory=list)
    best_entailment: float = 0.0
    is_hallucination: bool = False
    hallucination_reason: str = ""  # "numerical_ungrounded" | "nli_empty" | "nli_low" | "opinion_skip" | ""


class CAMAAttribution(BaseModel):
    """Result of a CAMA (Claim-Aware Memory Attribution) computation."""

    transaction_id: str
    scores: dict[str, float]  # memory_id → normalized attribution score
    claims: list[CAMAClaim]
    unsupported_claims: list[dict[str, Any]]
    hallucination_index: float
    dead_memories: list[str]
    method: str = "cama"
    num_claims: int = 0
    num_nli_calls: int = 0
    latency_ms: dict[str, float] = Field(default_factory=dict)

    @classmethod
    def _from_api(cls, data: dict, transaction_id: str) -> "CAMAAttribution":
        claims = [
            CAMAClaim(
                claim=c["claim"],
                claim_type=c["claim_type"],
                support_type=c["support_type"],
                sources=[CAMAClaimSource(**s) for s in c.get("sources", [])],
                best_entailment=c.get("best_entailment", 0.0),
                is_hallucination=c.get("is_hallucination", False),
                hallucination_reason=c.get("hallucination_reason", ""),
            )
            for c in data.get("claims", [])
        ]
        return cls(
            transaction_id=transaction_id,
            scores=data.get("scores", {}),
            claims=claims,
            unsupported_claims=data.get("unsupported_claims", []),
            hallucination_index=data.get("hallucination_index", 0.0),
            dead_memories=data.get("dead_memories", []),
            method=data.get("method", "cama"),
            num_claims=data.get("num_claims", 0),
            num_nli_calls=data.get("num_nli_calls", 0),
            latency_ms=data.get("latency_ms", {}),
        )


class RecallResult(BaseModel):
    """A single result from a semantic recall query."""

    memory: Memory
    score: float  # cosine similarity [0, 1]


class Page(BaseModel):
    """Paginated list of memories."""

    items: list[Memory]
    total: int
    offset: int
    limit: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total


class RecallAndAttributeResult(BaseModel):
    """Combined result from recall_and_attribute()."""

    memories: list[RecallResult]
    attribution: Attribution
