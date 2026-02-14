# Provenance Graph — Developer Guide

The provenance graph is CortexOS's compliance backbone: a directed acyclic graph (DAG) that tracks the full lineage of data through the memory pipeline. It powers GDPR cascading deletion, hallucination root-cause tracing, and compliance certificate generation.

```
interaction ──creation──▶ memory ──derivation──▶ summary
                              │                      │
                              ├──derivation──▶ embedding
                              │
                         attribution
                              │
                              ▼
                         interaction (influenced)
```

> **Design spec**: See `PROVENANCE.md` for the full technical specification including the rationale behind every design decision.

---

## Architecture Overview

The implementation spans three layers:

| Layer | Files | Purpose |
|-------|-------|---------|
| **ORM Models** | `cortex/db/models/provenance.py`, `compliance.py` | SQLAlchemy 2.x `mapped_column` definitions for all node and edge types |
| **Migration** | `alembic/versions/003_add_provenance_graph.py` | DDL with PostgreSQL HASH/RANGE partitioning |
| **Graph Operations** | `cortex/compliance/provenance.py` | `ProvenanceGraph` class — write path, F(u), I(u) queries |

---

## Data Model

### Node Types (5)

| Model | Table | Description |
|-------|-------|-------------|
| `InteractionNode` | `interaction_nodes` | An agent query-response cycle. Stores the user query, LLM response, cost, and agent metadata. |
| `MemoryNode` | `memory_nodes` | A memory unit. HASH-partitioned by `shard_id` across 16 partitions for SISA alignment. |
| `SummaryNode` | `summary_nodes` | A consolidation summary derived from multiple memories. First-class node for GDPR derived-data tracking. |
| `EmbeddingNode` | `embedding_nodes` | A vector embedding reference. Points to the vector store entry (e.g., Pinecone ID). |
| `ResponseNode` | `response_nodes` | Statement-level response decomposition. Created on-demand when ContextCite runs (~1% of queries). |

### Edge Types (4)

All edges are **append-only and immutable**. Updated scores produce new versioned edges; old edges are marked superseded but never deleted.

| Model | Table | Direction | Purpose |
|-------|-------|-----------|---------|
| `CreationEdge` | `creation_edges` | interaction → memory | Links an interaction to the memories it created |
| `AttributionEdge` | `attribution_edges` | memory → interaction | Calibrated attribution score. RANGE-partitioned by `created_at` (monthly). |
| `DerivationEdge` | `derivation_edges` | node → node | Tracks derived data: memory→summary, memory→embedding, summary→embedding, etc. Polymorphic. |
| `StatementAttributionEdge` | `statement_attribution_edges` | memory → response | Statement-level ContextCite scores (A[p,j] matrix). |

### Compliance Certificate

| Model | Table | Purpose |
|-------|-------|---------|
| `ComplianceCertificate` | `compliance_certificates` | Cryptographic audit log for GDPR deletion operations. Contains SHA-256 hash of the footprint snapshot. |

### Enums

All enums inherit from `(str, enum.Enum)` and are created as PostgreSQL types in the migration:

| Enum | Values | Used By |
|------|--------|---------|
| `MemoryType` | `raw`, `consolidated`, `critical` | `MemoryNode.memory_type` |
| `MemoryStatus` | `active`, `archived`, `deleted`, `pending_deletion` | `MemoryNode.status` |
| `Criticality` | `normal`, `safety_critical`, `protected` | `MemoryNode.criticality` |
| `ScoreType` | `eas`, `contextcite`, `calibrated` | `AttributionEdge.score_type` |
| `DerivationType` | `consolidation`, `embedding`, `re_embedding`, `summary` | `DerivationEdge.derivation_type` |
| `NodeType` | `memory`, `summary`, `embedding` | `DerivationEdge.source_type/target_type` |
| `RequestType` | `gdpr_deletion`, `audit_request`, `data_export` | `ComplianceCertificate.request_type` |

---

## PostgreSQL Partitioning

Two tables use native PostgreSQL partitioning:

### `memory_nodes` — HASH(shard_id)

Partitioned into 16 shards (`memory_nodes_p0` through `memory_nodes_p15`) aligned with the SISA framework. The shard is computed as `hash(user_id) % 16`.

**Consequence**: The primary key is composite `(id, shard_id)` because PostgreSQL requires the partition key in the PK. Edge tables that reference `memory_nodes` use **logical foreign keys** (no DB constraint) since PG cannot enforce FKs to hash-partitioned tables with composite PKs.

### `attribution_edges` — RANGE(created_at)

Partitioned by month (12 partitions for 2026 + a default partition for overflow). This enables:
- Efficient retention tiering (drop/detach old partitions)
- Time-scoped queries (partition pruning on `created_at`)

**Consequence**: The primary key is composite `(id, created_at)`. Include `created_at` in WHERE clauses for efficient queries.

### Adding Future Partitions

The migration seeds 2026 partitions. To add 2027:

```sql
CREATE TABLE attribution_edges_2027_01
    PARTITION OF attribution_edges
    FOR VALUES FROM ('2027-01-01') TO ('2027-02-01');
-- repeat for each month
```

This should be automated via a cron job or the retention engine.

---

## ProvenanceGraph API

All methods are async and accept an `AsyncSession`. The caller manages transaction boundaries (commit/rollback).

```python
from cortex.compliance.provenance import ProvenanceGraph, UserFootprint

graph = ProvenanceGraph()
```

### Write Operations

#### `record_transaction()`

Records a complete agent query-response cycle with attribution scores.

```python
interaction = await graph.record_transaction(
    session,
    user_id="user_123",
    query="What is my account balance?",
    response="Your balance is $1,234.",
    agent_id="finance-agent",
    transaction_cost=0.0042,
    memory_ids=[mem_1.id, mem_2.id],
    attribution_scores=[0.7, 0.3],
    score_type=ScoreType.calibrated,
)
# Creates: 1 InteractionNode + 2 AttributionEdges
```

#### `record_memory_creation()`

Records when an interaction creates a new memory, including the embedding.

```python
mem_node, emb_node = await graph.record_memory_creation(
    session,
    interaction_id=interaction.id,
    content="User's account balance is $1,234",
    user_id="user_123",
    vector_ref="pinecone-id-abc123",
    embedding_model="text-embedding-3-small",
    embedding_dim=1536,
    token_count=12,
)
# Creates: 1 MemoryNode + 1 CreationEdge + 1 EmbeddingNode + 1 DerivationEdge
```

#### `record_consolidation()`

Records when multiple memories are consolidated into a summary.

```python
summary = await graph.record_consolidation(
    session,
    source_memory_ids=[mem_1.id, mem_2.id, mem_3.id],
    summary_content="User has a finance account with balance ~$1,200",
    method="llm_consolidation",
)
# Creates: 1 SummaryNode + 3 DerivationEdges (one per source memory)
```

#### `record_contextcite()`

Records statement-level attribution when ContextCite runs.

```python
response_node = await graph.record_contextcite(
    session,
    interaction_id=interaction.id,
    statements=[
        {"text": "Your balance is $1,234.", "index": 0},
        {"text": "Last updated today.", "index": 1},
    ],
    memory_scores=[
        {"memory_id": mem_1.id, "statement_index": 0, "score": 0.9},
        {"memory_id": mem_2.id, "statement_index": 1, "score": 0.6},
    ],
)
# Creates: 1 ResponseNode + 2 StatementAttributionEdges
```

#### `update_attribution()`

Creates a new version of an attribution edge when calibration corrects a score.

```python
new_edge = await graph.update_attribution(
    session,
    source_id=mem_1.id,
    target_id=interaction.id,
    new_score=0.65,
    new_score_type=ScoreType.calibrated,
)
# Old edge: is_current=False, version=1
# New edge: is_current=True,  version=2
```

### Read Operations

#### `compute_user_footprint()` — F(u)

Computes all data nodes reachable from a user's interactions using a recursive CTE. This is the foundation for GDPR deletion.

```python
footprint = await graph.compute_user_footprint(session, user_id="user_123")

footprint.memory_node_ids      # All memories created by user's interactions
footprint.summary_node_ids     # Summaries derived from those memories
footprint.embedding_node_ids   # Embeddings derived from memories/summaries
footprint.interaction_node_ids # The user's own interactions
footprint.all_node_ids         # Union of all the above

# For compliance certificates:
footprint.serialize()          # Dict representation
footprint.certificate_hash()   # SHA-256 hex digest
```

**SQL under the hood** (recursive CTE):
```sql
WITH RECURSIVE user_footprint AS (
    SELECT ce.target_id AS node_id, 'memory' AS node_type
    FROM creation_edges ce
    JOIN interaction_nodes i ON ce.source_id = i.id
    WHERE i.user_id = :user_id
    UNION
    SELECT de.target_id, de.target_type::text
    FROM derivation_edges de
    JOIN user_footprint uf ON de.source_id = uf.node_id
)
SELECT node_id, node_type FROM user_footprint;
```

#### `compute_influence_footprint()` — I(u)

Finds all interactions that were influenced by a user's memories (i.e., other users' responses that cited this user's data).

```python
influenced_ids = await graph.compute_influence_footprint(session, user_id="user_123")
# Returns: list of InteractionNode UUIDs where user_123's memories had score > 0
```

---

## File Reference

### New Files

| Path | Description |
|------|-------------|
| `cortex/db/models/base.py` | `DeclarativeBase` shared by all ORM models. Separated to avoid circular imports. |
| `cortex/db/models/provenance.py` | 5 node models, 4 edge models, 6 enum types. Uses `mapped_column` style per project conventions. |
| `cortex/db/models/compliance.py` | `ComplianceCertificate` model and `RequestType` enum. |
| `cortex/db/models/__init__.py` | Re-exports `Base` and all model classes for convenient imports. |
| `cortex/compliance/__init__.py` | Module init for the compliance engine package. |
| `cortex/compliance/provenance.py` | `ProvenanceGraph` class (7 async methods) and `UserFootprint` dataclass. |
| `alembic/versions/003_add_provenance_graph.py` | Migration creating 10 tables (2 partitioned), 7 enum types, and all indexes. |

### Modified Files

| Path | Change |
|------|--------|
| `alembic/env.py` | Merges legacy `Table()` metadata with ORM `Base.metadata` so Alembic sees all 18 tables. |
| `pyproject.toml` | Added `uuid-utils>=0.9,<1` dependency for UUID v7 generation. |

---

## Design Decisions

### Why no FK constraints to `memory_nodes`?

PostgreSQL cannot enforce foreign keys referencing a hash-partitioned table with a composite primary key `(id, shard_id)` unless the FK also includes `shard_id`. Since edge tables don't store `shard_id`, we use logical foreign keys enforced at the application layer. The columns are documented with comments like `# logical FK to memory_nodes.id`.

### Why composite primary keys on partitioned tables?

PostgreSQL requires the partition key to be part of any unique constraint (including PKs). For `memory_nodes` this means `PK(id, shard_id)`, and for `attribution_edges` it means `PK(id, created_at)`. UUID v7 provides time-sortability which helps with range partition pruning.

### Why polymorphic DerivationEdge?

`DerivationEdge.source_id` can reference `memory_nodes`, `summary_nodes`, or `embedding_nodes`. A single FK can't target multiple tables, so we use `source_type`/`target_type` enum columns to indicate which table the UUID refers to. This is the standard relational approach for polymorphic references.

### Why append-only edges?

All edges are immutable for audit trail compliance. When calibration corrects an attribution score, a new `AttributionEdge` row is inserted with `version += 1` and `is_current = True`; the old row is set to `is_current = False`. Metrics queries filter on `is_current = TRUE` (via partial indexes); audit queries reconstruct full history.

### Why `metadata_` instead of `metadata`?

SQLAlchemy reserves `metadata` as a class attribute on `DeclarativeBase`. The Python attribute is named `metadata_` but maps to a `metadata` column in PostgreSQL via `mapped_column("metadata", JSONB, ...)`.

---

## Running the Migration

```bash
cd cortex-engine

# Preview the SQL that will be generated:
alembic upgrade head --sql

# Apply to a live database:
alembic upgrade head

# Rollback:
alembic downgrade 002
```

---

## Future Work

The following compliance engine components build on top of the provenance graph and are not yet implemented:

| Module | File | Purpose |
|--------|------|---------|
| GDPR Deletion Pipeline | `cortex/compliance/gdpr.py` | `gdpr_delete_user()` — 7-step cascading deletion using `compute_user_footprint()` |
| Erasure Verification | `cortex/compliance/verification.py` | Post-deletion verification per Definition 6.4 (orphan edge check, attribution test, vector proximity) |
| Certificate Generation | `cortex/compliance/certificate.py` | Creates `ComplianceCertificate` records with SHA-256 footprint hashes |
| Retention Tiering | `cortex/compliance/retention.py` | Nightly job: warm-tier aggregation (90d), cold-tier archival (2y), partition detach |
| API Routes | `cortex/api/compliance_routes.py` | REST endpoints for deletion requests, footprint queries, certificate retrieval |
