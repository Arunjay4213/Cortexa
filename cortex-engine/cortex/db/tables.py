"""SQLAlchemy table definitions — 9 tables."""

from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

memories = Table(
    "memories",
    metadata,
    Column("id", String, primary_key=True),
    Column("content", Text, nullable=False),
    # Phase 2: migrate to pgvector `vector(384)` type for ANN index support.
    # FLOAT8[] works for <50K memories; beyond that cosine scans become bottleneck.
    Column("embedding", ARRAY(Float(precision=53)), nullable=True),
    Column("tokens", Integer, nullable=False, default=0),
    Column("agent_id", String, nullable=False, default="default", index=True),
    Column("tier", String, nullable=False, default="warm"),
    Column("criticality", Float, nullable=False, default=0.5),
    Column("metadata_", JSONB, nullable=False, server_default="{}"),
    Column("retrieval_count", Integer, nullable=False, default=0),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
    Column("last_accessed", DateTime, nullable=True),
    Column("deleted_at", DateTime, nullable=True),  # soft delete
)

transactions = Table(
    "transactions",
    metadata,
    Column("id", String, primary_key=True),
    Column("query_text", Text, nullable=False),
    # Phase 2: migrate to pgvector `vector(384)` type.
    Column("query_embedding", ARRAY(Float(precision=53)), nullable=True),
    Column("response_text", Text, nullable=True),  # NULL while pending
    # Phase 2: migrate to pgvector `vector(384)` type.
    Column("response_embedding", ARRAY(Float(precision=53)), nullable=True),
    Column("status", String, nullable=False, default="completed"),  # pending | completed
    Column("retrieved_memory_ids", ARRAY(String), nullable=False, server_default="{}"),
    Column("agent_id", String, nullable=False, default="default", index=True),
    Column("input_tokens", Integer, nullable=False, default=0),
    Column("output_tokens", Integer, nullable=False, default=0),
    Column("model", String, nullable=False, default="unknown"),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
)

attribution_scores = Table(
    "attribution_scores",
    metadata,
    Column("id", String, primary_key=True),
    Column("memory_id", String, nullable=False, index=True),
    Column("transaction_id", String, nullable=False, index=True),
    Column("score", Float, nullable=False),
    Column("raw_score", Float, nullable=False),
    Column("method", String, nullable=False, default="eas"),
    Column("confidence", Float, nullable=False, default=1.0),
    Column("compute_time_ms", Float, nullable=False, default=0.0),
)

memory_profiles = Table(
    "memory_profiles",
    metadata,
    Column("memory_id", String, primary_key=True),
    Column("mean_attribution", Float, nullable=False, default=0.0),
    Column("m2", Float, nullable=False, default=0.0),  # Welford's M2 accumulator (variance = m2 / (n-1))
    Column("retrieval_count", Integer, nullable=False, default=0),
    Column("total_attribution", Float, nullable=False, default=0.0),
    Column("trend", String, nullable=False, default="stable"),
    Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
)

contradictions = Table(
    "contradictions",
    metadata,
    Column("id", String, primary_key=True),
    Column("memory_id_1", String, nullable=False, index=True),
    Column("memory_id_2", String, nullable=False, index=True),
    Column("type", String, nullable=False, default="logical"),
    Column("confidence", Float, nullable=False, default=0.0),
    Column("detected_at", DateTime, nullable=False, default=datetime.utcnow),
    Column("resolved", Boolean, nullable=False, default=False),
)

health_snapshots = Table(
    "health_snapshots",
    metadata,
    Column("id", String, primary_key=True),
    Column("agent_id", String, nullable=False, index=True),
    Column("contradiction_rate", Float, nullable=False, default=0.0),
    Column("retrieval_efficiency", Float, nullable=False, default=0.0),
    Column("semantic_drift", Float, nullable=False, default=0.0),
    Column("memory_quality", Float, nullable=False, default=0.0),
    Column("timestamp", DateTime, nullable=False, default=datetime.utcnow),
)

# §3.4 Two-speed loop calibration data — stores (EAS, exact) pairs
# for Phase 2 ContextCite calibration. Populated when exact/ContextCite
# scores are computed; the calibration loop reads from here.
calibration_pairs = Table(
    "calibration_pairs",
    metadata,
    Column("id", String, primary_key=True),
    Column("memory_id", String, nullable=False, index=True),
    Column("transaction_id", String, nullable=False, index=True),
    Column("eas_score", Float, nullable=False),
    Column("exact_score", Float, nullable=False),
    Column("method", String, nullable=False, default="contextcite"),  # exact | contextcite
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
)

# Per-agent token cost configuration — different LLM providers have different pricing
agent_cost_configs = Table(
    "agent_cost_configs",
    metadata,
    Column("agent_id", String, primary_key=True),
    Column("input_token_cost", Float, nullable=False),
    Column("output_token_cost", Float, nullable=False),
    Column("provider", String, nullable=True),  # e.g. "openai", "anthropic", "google"
    Column("model_id", String, nullable=True),   # e.g. "gpt-4", "claude-3-opus"
    Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
)
