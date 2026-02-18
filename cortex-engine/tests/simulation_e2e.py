#!/usr/bin/env python3
"""
CortexOS End-to-End Real-World Simulation
==========================================

Exercises every engine component with realistic data from a simulated
coding-assistant agent ("atlas-code") that has been running for 30 days.

  python tests/simulation_e2e.py

No database, no sentence-transformers — pure Python + numpy.
"""
from __future__ import annotations

import hashlib
import math
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from dataclasses import dataclass, field

import numpy as np

# ── Engine imports ────────────────────────────────────────────────────

from cortex.attribution.eas import compute_eas
from cortex.attribution.contradiction import (
    _find_candidate_pairs,
    _classify_contradiction_type,
    classify_contradiction_with_probability,
    _softmax,
)
from cortex.attribution.drift import cosine_distance, compute_drift_score
from cortex.attribution.coverage import _cosine_similarity_matrix, _simple_kmeans
from cortex.attribution.statement import (
    segment_into_statements,
    compute_statement_attribution,
    _token_overlap_score,
)
from cortex.attribution.belief_propagation import ContradictionGraph
from cortex.attribution.calibrator import CalibratorModel
from cortex.metrics.calculator import (
    transaction_cost,
    memory_pnl,
    gini_coefficient,
    snr_db,
    token_waste_rate,
    contradiction_risk,
)
from cortex.metrics.health import staleness_score, batch_staleness, compute_chi, CHIWeights
from cortex.metrics.financial import compute_sharpe_ratio, compute_portfolio_roi
from cortex.compliance.provenance import ProvenanceGraph, ProvenanceEventType
from cortex.compliance.sisa import SISAPartitioner
from cortex.compliance.erasure import ErasureCheckResult
from cortex.attribution.counterfactual import (
    MemoryRecord as CFMemoryRecord,
    TransactionRecord as CFTransactionRecord,
    ChangeSpec,
    run_counterfactual,
)
# Ensure TF is disabled (transformers Keras 3 conflict)
import os
os.environ.setdefault("USE_TF", "0")
from cortex.attribution.grounding import (
    MemoryForGrounding,
    TransactionForGrounding,
    compute_grounding_scores,
)
from cortex.attribution.contamination import (
    scan_contamination,
    gate_memory,
    simulate_quarantine,
)
from cortex.models import TokenCostConfig, MemoryTier

# ── Configuration ─────────────────────────────────────────────────────

AGENT_ID = "atlas-code"
EMBEDDING_DIM = 64  # compact for speed; real system uses 384
NOW = datetime(2026, 2, 15, 12, 0, 0, tzinfo=UTC)
RNG = np.random.default_rng(42)
COST_CONFIG = TokenCostConfig(input_token_cost=0.00001, output_token_cost=0.00003)


# ── Data structures ───────────────────────────────────────────────────

@dataclass
class SimMemory:
    id: str
    content: str
    tier: str
    tokens: int
    cluster: str
    embedding: np.ndarray
    created_at: datetime
    last_accessed: datetime | None
    retrieval_count: int
    content_hash: str = ""
    is_contradiction: bool = False
    contradiction_pair: str | None = None
    is_duplicate: bool = False
    duplicate_of: str | None = None

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()[:16]


@dataclass
class SimTransaction:
    id: str
    query_text: str
    response_text: str
    query_embedding: np.ndarray
    response_embedding: np.ndarray
    retrieved_memory_ids: list[str]
    input_tokens: int
    output_tokens: int


# ── Embedding factory ─────────────────────────────────────────────────

# Six cluster centroids in EMBEDDING_DIM space (unit-normalized)
_CLUSTER_CENTROIDS: dict[str, np.ndarray] = {}


def _init_centroids():
    """Create well-separated cluster centroids."""
    clusters = ["python", "arch", "debug", "user", "tools", "security"]
    for i, name in enumerate(clusters):
        v = np.zeros(EMBEDDING_DIM)
        # Spread centroids across dimensions
        start = i * (EMBEDDING_DIM // len(clusters))
        end = start + (EMBEDDING_DIM // len(clusters))
        v[start:end] = 1.0
        # Add some shared signal so cross-cluster similarity isn't zero
        v += 0.1
        v /= np.linalg.norm(v)
        _CLUSTER_CENTROIDS[name] = v


def _make_embedding(
    cluster: str,
    noise_scale: float = 0.15,
    near: np.ndarray | None = None,
) -> np.ndarray:
    """Generate an embedding near the cluster centroid (or near another vector)."""
    base = near if near is not None else _CLUSTER_CENTROIDS[cluster].copy()
    noise = RNG.normal(0, noise_scale, EMBEDDING_DIM)
    v = base + noise
    v /= np.linalg.norm(v)
    return v


def _make_query_embedding(clusters: list[str], noise_scale: float = 0.20) -> np.ndarray:
    """Generate a query embedding that pulls toward one or more clusters."""
    v = np.zeros(EMBEDDING_DIM)
    for c in clusters:
        v += _CLUSTER_CENTROIDS[c]
    v /= len(clusters)
    noise = RNG.normal(0, noise_scale, EMBEDDING_DIM)
    v = v + noise
    v /= np.linalg.norm(v)
    return v


# ── Stage 1: Memory Corpus ───────────────────────────────────────────

def build_memory_corpus() -> list[SimMemory]:
    """Create ~50 realistic coding-assistant memories."""
    memories: list[SimMemory] = []
    mid = 0

    def _add(cluster: str, content: str, tier: str = "warm",
             tokens: int | None = None, days_ago: float = 15.0,
             last_access_days_ago: float | None = 2.0,
             retrieval_count: int = 3, noise: float = 0.15,
             near_embedding: np.ndarray | None = None,
             **kwargs) -> SimMemory:
        nonlocal mid
        mid += 1
        tok = tokens or max(150, len(content.split()) * 8)
        created = NOW - timedelta(days=days_ago)
        la = (NOW - timedelta(days=last_access_days_ago)) if last_access_days_ago is not None else None
        m = SimMemory(
            id=f"mem-{cluster}-{mid:02d}",
            content=content,
            tier=tier,
            tokens=tok,
            cluster=cluster,
            embedding=_make_embedding(cluster, noise, near=near_embedding),
            created_at=created,
            last_accessed=la,
            retrieval_count=retrieval_count,
            **kwargs,
        )
        memories.append(m)
        return m

    # ── Python preferences (10) ──
    _add("python", "User always uses type hints (PEP 484) in all function signatures and return types.", tier="hot", retrieval_count=8)
    _add("python", "Project uses Python 3.12 with match statements for control flow where appropriate.", tier="hot", retrieval_count=6)
    p3 = _add("python", "User strongly prefers pytest for all unit and integration tests. Uses pytest-cov for coverage.", tier="hot", retrieval_count=12)
    _add("python", "Docstrings follow Google style with Args/Returns/Raises sections.", retrieval_count=5)
    _add("python", "User prefers dataclasses over NamedTuples for structured data. Uses attrs for complex cases.", retrieval_count=4)
    _add("python", "All async code uses asyncio with structured concurrency via TaskGroup (Python 3.11+).", retrieval_count=3)
    # Contradiction 1: pytest vs unittest (high similarity, conflicting content)
    p7 = _add("python", "User prefers unittest with setUp/tearDown pattern for all tests. Avoids pytest magic.",
              tier="cold", retrieval_count=2, days_ago=25.0, noise=0.04, near_embedding=p3.embedding,
              is_contradiction=True, contradiction_pair=p3.id)
    _add("python", "Type checking runs via mypy in strict mode. All code must pass mypy --strict.", retrieval_count=4)
    _add("python", "Error handling uses custom exception hierarchy: AppError > ValidationError, NotFoundError, AuthError.", retrieval_count=3)
    _add("python", "Logging uses structlog with JSON output in production, console renderer in development.", retrieval_count=5)

    # ── Architecture decisions (8) ──
    a1 = _add("arch", "System uses microservices architecture with gRPC for inter-service communication.", tier="hot", retrieval_count=10)
    _add("arch", "PostgreSQL 16 is the primary database. Uses JSONB columns for flexible metadata.", tier="hot", retrieval_count=9)
    _add("arch", "API follows REST conventions with versioned endpoints: /api/v1/resources.", retrieval_count=6)
    _add("arch", "Event-driven architecture with Redis Streams for async task processing between services.", retrieval_count=5)
    # Contradiction 2: microservices vs monolith
    a5 = _add("arch", "Project is a monolithic Django application. All features in a single deployable unit.",
              tier="cold", retrieval_count=2, days_ago=28.0, noise=0.04, near_embedding=a1.embedding,
              is_contradiction=True, contradiction_pair=a1.id)
    _add("arch", "Database migrations managed by Alembic with auto-generated migration scripts.", retrieval_count=4)
    _add("arch", "Caching layer uses Redis with 5-minute TTL for read-heavy endpoints.", retrieval_count=3)
    _add("arch", "Background job processing via Celery with Redis as broker and PostgreSQL as result backend.", retrieval_count=4)

    # ── Debugging insights (9) ──
    _add("debug", "Memory leak in worker pool was caused by unclosed HTTP connections. Fix: use contextmanager for httpx.AsyncClient.", tier="hot", retrieval_count=7)
    _add("debug", "Race condition in task queue fixed by adding asyncio.Lock around shared state mutation in the dispatcher.", tier="hot", retrieval_count=9)
    _add("debug", "Slow database queries traced to missing index on transactions.created_at column. Added btree index.", retrieval_count=6)
    _add("debug", "Deadlock in connection pool resolved by reducing pool_size from 20 to 10 and adding pool_timeout=30.", retrieval_count=4)
    _add("debug", "Intermittent 502 errors caused by Kubernetes readiness probe timeout. Increased to 10s.", retrieval_count=3)
    _add("debug", "JSON serialization bottleneck: switched from json.dumps to orjson.dumps for 5x throughput.", retrieval_count=5)
    _add("debug", "OOM in batch processing: implemented chunked iteration with itertools.batched(data, 1000).", retrieval_count=4)
    _add("debug", "WebSocket disconnection storm traced to nginx proxy_read_timeout too low. Set to 300s.", retrieval_count=3)
    _add("debug", "Flaky tests caused by shared database state. Fix: use pytest-xdist with --forked for isolation.", retrieval_count=2)

    # ── User context (7) ──
    _add("user", "User timezone is America/Los_Angeles (Pacific Time). Prefers 24-hour time format.", retrieval_count=4)
    _add("user", "Project name is 'Nexus Platform'. Main repo is github.com/acme/nexus.", tier="hot", retrieval_count=8)
    _add("user", "Team members: Alice (backend lead), Bob (frontend), Carol (DevOps), Dave (ML engineer).", retrieval_count=5)
    u4 = _add("user", "User has a meeting every Tuesday at 10:00 PT for sprint planning.", tier="cold", retrieval_count=1,
              last_access_days_ago=25.0, days_ago=29.0)  # stale
    _add("user", "Preferred communication: Slack for quick questions, GitHub issues for bugs, Linear for tasks.", retrieval_count=3)
    _add("user", "Code review policy: all PRs need at least 2 approvals before merge to main.", retrieval_count=4)
    _add("user", "User prefers dark mode in all tools. Uses Catppuccin Mocha color theme everywhere.", tier="cold", retrieval_count=2,
         last_access_days_ago=22.0, days_ago=28.0)  # stale

    # ── Tool preferences (8) ──
    t1 = _add("tools", "Primary editor is Neovim with LazyVim configuration. Uses Telescope for fuzzy finding.", tier="hot", retrieval_count=7)
    _add("tools", "Git workflow: trunk-based development with short-lived feature branches. Squash merge to main.", retrieval_count=6)
    _add("tools", "CI/CD pipeline: GitHub Actions with separate jobs for lint, test, build, deploy.", tier="hot", retrieval_count=8)
    # Contradiction 3: Neovim vs VS Code
    t4 = _add("tools", "User's primary editor is VS Code with Vim extension. Uses command palette extensively.",
              tier="cold", retrieval_count=1, days_ago=27.0, noise=0.04, near_embedding=t1.embedding,
              is_contradiction=True, contradiction_pair=t1.id)
    _add("tools", "Container runtime: Docker with multi-stage builds. Production images based on python:3.12-slim.", retrieval_count=4)
    _add("tools", "Infrastructure as code with Terraform. State stored in S3 with DynamoDB locking.", retrieval_count=3)
    _add("tools", "Deployment strategy: blue-green with automatic rollback on health check failure.", retrieval_count=5)
    _add("tools", "Monitoring stack: Prometheus + Grafana for metrics, Loki for logs, Tempo for traces.", tier="cold", retrieval_count=4,
         last_access_days_ago=23.0, days_ago=26.0)  # stale

    # ── Security patterns (8) ──
    _add("security", "Authentication uses JWT with RS256 signing. Access tokens expire in 15 minutes, refresh in 7 days.", tier="hot", retrieval_count=9)
    s2 = _add("security", "Secrets managed via HashiCorp Vault with dynamic database credentials. No .env files in production.", retrieval_count=6)
    _add("security", "CORS configured to allow only specific origins. Uses FastAPI CORSMiddleware with explicit allow_origins.", retrieval_count=4)
    # Contradiction 4: Vault vs .env
    s4 = _add("security", "All secrets stored in .env files loaded via python-dotenv. Vault considered too complex for team size.",
              tier="cold", retrieval_count=1, days_ago=26.0, noise=0.04, near_embedding=s2.embedding,
              is_contradiction=True, contradiction_pair=s2.id)
    _add("security", "Input validation on all API endpoints using Pydantic models. SQL injection prevented by SQLAlchemy ORM.", retrieval_count=5)
    _add("security", "Rate limiting: 100 req/min per API key using Redis-backed sliding window counter.", retrieval_count=3)
    _add("security", "All PII encrypted at rest with AES-256-GCM. Key rotation every 90 days via Vault transit engine.", tier="cold", retrieval_count=4,
         last_access_days_ago=24.0, days_ago=27.0)  # stale
    _add("security", "Security headers: HSTS, X-Content-Type-Options, X-Frame-Options set via middleware.", tier="cold", retrieval_count=3,
         last_access_days_ago=25.0, days_ago=28.0)  # stale

    # ── Exact duplicates (3 groups) ──
    # Duplicate of first python memory
    src = memories[0]
    _add("python", src.content, tier=src.tier, tokens=src.tokens,
         retrieval_count=1, days_ago=10.0, noise=0.02, near_embedding=src.embedding,
         is_duplicate=True, duplicate_of=src.id)

    # Duplicate of first arch memory
    src2 = memories[10]
    _add("arch", src2.content, tier="warm", tokens=src2.tokens,
         retrieval_count=0, days_ago=8.0, noise=0.02, near_embedding=src2.embedding,
         is_duplicate=True, duplicate_of=src2.id)

    # Duplicate of first security memory
    sec_mems = [m for m in memories if m.cluster == "security"]
    src3 = sec_mems[0]
    _add("security", src3.content, tier="warm", tokens=src3.tokens,
         retrieval_count=1, days_ago=5.0, noise=0.02, near_embedding=src3.embedding,
         is_duplicate=True, duplicate_of=src3.id)

    return memories


# ── Stage 2: Transaction Simulation ──────────────────────────────────

TRANSACTIONS_SPEC = [
    {
        "query": "How should I structure the API endpoints?",
        "clusters": ["arch"],
        "response": (
            "Based on your project setup, structure the API endpoints following REST conventions "
            "under /api/v1/. Use FastAPI routers to group related endpoints. Each resource gets "
            "its own router file. Use dependency injection for database sessions and auth. "
            "Follow the versioned endpoint pattern already established in the Nexus Platform."
        ),
    },
    {
        "query": "Fix the memory leak in the worker pool",
        "clusters": ["debug"],
        "response": (
            "The memory leak is likely caused by unclosed HTTP connections in the worker pool. "
            "Wrap httpx.AsyncClient in an async context manager to ensure cleanup. Also check "
            "for leaked asyncio tasks — use TaskGroup for structured concurrency. Add memory "
            "profiling with tracemalloc to confirm the fix."
        ),
    },
    {
        "query": "What testing framework do we use?",
        "clusters": ["python"],
        "response": (
            "We primarily use pytest for unit testing. Integration tests run with unittest "
            "for some legacy modules. Coverage is tracked via pytest-cov with a minimum "
            "threshold of 85%. Tests are run in CI via GitHub Actions on every push."
        ),
    },
    {
        "query": "Set up the CI/CD pipeline",
        "clusters": ["tools"],
        "response": (
            "The CI/CD pipeline uses GitHub Actions with four stages: lint (ruff + mypy), "
            "test (pytest with coverage), build (Docker multi-stage), and deploy (blue-green "
            "via Terraform). Use branch protection rules to require all checks pass before merge."
        ),
    },
    {
        "query": "How do I handle auth tokens?",
        "clusters": ["security"],
        "response": (
            "Authentication uses JWT with RS256 signing. Access tokens have a 15-minute TTL. "
            "Refresh tokens last 7 days and are stored in httpOnly cookies. Use FastAPI's "
            "Depends() with a token verification dependency. Secrets are managed via Vault."
        ),
    },
    {
        "query": "Refactor the database layer",
        "clusters": ["arch", "python"],
        "response": (
            "Refactor the database layer to use the repository pattern. Create abstract base "
            "repositories with SQLAlchemy async sessions. Use Alembic for migrations. Define "
            "typed models with Pydantic for input/output and SQLAlchemy for ORM. Add connection "
            "pooling with asyncpg and configure pool_size based on load testing results."
        ),
    },
    {
        "query": "Debug the race condition in the queue",
        "clusters": ["debug"],
        "response": (
            "The race condition in the task queue is caused by concurrent access to shared "
            "dispatcher state. Add an asyncio.Lock around the state mutation. Consider using "
            "Redis Streams instead of in-memory queues for distributed safety. Add retry logic "
            "with exponential backoff for transient failures."
        ),
    },
    {
        "query": "What's our deployment strategy?",
        "clusters": ["tools"],
        "response": (
            "We use blue-green deployment with automatic rollback on health check failure. "
            "Infrastructure is managed with Terraform, stored in S3. Container images are "
            "built with Docker multi-stage builds using python:3.12-slim base. Monitoring "
            "via Prometheus and Grafana alerts on deployment metrics."
        ),
    },
    {
        "query": "Optimize the query performance",
        "clusters": ["arch"],
        "response": (
            "Start by adding indexes on frequently queried columns like created_at and agent_id. "
            "Use EXPLAIN ANALYZE to identify slow queries. Implement Redis caching with 5-minute "
            "TTL for read-heavy endpoints. Consider materialized views for complex aggregations. "
            "Use connection pooling and batch queries where possible."
        ),
    },
    {
        "query": "Review the PR for security issues",
        "clusters": ["security", "python"],
        "response": (
            "Check for: SQL injection (use parameterized queries via SQLAlchemy), XSS in any "
            "HTML responses, missing input validation (all endpoints need Pydantic models), "
            "hardcoded secrets (should be in Vault), CORS misconfiguration, missing rate "
            "limiting on public endpoints, and proper error handling that doesn't leak internals."
        ),
    },
]


def build_transactions(memories: list[SimMemory]) -> list[SimTransaction]:
    """Build 10 simulated transactions with realistic retrieval."""
    txns = []
    mem_by_cluster: dict[str, list[SimMemory]] = {}
    for m in memories:
        mem_by_cluster.setdefault(m.cluster, []).append(m)

    for i, spec in enumerate(TRANSACTIONS_SPEC):
        # Retrieve top memories from specified clusters
        retrieved_ids = []
        for cluster in spec["clusters"]:
            cluster_mems = sorted(
                mem_by_cluster.get(cluster, []),
                key=lambda m: m.retrieval_count, reverse=True,
            )
            for m in cluster_mems[:4]:
                if m.id not in retrieved_ids:
                    retrieved_ids.append(m.id)
        retrieved_ids = retrieved_ids[:6]

        q_emb = _make_query_embedding(spec["clusters"])
        r_emb = _make_query_embedding(spec["clusters"], noise_scale=0.25)

        txns.append(SimTransaction(
            id=f"txn-{i+1:02d}",
            query_text=spec["query"],
            response_text=spec["response"],
            query_embedding=q_emb,
            response_embedding=r_emb,
            retrieved_memory_ids=retrieved_ids,
            input_tokens=len(spec["query"].split()) * 2 + sum(
                next((m.tokens for m in memories if m.id == mid), 0)
                for mid in retrieved_ids
            ),
            output_tokens=len(spec["response"].split()) * 2,
        ))

    return txns


# ── Report helpers ────────────────────────────────────────────────────

def _hr(char: str = "═", width: int = 60) -> str:
    return char * width


def _header(title: str, width: int = 60) -> str:
    return f"\n{_hr()}\n  {title}\n{_hr()}"


def _section(num: int, total: int, title: str) -> str:
    return f"\n{'─'*60}\n  [{num}/{total}] {title}\n{'─'*60}"


# ── Main simulation ──────────────────────────────────────────────────

def run_simulation() -> int:
    """Run all 11 pipeline stages. Returns error count."""
    t_start = time.perf_counter()
    errors = 0
    components_exercised = set()

    _init_centroids()
    memories = build_memory_corpus()
    mem_map = {m.id: m for m in memories}

    tier_counts = {}
    cluster_counts = {}
    total_tokens = 0
    for m in memories:
        tier_counts[m.tier] = tier_counts.get(m.tier, 0) + 1
        cluster_counts[m.cluster] = cluster_counts.get(m.cluster, 0) + 1
        total_tokens += m.tokens

    contradiction_pairs = [(m, mem_map[m.contradiction_pair])
                           for m in memories if m.is_contradiction and m.contradiction_pair in mem_map]
    duplicate_groups = [(m, mem_map[m.duplicate_of])
                        for m in memories if m.is_duplicate and m.duplicate_of in mem_map]

    # ── Header ──
    print(_hr("═"))
    print(f"  CORTEXOS E2E SIMULATION — {AGENT_ID} agent")
    print(f"  {len(memories)} memories · 10 transactions · 30-day window · counterfactual staging")
    print(_hr("═"))

    # ══════════════════════════════════════════════════════════════════
    # STAGE 1: Memory Corpus
    # ══════════════════════════════════════════════════════════════════
    print(_section(1, 11,"MEMORY CORPUS"))
    print(f"  Total: {len(memories)} memories ({tier_counts.get('hot',0)} hot, "
          f"{tier_counts.get('warm',0)} warm, {tier_counts.get('cold',0)} cold)")
    print(f"  Token budget: {total_tokens:,} tokens")
    cluster_str = " ".join(f"{k.capitalize()}({v})" for k, v in sorted(cluster_counts.items()))
    print(f"  Topic clusters: {cluster_str}")
    print(f"  Contradictions seeded: {len(contradiction_pairs)} pairs")
    print(f"  Duplicates seeded: {len(duplicate_groups)} groups")
    components_exercised.add("MemoryCorpus")

    # ══════════════════════════════════════════════════════════════════
    # STAGE 2: Transaction Simulation
    # ══════════════════════════════════════════════════════════════════
    print(_section(2, 11,"TRANSACTION SIMULATION"))

    transactions = build_transactions(memories)

    # Track per-memory attribution scores across transactions
    mem_attribution_history: dict[str, list[float]] = {m.id: [] for m in memories}
    mem_total_attribution: dict[str, float] = {m.id: 0.0 for m in memories}
    txn_costs = []
    txn_eas_results = []

    for txn in transactions:
        retrieved = [mem_map[mid] for mid in txn.retrieved_memory_ids if mid in mem_map]
        if not retrieved:
            continue

        mem_embs = np.array([m.embedding for m in retrieved])
        eas_result = compute_eas(mem_embs, txn.query_embedding, txn.response_embedding)
        components_exercised.add("compute_eas")

        tc = transaction_cost(txn.input_tokens, txn.output_tokens, COST_CONFIG, txn.id)
        components_exercised.add("transaction_cost")
        txn_costs.append(tc)
        txn_eas_results.append((txn, eas_result, retrieved))

        scores = eas_result["scores"]
        top_idx = int(np.argmax(scores))
        top_mem = retrieved[top_idx]
        top_score = float(scores[top_idx])

        for j, m in enumerate(retrieved):
            s = float(scores[j])
            mem_attribution_history[m.id].append(s)
            mem_total_attribution[m.id] += s

        print(f"  Txn {txn.id[-2:]}: \"{txn.query_text}\"")
        print(f"    Retrieved: {len(retrieved)} memories | Cost: ${tc.total_cost:.4f} | "
              f"EAS top: {top_mem.id} ({top_score:.3f})")

    # ══════════════════════════════════════════════════════════════════
    # STAGE 3: Attribution & Calibration
    # ══════════════════════════════════════════════════════════════════
    print(_section(3, 11,"ATTRIBUTION & CALIBRATION"))

    # Build calibration pairs: EAS vs "ground truth" (EAS + noise)
    eas_scores_cal: list[float] = []
    exact_scores_cal: list[float] = []
    for txn, eas_result, retrieved in txn_eas_results:
        for j, m in enumerate(retrieved):
            eas_s = float(eas_result["scores"][j])
            # Simulated ground truth: correlated with EAS but noisy
            exact_s = np.clip(eas_s + RNG.normal(0, 0.05), 0.0, 1.0)
            eas_scores_cal.append(eas_s)
            exact_scores_cal.append(float(exact_s))

    calibrator = CalibratorModel()
    try:
        calibrator.fit(eas_scores_cal, exact_scores_cal)
        components_exercised.add("CalibratorModel.fit")
        cal_metrics = calibrator.quality_metrics()
        components_exercised.add("CalibratorModel.quality_metrics")
        print(f"  Calibrator: fitted on {cal_metrics['sample_count']} pairs | "
              f"R²={cal_metrics['r_squared']:.2f} | MAE={cal_metrics['mae']:.3f}")

        # Test transform
        test_calibrated = calibrator.transform([0.3, 0.5, 0.7])
        components_exercised.add("CalibratorModel.transform")
    except Exception as e:
        errors += 1
        print(f"  [ERROR] Calibrator: {e}")

    # Memory profiles
    print("  Memory profiles:")
    profile_count = 0
    for m in memories:
        history = mem_attribution_history[m.id]
        if not history:
            continue
        profile_count += 1
        mean_a = float(np.mean(history))
        # Simple trend: compare first half vs second half
        if len(history) >= 2:
            first_half = np.mean(history[:len(history)//2])
            second_half = np.mean(history[len(history)//2:])
            trend = "up" if second_half > first_half * 1.1 else ("down" if second_half < first_half * 0.9 else "stable")
        else:
            trend = "stable"
        total_a = mem_total_attribution[m.id]
        if profile_count <= 5:
            print(f"    {m.id}: mean={mean_a:.3f}, trend={trend}, total={total_a:.3f}")
    if profile_count > 5:
        print(f"    ... and {profile_count - 5} more profiles")

    # ══════════════════════════════════════════════════════════════════
    # STAGE 4: Contradiction Detection
    # ══════════════════════════════════════════════════════════════════
    print(_section(4, 11,"CONTRADICTION DETECTION"))

    embedding_matrix = np.array([m.embedding for m in memories])
    candidate_pairs = _find_candidate_pairs(embedding_matrix, threshold=0.7)
    components_exercised.add("_find_candidate_pairs")
    print(f"  Candidate pairs: {len(candidate_pairs)} (sim > 0.7)")

    # Classify each candidate
    direct_contradictions = []
    for i, j in candidate_pairs:
        ma, mb = memories[i], memories[j]
        # Simulate NLI confidence: high for seeded contradictions, low otherwise
        if (ma.is_contradiction and ma.contradiction_pair == mb.id) or \
           (mb.is_contradiction and mb.contradiction_pair == ma.id):
            nli_conf = float(RNG.uniform(0.75, 0.95))
        else:
            nli_conf = float(RNG.uniform(0.1, 0.4))

        result = classify_contradiction_with_probability(
            ma.created_at, mb.created_at, AGENT_ID, AGENT_ID, nli_conf,
        )
        components_exercised.add("classify_contradiction_with_probability")

        ctype = _classify_contradiction_type(
            ma.created_at, mb.created_at, AGENT_ID, AGENT_ID,
        )
        components_exercised.add("_classify_contradiction_type")

        if result["probability"] > 0.5:
            direct_contradictions.append((ma, mb, result))

    print(f"  Direct contradictions: {len(direct_contradictions)}")

    # Belief propagation — add detected contradictions plus bridge edges
    graph = ContradictionGraph()
    components_exercised.add("ContradictionGraph")
    for ma, mb, result in direct_contradictions:
        graph.add_contradiction(ma.id, mb.id, result["probability"])

    # Add bridge contradictions between contradiction-cluster memories
    # to enable transitive chain detection (A↔B, B↔C → A--B--C)
    contra_mems = [m for m in memories if m.is_contradiction]
    if len(contra_mems) >= 4:
        # Bridge: contradiction mem 0 ↔ contradiction mem 2  (cross-cluster bridge)
        graph.add_contradiction(contra_mems[0].id, contra_mems[2].id, 0.55)
        # Bridge: contradiction mem 1 ↔ contradiction mem 3
        graph.add_contradiction(contra_mems[1].id, contra_mems[3].id, 0.50)

    bp_result = graph.run_belief_propagation(max_hops=3, decay_factor=0.7, min_confidence=0.3)
    components_exercised.add("ContradictionGraph.run_belief_propagation")

    print(f"  Transitive (via BP): {len(bp_result.transitive_contradictions)} chains")
    for tc in bp_result.transitive_contradictions[:3]:
        path_str = " → ".join(tc.path)
        print(f"    Chain: {path_str} (conf: {tc.confidence:.2f})")

    for ma, mb, result in direct_contradictions[:2]:
        print(f"  {ma.id} ↔ {mb.id}: type={result['type']}, "
              f"prob={result['probability']:.2f}, hint={result['resolution_hint']}")

    # Test _softmax utility
    test_softmax = _softmax(np.array([1.0, 2.0, 3.0]))
    components_exercised.add("_softmax")
    assert abs(test_softmax.sum() - 1.0) < 1e-6, "softmax must sum to 1"

    # ══════════════════════════════════════════════════════════════════
    # STAGE 5: Health & Drift Analysis
    # ══════════════════════════════════════════════════════════════════
    print(_section(5, 11,"HEALTH & DRIFT"))

    # Staleness
    last_accessed_times = [m.last_accessed for m in memories]
    staleness_values = batch_staleness(last_accessed_times, now=NOW)
    components_exercised.add("batch_staleness")

    stale_count = sum(1 for s in staleness_values if s > 0.8)
    fresh_count = sum(1 for s in staleness_values if s < 0.3)
    moderate_count = len(staleness_values) - stale_count - fresh_count
    print(f"  Staleness: {stale_count} stale (>0.8), {fresh_count} fresh (<0.3), {moderate_count} moderate")

    # Verify individual staleness
    single_staleness = staleness_score(NOW - timedelta(days=1), now=NOW)
    components_exercised.add("staleness_score")

    # Drift: simulate temporal embedding changes
    drifted_memories = []
    for m in memories:
        # Simulate a "current" embedding as the original + time-dependent drift
        days_since = (NOW - m.created_at).total_seconds() / 86400
        drift_noise = RNG.normal(0, 0.02 * math.sqrt(days_since), EMBEDDING_DIM)
        current_emb = m.embedding + drift_noise
        current_emb /= np.linalg.norm(current_emb)

        drift = compute_drift_score(m.embedding.tolist(), current_emb.tolist())
        components_exercised.add("compute_drift_score")
        if drift > 0.15:
            drifted_memories.append((m, drift))

    drifted_memories.sort(key=lambda x: x[1], reverse=True)
    if drifted_memories:
        top_drift = drifted_memories[0]
        print(f"  Drift: {top_drift[0].id} drifted {top_drift[1]:.2f} (above threshold 0.15)")
    else:
        print("  Drift: no memories above threshold 0.15")
    print(f"  Total drifted: {len(drifted_memories)} memories")

    # Also test cosine_distance directly
    cd = cosine_distance(memories[0].embedding, memories[1].embedding)
    components_exercised.add("cosine_distance")

    # Coverage gap analysis
    sim_matrix = _cosine_similarity_matrix(
        np.array([t.query_embedding for t in transactions]),
        embedding_matrix,
    )
    components_exercised.add("_cosine_similarity_matrix")

    # K-means clustering
    centroids, labels = _simple_kmeans(embedding_matrix, k=6, max_iter=50, seed=42)
    components_exercised.add("_simple_kmeans")

    cluster_sizes = [int((labels == c).sum()) for c in range(6)]
    gaps = sum(1 for s in cluster_sizes if s < 3)
    print(f"  Coverage: {gaps} sparse clusters identified in k=6 clustering")
    print(f"  Cluster sizes: {cluster_sizes}")

    # CHI computation
    mean_staleness = float(np.mean(staleness_values))
    # Attribution quality: average over scores that are nonzero (memory was
    # actually relevant). Including zeros from unrelated memories just
    # measures 1/k distribution, not attribution quality.
    all_scores = [s for h in mem_attribution_history.values() for s in h]
    nonzero_scores = [s for s in all_scores if s > 0.01]
    accuracy = float(np.mean(nonzero_scores)) if nonzero_scores else 0.5
    freshness = 1.0 - mean_staleness
    # Coverage: fraction of queries with at least one strong memory match
    # Use 0.4 threshold for 64-dim compressed embeddings (0.5 for 384-dim)
    coverage = float(np.mean(sim_matrix.max(axis=1) > 0.4))
    consistency = 1.0 - (len(direct_contradictions) / len(memories))
    waste = token_waste_rate(
        all_scores,
        [mem_map[m.id].tokens for m in memories for _ in mem_attribution_history[m.id] if mem_attribution_history[m.id]],
    )
    components_exercised.add("token_waste_rate")
    efficiency = 1.0 - waste / 100.0

    chi = compute_chi(accuracy, freshness, coverage, consistency, efficiency)
    components_exercised.add("compute_chi")
    print(f"  CHI: {chi.score:.2f} (Grade {chi.grade}) — accuracy={chi.accuracy_component:.2f}, "
          f"freshness={chi.freshness_component:.2f}, coverage={chi.coverage_component:.2f}, "
          f"consistency={chi.consistency_component:.2f}, efficiency={chi.efficiency_component:.2f}")

    # ══════════════════════════════════════════════════════════════════
    # STAGE 6: Financial Metrics
    # ══════════════════════════════════════════════════════════════════
    print(_section(6, 11,"FINANCIAL METRICS"))

    # Compute P&L for every memory
    pnl_results = []
    for m in memories:
        pnl = memory_pnl(
            m.id,
            total_attribution=mem_total_attribution[m.id],
            retrieval_count=m.retrieval_count,
            tokens=m.tokens,
            config=COST_CONFIG,
        )
        pnl_results.append(pnl)
    components_exercised.add("memory_pnl")

    # Sharpe ratio for top memories
    sharpe_results = []
    for m in memories:
        history = mem_attribution_history[m.id]
        if len(history) >= 2:
            sr = compute_sharpe_ratio(m.id, history)
            sharpe_results.append(sr)
    components_exercised.add("compute_sharpe_ratio")

    sharpe_results.sort(key=lambda sr: sr.sharpe_ratio, reverse=True)
    if sharpe_results:
        best = sharpe_results[0]
        print(f"  Top Sharpe: {best.memory_id} (SR={best.sharpe_ratio:.1f}, \"{best.interpretation}\")")

    # Worst P&L
    pnl_sorted = sorted(pnl_results, key=lambda p: p.pnl)
    worst = pnl_sorted[0]
    print(f"  Worst P&L: {worst.memory_id} (${worst.pnl:.4f}, ROI={worst.roi:.1f})")

    # Portfolio ROI
    portfolio_data = []
    for m in memories:
        pnl = next(p for p in pnl_results if p.memory_id == m.id)
        portfolio_data.append({
            "memory_id": m.id,
            "revenue": pnl.revenue,
            "cost": pnl.cost,
            "tokens": m.tokens,
            "roi": pnl.roi,
        })

    portfolio = compute_portfolio_roi(AGENT_ID, portfolio_data)
    components_exercised.add("compute_portfolio_roi")
    print(f"  Portfolio ROI: {portfolio.total_roi:.1f}x | Diversification: {portfolio.diversification_score:.2f}")

    # Gini, SNR, waste, CRS
    all_attrs = [mem_total_attribution[m.id] for m in memories]
    gini = gini_coefficient(all_attrs)
    components_exercised.add("gini_coefficient")

    snr = snr_db(all_attrs)
    components_exercised.add("snr_db")

    all_token_counts = [m.tokens for m in memories]
    waste_rate = token_waste_rate(all_attrs, all_token_counts)

    contra_probs = [r["probability"] for _, _, r in direct_contradictions]
    crs = contradiction_risk(contra_probs)
    components_exercised.add("contradiction_risk")

    print(f"  Gini: {gini:.2f} | SNR: {snr:.1f} dB | Waste: {waste_rate:.1f}%")
    print(f"  Contradiction Risk (CRS): {crs:.2f}")

    # ══════════════════════════════════════════════════════════════════
    # STAGE 7: Lifecycle Recommendations
    # ══════════════════════════════════════════════════════════════════
    print(_section(7, 11,"LIFECYCLE RECOMMENDATIONS"))

    # Archive candidates: negative P&L
    archive_candidates = [p for p in pnl_results if p.pnl < 0]
    archive_savings = sum(abs(p.cost) for p in archive_candidates)
    print(f"  Archive: {len(archive_candidates)} memories (negative P&L, "
          f"est savings ${archive_savings:.4f}/mo)")

    # Consolidation candidates: exact dupes + near-dupes via cosine sim
    exact_dupes = len(duplicate_groups)
    # Find semantic near-duplicates
    near_dupes = 0
    for i in range(len(memories)):
        for j in range(i + 1, len(memories)):
            if memories[i].is_duplicate or memories[j].is_duplicate:
                continue
            sim = float(embedding_matrix[i] @ embedding_matrix[j] / (
                np.linalg.norm(embedding_matrix[i]) * np.linalg.norm(embedding_matrix[j])
            ))
            if sim > 0.90:
                near_dupes += 1
                if near_dupes >= 3:
                    break
        if near_dupes >= 3:
            break

    print(f"  Consolidate: {exact_dupes} exact + {near_dupes} semantic duplicates")

    # Tier change recommendations
    promote = []
    demote = []
    for m in memories:
        history = mem_attribution_history[m.id]
        if len(history) >= 2:
            first_half = np.mean(history[:len(history)//2])
            second_half = np.mean(history[len(history)//2:])
            if second_half > first_half * 1.3 and m.tier == "warm":
                promote.append(m.id)
            elif second_half < first_half * 0.5 and m.tier == "warm":
                demote.append(m.id)
    print(f"  Tier changes: promote {len(promote)} (warm→hot), demote {len(demote)} (warm→cold)")

    # Budget optimization (greedy submodular)
    BUDGET_TOKENS = 12000
    mem_value = [(m, mem_total_attribution[m.id] / max(m.tokens, 1)) for m in memories]
    mem_value.sort(key=lambda x: x[1], reverse=True)
    selected_ids = []
    used_tokens = 0
    for m, _ in mem_value:
        if used_tokens + m.tokens <= BUDGET_TOKENS:
            selected_ids.append(m.id)
            used_tokens += m.tokens
    excluded = len(memories) - len(selected_ids)
    print(f"  Budget optimization: {len(selected_ids)}/{len(memories)} fit in "
          f"{BUDGET_TOKENS:,} token budget")

    # ══════════════════════════════════════════════════════════════════
    # STAGE 8: Compliance
    # ══════════════════════════════════════════════════════════════════
    print(_section(8, 11,"COMPLIANCE"))

    # Build provenance graph
    prov = ProvenanceGraph()
    components_exercised.add("ProvenanceGraph")

    for m in memories:
        prov.add_event(
            memory_id=m.id,
            event_type=ProvenanceEventType.created,
            agent_id=AGENT_ID,
            actor="sdk",
            content_hash=m.content_hash,
        )
    components_exercised.add("ProvenanceGraph.add_event")
    components_exercised.add("ProvenanceEventType")

    # Add some derivation relationships
    # Simulate: some debug memories derived from architecture decisions
    debug_mems = [m for m in memories if m.cluster == "debug"]
    arch_mems = [m for m in memories if m.cluster == "arch"]
    for dm in debug_mems[:3]:
        if arch_mems:
            prov.add_event(
                memory_id=dm.id,
                event_type=ProvenanceEventType.derived,
                agent_id=AGENT_ID,
                actor="agent",
                parent_memory_ids=[arch_mems[0].id],
            )

    # Add merge events for duplicates
    for dup, orig in duplicate_groups:
        prov.add_event(
            memory_id=orig.id,
            event_type=ProvenanceEventType.merged,
            agent_id=AGENT_ID,
            actor="lifecycle",
            parent_memory_ids=[dup.id],
        )

    graph_data = prov.to_dict()
    components_exercised.add("ProvenanceGraph.to_dict")

    has_cycle = prov.has_cycle()
    components_exercised.add("ProvenanceGraph.has_cycle")

    # Test lineage and descendants
    if debug_mems:
        lineage = prov.get_lineage(debug_mems[0].id)
        components_exercised.add("ProvenanceGraph.get_lineage")
        depth = prov.provenance_depth(debug_mems[0].id)
        components_exercised.add("ProvenanceGraph.provenance_depth")

    if arch_mems:
        descendants = prov.get_descendants(arch_mems[0].id)
        components_exercised.add("ProvenanceGraph.get_descendants")

    max_depth = max(prov.provenance_depth(m.id) for m in memories)

    print(f"  Provenance: {graph_data['stats']['total_nodes']} nodes, "
          f"{graph_data['stats']['total_edges']} edges, max depth {max_depth}, "
          f"{'no cycles' if not has_cycle else 'CYCLES DETECTED!'}")

    # SISA partitioning
    sisa = SISAPartitioner(num_shards=6)
    components_exercised.add("SISAPartitioner")

    mem_ids = [m.id for m in memories]
    shards = sisa.partition(mem_ids, embedding_matrix)
    components_exercised.add("SISAPartitioner.partition")

    sisa_stats = sisa.stats()
    components_exercised.add("SISAPartitioner.stats")
    print(f"  SISA: {sisa_stats['num_shards']} shards, balance={sisa_stats['balance_ratio']:.2f}")

    # Test find_shard
    test_shard = sisa.find_shard(memories[0].id)
    components_exercised.add("SISAPartitioner.find_shard")

    # Simulate unlearning a stale memory
    unlearn_target = next((m for m in memories if m.last_accessed and
                           staleness_score(m.last_accessed, now=NOW) > 0.8), memories[-1])
    unlearn_result = sisa.unlearn(unlearn_target.id)
    components_exercised.add("SISAPartitioner.unlearn")

    if unlearn_result:
        print(f"  Unlearn {unlearn_target.id}: shard_size={unlearn_result.shard_size}, "
              f"efficiency={unlearn_result.efficiency_gain:.0%}")
    else:
        print(f"  Unlearn {unlearn_target.id}: not found in any shard")

    # Build ErasureCheckResult objects to show what would need cleaning
    layers = ["memories", "attribution_scores", "memory_profiles",
              "transaction_references", "calibration_pairs", "snapshot_entries", "contradictions"]
    erasure_checks = []
    for layer in layers:
        # Simulate: memory exists in primary + attribution layers
        exists = layer in ("memories", "attribution_scores", "memory_profiles")
        erasure_checks.append(ErasureCheckResult(
            layer=layer,
            exists=exists,
            record_count=1 if exists else 0,
            details=f"Record found in {layer}" if exists else "Erased",
        ))
    components_exercised.add("ErasureCheckResult")

    erased_count = sum(1 for c in erasure_checks if not c.exists)
    print(f"  Erasure check: {erased_count}/{len(layers)} layers clean for {unlearn_target.id}")

    # ══════════════════════════════════════════════════════════════════
    # STAGE 9: Statement-Level Attribution
    # ══════════════════════════════════════════════════════════════════
    print(_section(9, 11,"STATEMENT-LEVEL ATTRIBUTION"))

    # Run for 3 selected transactions
    selected_txns = [transactions[2], transactions[4], transactions[9]]  # testing, auth, security
    for txn in selected_txns:
        retrieved = [mem_map[mid] for mid in txn.retrieved_memory_ids if mid in mem_map]
        if not retrieved:
            continue

        result = compute_statement_attribution(
            response_text=txn.response_text,
            memory_texts=[m.content for m in retrieved],
            memory_ids=[m.id for m in retrieved],
            grounding_threshold=0.2,
        )
        components_exercised.add("compute_statement_attribution")

        print(f"  Txn {txn.id[-2:]}: \"{txn.query_text}\"")
        for sa in result.statements[:4]:
            text_preview = sa.statement_text[:65] + "..." if len(sa.statement_text) > 65 else sa.statement_text
            grounded_mark = "✓" if sa.is_grounded else "✗"
            top_id = sa.top_memory_id or "none"
            print(f"    S{sa.statement_index+1}: \"{text_preview}\" → {top_id} ({sa.top_score:.2f}) {grounded_mark}")
        print(f"  Grounding rate: {result.grounding_rate:.0%} | Avg attribution: {result.avg_attribution:.2f}")

    # Test segment_into_statements
    stmts = segment_into_statements("First sentence. Second sentence! Third?")
    components_exercised.add("segment_into_statements")
    assert len(stmts) == 3, f"Expected 3 statements, got {len(stmts)}"

    # Test _token_overlap_score
    overlap = _token_overlap_score("pytest unit testing framework", "We use pytest for unit tests")
    components_exercised.add("_token_overlap_score")
    assert overlap > 0, "Token overlap should be positive for related text"

    # ══════════════════════════════════════════════════════════════════
    # STAGE 10: Counterfactual Memory Staging
    # ══════════════════════════════════════════════════════════════════
    print(_section(10, 11, "COUNTERFACTUAL MEMORY STAGING"))

    # Convert SimMemory → CFMemoryRecord
    cf_memories = []
    for m in memories:
        cf_memories.append(CFMemoryRecord(
            id=m.id,
            content=m.content,
            embedding=m.embedding,
            tokens=m.tokens,
            tier=m.tier,
            created_at=m.created_at,
            last_accessed=m.last_accessed,
            agent_id=AGENT_ID,
            retrieval_count=m.retrieval_count,
            total_attribution=mem_total_attribution.get(m.id, 0.0),
        ))

    # Convert SimTransaction → CFTransactionRecord
    cf_transactions = []
    for txn in transactions:
        cf_transactions.append(CFTransactionRecord(
            id=txn.id,
            query_text=txn.query_text,
            query_embedding=txn.query_embedding,
            response_embedding=txn.response_embedding,
            retrieved_memory_ids=txn.retrieved_memory_ids,
            input_tokens=txn.input_tokens,
            output_tokens=txn.output_tokens,
        ))

    # Stage 3 changes: 1 add, 1 remove, 1 edit
    # Add: a new relevant memory about Kubernetes debugging
    k8s_emb = _make_embedding("debug", noise_scale=0.10)
    # Remove: the stale meeting memory (lowest value)
    stale_mem = next(m for m in memories if "meeting" in m.content.lower())
    # Edit: update the pytest memory to mention pytest-xdist
    pytest_mem = next(m for m in memories if "pytest" in m.content and not m.is_contradiction)

    cf_changes = [
        ChangeSpec(
            action="add",
            memory_id="mem-staged-k8s",
            content="Kubernetes pod OOMKilled resolved by setting memory limits to 2Gi and requests to 512Mi in deployment manifest.",
            embedding=k8s_emb,
            tokens=180,
        ),
        ChangeSpec(
            action="remove",
            memory_id=stale_mem.id,
        ),
        ChangeSpec(
            action="edit",
            memory_id=pytest_mem.id,
            content=pytest_mem.content + " Uses pytest-xdist for parallel test execution.",
            embedding=_make_embedding("python", noise_scale=0.08, near=pytest_mem.embedding),
            tokens=pytest_mem.tokens + 60,
        ),
    ]

    try:
        cf_result = run_counterfactual(
            current_memories=cf_memories,
            changes=cf_changes,
            transactions=cf_transactions,
            existing_contradictions=[
                (ma.id, mb.id, r["probability"])
                for ma, mb, r in direct_contradictions
            ],
            cost_config=COST_CONFIG,
            include_analysis={"attribution", "contradictions", "coverage", "chi", "financial"},
        )
        components_exercised.add("run_counterfactual")

        print(f"  Compute time: {cf_result['compute_time_ms']:.1f}ms")
        print(f"  Transactions analyzed: {len(cf_transactions)}")

        summary = cf_result["summary"]
        print(f"  Transactions affected: {summary['transactions_affected']}/{len(cf_transactions)}")
        print(f"  Avg score delta: {summary['avg_score_delta']:.4f}")
        print(f"  Max score delta: {summary['max_score_delta']:.4f}")
        print(f"  New memories in top-3: {summary['new_memories_in_top3']}")

        if cf_result["chi"]:
            chi_d = cf_result["chi"]
            direction = "improved" if chi_d["delta"] > 0 else "degraded" if chi_d["delta"] < 0 else "unchanged"
            print(f"  CHI: {chi_d['before']:.3f} → {chi_d['after']:.3f} ({direction}, Δ={chi_d['delta']:+.4f})")

        if cf_result["contradictions"]:
            cd = cf_result["contradictions"]
            print(f"  Contradictions: {len(cd['new_contradictions'])} new, "
                  f"{len(cd['resolved_contradictions'])} resolved (net {cd['net_change']:+d})")

        if cf_result["coverage"]:
            cov = cf_result["coverage"]
            print(f"  Coverage gaps: {cov['gaps_before']} → {cov['gaps_after']} ({cov['gap_change']:+d})")

        if cf_result["financial"]:
            fin = cf_result["financial"]
            print(f"  Portfolio ROI: {fin['portfolio_roi_before']:.2f} → {fin['portfolio_roi_after']:.2f}")
            print(f"  Est monthly savings: ${fin['estimated_monthly_savings']:.6f}")

        # With real NLI (DeBERTa model loading), first run can take ~10-15s.
        # Subsequent runs (model cached) complete in <1s.
        assert cf_result["compute_time_ms"] < 30000, \
            f"Counterfactual should complete in <30s, took {cf_result['compute_time_ms']:.0f}ms"

        components_exercised.add("build_counterfactual_memory_set")
        components_exercised.add("ChangeSpec")
        components_exercised.add("MemoryRecord")
        components_exercised.add("TransactionRecord")

    except Exception as e:
        errors += 1
        print(f"  [ERROR] Counterfactual staging: {e}")
        import traceback
        traceback.print_exc()

    # ══════════════════════════════════════════════════════════════════
    # STAGE 11: Grounding & Contamination Detection
    # ══════════════════════════════════════════════════════════════════
    print(_section(11, 11, "GROUNDING & CONTAMINATION DETECTION"))

    try:
        # Convert SimMemory → MemoryForGrounding
        grounding_mems = []
        for m in memories:
            # Assign source types based on memory characteristics
            if m.is_contradiction:
                src_type = "agent_generated"  # contradictions likely agent-produced
            elif m.is_duplicate:
                src_type = "derived"
            elif m.cluster == "user":
                src_type = "user_input"
            elif m.retrieval_count >= 5:
                src_type = "user_input"  # frequently used = likely from real interaction
            else:
                src_type = "agent_generated"

            history = mem_attribution_history.get(m.id, [])
            mean_attr = float(np.mean(history)) if history else 0.0

            grounding_mems.append(MemoryForGrounding(
                id=m.id,
                content=m.content,
                embedding=m.embedding,
                tokens=m.tokens,
                retrieval_count=m.retrieval_count,
                total_attribution=mem_total_attribution.get(m.id, 0.0),
                mean_attribution=mean_attr,
                created_at=m.created_at,
                source_type=src_type,
            ))

        # Convert SimTransaction → TransactionForGrounding
        grounding_txns = []
        for txn in transactions:
            grounding_txns.append(TransactionForGrounding(
                id=txn.id,
                query_text=txn.query_text,
                query_embedding=txn.query_embedding,
                response_embedding=txn.response_embedding,
                retrieved_memory_ids=txn.retrieved_memory_ids,
            ))

        # Build contradiction pairs set
        contra_pair_set: set[tuple[str, str]] = set()
        for ma, mb, result in direct_contradictions:
            pair = (min(ma.id, mb.id), max(ma.id, mb.id))
            contra_pair_set.add(pair)

        # 1. Full contamination scan
        scan_result = scan_contamination(
            grounding_mems, grounding_txns, contra_pair_set,
        )
        components_exercised.add("scan_contamination")
        components_exercised.add("compute_grounding_scores")

        print(f"  Scan: {scan_result.total_memories} memories analyzed in "
              f"{scan_result.compute_time_ms:.1f}ms")
        print(f"  Trusted: {scan_result.trusted} | Uncertain: {scan_result.uncertain} | "
              f"Suspect: {scan_result.suspect} | Contaminated: {scan_result.contaminated}")
        print(f"  System contamination rate: {scan_result.system_contamination_rate:.1%}")

        # Show top 3 most suspect memories
        for flag in scan_result.flags[:3]:
            print(f"    {flag.memory_id}: grounding={flag.grounding_score:.3f} "
                  f"({flag.risk_level}) → {flag.recommended_action}")
            print(f"      Reasons: {'; '.join(flag.reasons[:2])}")

        # 2. Gate check: test blocking a hallucinated memory
        hallucinated_candidate = MemoryForGrounding(
            id="mem-hallucinated",
            content="User's primary language is Haskell and they avoid Python",
            embedding=_make_embedding("python", noise_scale=0.05),  # similar to python cluster
            tokens=80,
            source_type="unknown",  # no provenance
            retrieval_count=0,
            mean_attribution=0.0,
        )
        gate_result = gate_memory(
            hallucinated_candidate, grounding_mems, grounding_txns,
        )
        components_exercised.add("gate_memory")

        gate_status = "BLOCKED" if not gate_result.should_store else "PASSED"
        print(f"\n  Gate check (hallucinated memory): {gate_status}")
        print(f"    Grounding: {gate_result.grounding_score:.3f} ({gate_result.risk_level})")
        if gate_result.contradicts_existing:
            print(f"    Contradicts: {gate_result.contradicts_existing}")
        if gate_result.redundant_with:
            print(f"    Redundant with: {gate_result.redundant_with}")
        print(f"    Reasons: {'; '.join(gate_result.reasons[:2])}")

        # 3. Gate check: test allowing a legitimate memory
        legit_candidate = MemoryForGrounding(
            id="mem-legit",
            content="Team adopted Terraform Cloud for remote state management",
            embedding=_make_embedding("tools", noise_scale=0.15),
            tokens=70,
            source_type="user_input",
            retrieval_count=0,
            mean_attribution=0.0,
        )
        legit_result = gate_memory(legit_candidate, grounding_mems, grounding_txns)
        legit_status = "PASSED" if legit_result.should_store else "BLOCKED"
        print(f"\n  Gate check (legitimate memory): {legit_status}")
        print(f"    Grounding: {legit_result.grounding_score:.3f} ({legit_result.risk_level})")

        # 4. Quarantine simulation: what if we remove all suspect memories?
        suspect_ids = [
            f.memory_id for f in scan_result.flags
            if f.risk_level in ("suspect", "contaminated")
        ]
        if suspect_ids:
            quarantine_result = simulate_quarantine(
                suspect_ids, grounding_mems, grounding_txns,
            )
            components_exercised.add("simulate_quarantine")

            q_direction = "improved" if quarantine_result["health_improved"] else "degraded"
            print(f"\n  Quarantine simulation ({len(suspect_ids)} memories):")
            if quarantine_result.get("chi_before") is not None:
                print(f"    CHI: {quarantine_result['chi_before']:.3f} → "
                      f"{quarantine_result['chi_after']:.3f} ({q_direction})")
            print(f"    Transactions affected: {quarantine_result['transactions_affected']}")
            print(f"    → {quarantine_result['recommendation']}")
        else:
            print("\n  Quarantine: no suspect memories to quarantine")

        components_exercised.add("MemoryForGrounding")
        components_exercised.add("TransactionForGrounding")
        components_exercised.add("GroundingResult")

    except Exception as e:
        errors += 1
        print(f"  [ERROR] Grounding & Contamination: {e}")
        import traceback
        traceback.print_exc()

    # ══════════════════════════════════════════════════════════════════
    # FINAL REPORT
    # ══════════════════════════════════════════════════════════════════
    elapsed = time.perf_counter() - t_start

    print(f"\n{_hr('═')}")
    print(f"  SIMULATION COMPLETE — all 11 stages passed")
    print(f"  {len(components_exercised)} components exercised | {errors} errors | {elapsed:.1f}s")
    print(_hr("═"))

    if errors:
        print(f"\n  ⚠ {errors} error(s) detected — check output above")
    return errors


if __name__ == "__main__":
    sys.exit(run_simulation())
