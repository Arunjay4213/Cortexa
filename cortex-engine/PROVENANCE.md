# CortexOS Provenance Graph — Implementation Specification

## Context

This spec captures the design decisions for implementing the Compliance Engine's provenance graph (Section 6 of the Technical Foundations Document). It was developed through a conversation analyzing the product doc, Bloomberg metrics doc, and technical foundations doc, and resolving open design questions.

Place this file at: `cortex-engine/PROVENANCE.md`

---

## 1. Overview

The provenance graph is a directed acyclic graph (DAG) that tracks the full lineage of data through the CortexOS pipeline:

```
interaction → raw_memory → summary → embedding → response
```

Every node and edge is immutable for audit purposes. The graph supports:
- **GDPR cascading deletion** via reachability traversal
- **Hallucination root-cause tracing** via attribution edges
- **Compliance certificate generation** with cryptographic audit logs
- **User data footprint computation** (Definition 6.2 from tech doc)

---

## 2. Node Types

We use **five first-class node types** (expanded from the tech doc's two to properly handle GDPR derived-data requirements):

### 2.1 Interaction Node
```
interaction_node {
    id: UUID
    user_id: str                # originating user
    query: text                 # the user query
    response: text              # the generated response
    timestamp: datetime
    agent_id: str               # which agent processed this
    transaction_cost: float     # Cost(ξ) from Definition 2.3
    metadata: JSONB             # model version, temperature, etc.
}
```

### 2.2 Memory Node
```
memory_node {
    id: UUID
    content: text               # the memory content
    memory_type: enum           # raw | consolidated | critical
    status: enum                # active | archived | deleted | pending_deletion
    shard_id: int               # SISA shard assignment: h(user_id) mod s
    slice_id: int               # SISA slice within shard (creation order)
    created_at: datetime
    created_by_user_id: str     # originating user (for F(u) computation)
    token_count: int            # tokens(m_i) for cost calculations
    criticality: enum           # normal | safety_critical | protected
    metadata: JSONB             # source info, tags, etc.
}
```

### 2.3 Summary Node
A summary is produced when memories are consolidated (Section 5.3). It is a distinct node because it's derived personal data under GDPR.

```
summary_node {
    id: UUID
    content: text               # the consolidated summary text
    source_memory_count: int    # how many memories were consolidated
    created_at: datetime
    method: str                 # "llm_consolidation" | "manual"
    metadata: JSONB
}
```

### 2.4 Embedding Node
Each embedding vector is derived data. Tracking it as a node enables GDPR deletion of vector store entries.

```
embedding_node {
    id: UUID
    vector_ref: str             # pointer to vector in the vector store (e.g., Pinecone ID, pgvector row ID)
    model_version: str          # embedding model used (e.g., "text-embedding-3-small")
    dimensions: int             # dimensionality (e.g., 768, 1536)
    created_at: datetime
    metadata: JSONB
}
```

### 2.5 Response Node
Responses are separate from interactions when we need statement-level granularity. For most purposes, the response is stored inline on the interaction node. Response nodes are created on-demand when ContextCite runs.

```
response_node {
    id: UUID
    interaction_id: UUID        # FK to interaction_node
    statements: JSONB           # list of decomposed statements [{text, index}]
    created_at: datetime
}
```

---

## 3. Edge Types

All edges are **append-only / immutable**. Updated scores produce new versioned edges; old edges are marked superseded but never deleted (for audit trail).

### 3.1 Creation Edge
```
creation_edge {
    id: UUID
    source_id: UUID             # interaction_node.id
    target_id: UUID             # memory_node.id
    created_at: datetime
    metadata: JSONB
}
```
**Cardinality:** One interaction can create multiple memories (one-to-many).

### 3.2 Attribution Edge
```
attribution_edge {
    id: UUID
    source_id: UUID             # memory_node.id
    target_id: UUID             # interaction_node.id
    score: float                # calibrated attribution score (a_i^calibrated)
    score_type: enum            # eas | contextcite | calibrated
    version: int                # monotonically increasing per (source, target) pair
    is_current: bool            # True for latest version only
    created_at: datetime
    metadata: JSONB             # e.g., calibration model version
}
```
**Key design decision:** When calibration corrects a score, a new row is inserted with `version += 1` and `is_current = True`; the old row is set to `is_current = False`. Metrics queries filter on `is_current = True`; audit queries can reconstruct full history.

### 3.3 Derivation Edge
```
derivation_edge {
    id: UUID
    source_id: UUID             # source node (any type)
    source_type: enum           # memory | summary | embedding
    target_id: UUID             # derived node (any type)
    target_type: enum           # memory | summary | embedding
    derivation_type: enum       # consolidation | embedding | re_embedding | summary
    created_at: datetime
    metadata: JSONB             # e.g., which consolidation operation
}
```
**Covers the full chain:**
- memory → summary (consolidation)
- memory → embedding (vector encoding)
- summary → embedding (encoding consolidated text)
- embedding → embedding (re-embedding with new model version)

### 3.4 Statement Attribution Edge (On-Demand)
Only created when ContextCite runs or hallucination tracing triggers.

```
statement_attribution_edge {
    id: UUID
    memory_id: UUID             # memory_node.id
    response_id: UUID           # response_node.id
    statement_index: int        # which statement in the response
    score: float                # A[p,j] from Section 3.6
    created_at: datetime
}
```

---

## 4. Storage Backend: PostgreSQL

### 4.1 Why Postgres, Not a Graph DB

- **SISA alignment:** Table partitioning by `hash(user_id)` maps directly to SISA shards (Definition 6.3). This is a native Postgres feature.
- **F(u) traversal:** `WITH RECURSIVE` CTEs handle the reachability query for user data footprint, scoped to one partition. Fast and well-optimized in Postgres.
- **Transactional consistency:** Provenance writes happen in the same transaction as memory writes. No cross-store consistency issues.
- **Operational simplicity:** One database to manage, not Postgres + Neo4j.
- **Scale:** ~365M attribution edges/year ≈ ~1GB/year at ~30 bytes/edge. Well within Postgres capacity.

For batch graph analytics (multi-hop contradiction detection from Section 4.1.3), materialize subgraphs into igraph/NetworkX. The source of truth stays in Postgres.

### 4.2 Partitioning Strategy

```sql
-- Partition memory_nodes by SISA shard
CREATE TABLE memory_nodes (
    ...
    shard_id INT NOT NULL
) PARTITION BY HASH (shard_id);

-- Create s partitions (e.g., s = 16)
CREATE TABLE memory_nodes_p0 PARTITION OF memory_nodes FOR VALUES WITH (MODULUS 16, REMAINDER 0);
CREATE TABLE memory_nodes_p1 PARTITION OF memory_nodes FOR VALUES WITH (MODULUS 16, REMAINDER 1);
-- ... etc.

-- Attribution edges partitioned by time for retention tiering
CREATE TABLE attribution_edges (
    ...
    created_at TIMESTAMPTZ NOT NULL
) PARTITION BY RANGE (created_at);

-- Monthly partitions
CREATE TABLE attribution_edges_2026_01 PARTITION OF attribution_edges
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
```

### 4.3 Key Indexes

```sql
-- F(u) computation: find all memories for a user
CREATE INDEX idx_memory_nodes_user ON memory_nodes (created_by_user_id);

-- Attribution lookup: given interaction, find all memory contributions
CREATE INDEX idx_attr_edges_target ON attribution_edges (target_id) WHERE is_current = TRUE;

-- Attribution lookup: given memory, find all interactions it influenced
CREATE INDEX idx_attr_edges_source ON attribution_edges (source_id) WHERE is_current = TRUE;

-- Derivation traversal
CREATE INDEX idx_deriv_edges_source ON derivation_edges (source_id);
CREATE INDEX idx_deriv_edges_target ON derivation_edges (target_id);

-- Creation edge lookup
CREATE INDEX idx_creation_edges_source ON creation_edges (source_id);
CREATE INDEX idx_creation_edges_target ON creation_edges (target_id);
```

---

## 5. Core Operations

### 5.1 Record Transaction (Write Path)

On every query-response transaction:

```python
def record_transaction(transaction: Transaction, memories: List[Memory], attribution_scores: List[float]):
    """
    Called after every agent query-response cycle.
    Writes interaction node + attribution edges in a single DB transaction.
    """
    with db.transaction():
        # 1. Create interaction node
        interaction = InteractionNode.create(
            user_id=transaction.user_id,
            query=transaction.query,
            response=transaction.response,
            timestamp=transaction.timestamp,
            agent_id=transaction.agent_id,
            transaction_cost=transaction.cost
        )

        # 2. Create attribution edges (from EAS, calibrated)
        for memory, score in zip(memories, attribution_scores):
            AttributionEdge.create(
                source_id=memory.id,
                target_id=interaction.id,
                score=score,
                score_type='calibrated',
                version=1,
                is_current=True
            )
```

### 5.2 Record Memory Creation

When the agent creates a new memory from an interaction:

```python
def record_memory_creation(interaction_id: UUID, memory: Memory):
    with db.transaction():
        # 1. Create memory node
        mem_node = MemoryNode.create(
            content=memory.content,
            memory_type='raw',
            status='active',
            shard_id=hash(memory.user_id) % NUM_SHARDS,
            slice_id=get_next_slice_id(memory.user_id),
            created_by_user_id=memory.user_id,
            token_count=count_tokens(memory.content)
        )

        # 2. Create creation edge
        CreationEdge.create(
            source_id=interaction_id,
            target_id=mem_node.id
        )

        # 3. Create embedding node + derivation edge
        emb_node = EmbeddingNode.create(
            vector_ref=memory.vector_id,
            model_version=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIM
        )
        DerivationEdge.create(
            source_id=mem_node.id,
            source_type='memory',
            target_id=emb_node.id,
            target_type='embedding',
            derivation_type='embedding'
        )
```

### 5.3 User Data Footprint — F(u) (Definition 6.2)

```sql
-- Recursive CTE to compute F(u): all nodes reachable from user u's interactions
WITH RECURSIVE user_footprint AS (
    -- Base case: all memories directly created by user's interactions
    SELECT ce.target_id AS node_id, 'memory' AS node_type
    FROM creation_edges ce
    JOIN interaction_nodes i ON ce.source_id = i.id
    WHERE i.user_id = :user_id

    UNION

    -- Recursive case: all nodes derived from those memories
    SELECT de.target_id AS node_id, de.target_type AS node_type
    FROM derivation_edges de
    JOIN user_footprint uf ON de.source_id = uf.node_id
)
SELECT * FROM user_footprint;
```

### 5.4 Influence Footprint — I(u) (Definition 6.2, Eq. 53)

```sql
-- Find all interactions that were influenced by user u's memories
SELECT DISTINCT ae.target_id AS influenced_interaction_id
FROM attribution_edges ae
JOIN user_footprint uf ON ae.source_id = uf.node_id
WHERE ae.is_current = TRUE
  AND ae.score > 0;
```

### 5.5 GDPR Cascading Deletion

```python
def gdpr_delete_user(user_id: str):
    """
    GDPR Article 17 deletion.
    1. Compute F(u)
    2. Handle consolidated memories with mixed ownership
    3. Delete or regenerate
    4. Verify erasure
    5. Generate compliance certificate
    """
    with db.transaction():
        # Step 1: Compute footprint
        footprint = compute_user_footprint(user_id)

        # Step 2: Handle consolidated memories with mixed ownership
        for node in footprint.memory_nodes:
            if node.memory_type == 'consolidated':
                source_memories = get_derivation_sources(node.id)
                non_user_sources = [m for m in source_memories if m.created_by_user_id != user_id]
                if non_user_sources:
                    # Regenerate consolidated memory without user's data
                    regenerate_consolidation(node, exclude_user=user_id)
                else:
                    # All sources belong to user, safe to delete entirely
                    mark_for_deletion(node)
            else:
                mark_for_deletion(node)

        # Step 3: Delete embedding nodes (remove from vector store)
        for node in footprint.embedding_nodes:
            vector_store.delete(node.vector_ref)
            mark_for_deletion(node)

        # Step 4: Mark attribution edges as deleted (don't remove — audit trail)
        for edge in footprint.attribution_edges:
            edge.update(status='deleted_gdpr')

        # Step 5: Soft-delete memory nodes (30-day grace period per product doc)
        for node in footprint.memory_nodes:
            node.update(status='pending_deletion', deletion_scheduled_at=now() + timedelta(days=30))

        # Step 6: Generate compliance certificate
        cert = ComplianceCertificate.create(
            user_id=user_id,
            footprint_snapshot=footprint.serialize(),
            deletion_timestamp=now(),
            certificate_hash=sha256(footprint.serialize()),
            nodes_deleted=len(footprint.all_nodes),
            edges_affected=len(footprint.all_edges)
        )

    # Step 7: Post-deletion verification (async, Section 6.3)
    schedule_erasure_verification(user_id, cert.id)
```

### 5.6 Erasure Verification (Definition 6.4)

```python
def verify_erasure(user_id: str, cert_id: UUID):
    """
    Post-deletion verification per Section 6.3.
    1. No active derivation edges from deleted nodes
    2. Zero attribution on random query sample
    3. No vector similarity to deleted embeddings
    """
    deleted_embeddings = get_deleted_embedding_vectors(user_id)

    # Check 1: No derivation edges from deleted to active nodes
    orphan_edges = db.query("""
        SELECT de.* FROM derivation_edges de
        JOIN memory_nodes mn ON de.source_id = mn.id
        WHERE mn.created_by_user_id = :user_id
          AND mn.status IN ('deleted', 'pending_deletion')
          AND de.target_id IN (SELECT id FROM memory_nodes WHERE status = 'active')
    """, user_id=user_id)
    assert len(orphan_edges) == 0, "Derivation edges to active nodes still exist"

    # Check 2: Random query attribution test
    test_queries = sample_recent_queries(n=100)
    for q in test_queries:
        scores = run_attribution(q)
        for mem_id, score in scores.items():
            if mem_id in footprint.memory_ids:
                assert score == 0, f"Deleted memory {mem_id} still has attribution"

    # Check 3: Vector proximity check (Eq. 54)
    for emb in deleted_embeddings:
        nearest = vector_store.search(emb, top_k=1)
        similarity = cosine_similarity(emb, nearest.vector)
        assert similarity < ERASURE_THRESHOLD, f"Vector too similar to deleted embedding"

    # Log verification result
    ComplianceCertificate.update(cert_id, verified=True, verified_at=now())
```

---

## 6. Retention Policy (Tiered)

Mirrors the lifecycle engine's hot/warm/cold tiers:

| Tier | Age | What's Kept | What's Pruned |
|------|-----|-------------|---------------|
| **Hot** | 0–90 days | All nodes, all edges, all edge versions | Nothing |
| **Warm** | 90 days – 2 years | Creation + derivation edges, aggregated attribution stats per memory, interaction metadata | Individual attribution edge versions (keep only `is_current`), statement attribution edges |
| **Cold** | 2+ years | Creation + derivation edges only, compliance certificates | Attribution edges aggregated to per-memory lifetime stats, interaction response text |

**Never pruned (while user account exists):**
- Creation edges (needed for F(u))
- Derivation edges (needed for F(u))
- Compliance certificates

### Retention Implementation

```python
# Run nightly
def tier_old_data():
    # Warm tier: aggregate attribution edges older than 90 days
    db.execute("""
        INSERT INTO attribution_aggregates (memory_id, period_start, period_end, mean_score, retrieval_count)
        SELECT source_id, date_trunc('month', created_at), date_trunc('month', created_at) + interval '1 month',
               avg(score), count(*)
        FROM attribution_edges
        WHERE created_at < now() - interval '90 days'
          AND is_current = TRUE
        GROUP BY source_id, date_trunc('month', created_at)
        ON CONFLICT DO NOTHING;

        -- Drop non-current edge versions
        DELETE FROM attribution_edges
        WHERE created_at < now() - interval '90 days'
          AND is_current = FALSE;
    """)

    # Cold tier: archive to object storage
    # (implemented as partition detach + export + S3 upload)
```

---

## 7. Compliance Certificate Schema

```python
compliance_certificate {
    id: UUID
    user_id: str
    request_type: enum          # gdpr_deletion | audit_request | data_export
    footprint_snapshot: JSONB   # serialized F(u) at time of request
    nodes_deleted: int
    edges_affected: int
    deletion_timestamp: datetime
    grace_period_end: datetime  # deletion_timestamp + 30 days
    hard_deleted_at: datetime   # NULL until grace period expires
    verified: bool
    verified_at: datetime
    certificate_hash: str       # SHA-256 of footprint_snapshot
    metadata: JSONB
}
```

---

## 8. Integration Points with Other Engines

### Attribution Engine (Section 3)
- Every calibrated attribution score → write `attribution_edge`
- ContextCite results → write `statement_attribution_edge` + `response_node`
- Calibration corrections → new `attribution_edge` version

### Health Monitor (Section 4)
- Contradiction detection reads memory nodes + derivation edges to check for conflicting info
- Staleness scoring reads attribution edges to compute `τ_last(m_i)`

### Lifecycle Engine (Section 5)
- Memory consolidation → create `summary_node` + `derivation_edges` from source memories
- Auto-archive → update `memory_node.status`, do NOT delete provenance edges
- Memory budget optimization reads attribution aggregates

### P&L Framework (Section 7)
- Revenue computation reads `attribution_edges` (is_current) + quality signals
- Carrying cost reads `memory_node.token_count` + retrieval frequency from attribution edges
- Sharpe ratio computed from attribution edge time series

---

## 9. Repo Location

Implementation goes in:

```
cortex-engine/
├── cortex/
│   ├── db/
│   │   ├── models/
│   │   │   ├── provenance.py      # SQLAlchemy models for all node/edge types
│   │   │   └── compliance.py      # ComplianceCertificate model
│   │   └── migrations/
│   │       └── versions/
│   │           └── xxx_add_provenance_graph.py  # Alembic migration
│   ├── compliance/
│   │   ├── provenance.py          # ProvenanceGraph class (F(u), I(u), traversals)
│   │   ├── gdpr.py                # GDPR deletion pipeline
│   │   ├── verification.py        # Erasure verification (Definition 6.4)
│   │   ├── certificate.py         # Compliance certificate generation
│   │   └── retention.py           # Tiered retention policy
│   └── api/
│       └── compliance_routes.py   # API endpoints for deletion requests, audit
└── tests/
    └── test_provenance.py         # Tests for graph operations
```
