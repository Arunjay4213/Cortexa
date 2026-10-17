"""Unified CAMA scorer — orchestrates all pipeline tiers.

Pipeline: Decompose → Numerical Gate → NLI Entailment → Attribution → Ghost → Contradiction → Stale → Health
"""

import logging
import time

from cortexa.engine.attribution import AttributionComputer
from cortexa.engine.contradiction import ContradictionDetector
from cortexa.engine.decomposer import ClaimDecomposer
from cortexa.engine.entailment import EntailmentScorer
from cortexa.engine.ghost_detector import GhostDetector
from cortexa.engine.models import (
    AuditResult,
    Memory,
    TraceResult,
)
from cortexa.engine.numerical_gate import NumericalGate
from cortexa.engine.staleness import StalenessDetector

logger = logging.getLogger(__name__)


class CortexaScorer:
    """Orchestrates the full CAMA verification pipeline."""

    def __init__(
        self,
        decompose_mode: str = "fast",
        nli_backend: str = "api",
        nli_model: str | None = None,
        ghost_threshold: float = 0.05,
        contradiction_threshold: float = 0.7,
        staleness_days: int = 30,
        temperature: float = 0.5,
    ) -> None:
        self.decomposer = ClaimDecomposer(mode=decompose_mode)
        self.numerical_gate = NumericalGate()
        self.entailment = EntailmentScorer(backend=nli_backend, model_name=nli_model)
        self.attribution = AttributionComputer(
            temperature=temperature, ghost_threshold=ghost_threshold
        )
        self.ghost_detector = GhostDetector(ghost_threshold=ghost_threshold)
        self.contradiction_detector = ContradictionDetector(
            contradiction_threshold=contradiction_threshold
        )
        self.staleness_detector = StalenessDetector(staleness_days=staleness_days)

    def trace(
        self,
        query: str,
        response: str,
        memories: list[Memory],
        recent_traces: list[TraceResult] | None = None,
    ) -> TraceResult:
        """Run the full CAMA pipeline on a query-response pair.

        Args:
            query: The user's query.
            response: The LLM's response.
            memories: Retrieved memories used for generation.
            recent_traces: Optional rolling window for ghost detection.
        """
        start = time.time()

        # Tier 1: Claim decomposition
        claims = self.decomposer.decompose(response)
        logger.info("Decomposed into %d claims", len(claims))

        # Tier 2: Numerical gate
        numerical = self.numerical_gate.check(claims, memories)
        logger.info(
            "Numerical gate: %d matches, %d contradictions, %d unverified",
            len(numerical.matches),
            len(numerical.contradictions),
            len(numerical.unverified),
        )

        # Tier 3: NLI entailment
        entailments = self.entailment.score_batch(claims, memories)
        logger.info("Scored %d entailment pairs", len(entailments))

        # Tier 4: Attribution (MAS)
        attributions = self.attribution.compute(claims, memories, entailments)

        # Merge numerical gate results into attributions
        num_match_set: set[tuple[str, str]] = set()
        for nm in numerical.matches:
            num_match_set.add((nm.claim_id, nm.memory_id))
        num_contra_set: set[tuple[str, str]] = set()
        for nm in numerical.contradictions:
            num_contra_set.add((nm.claim_id, nm.memory_id))

        for attr in attributions:
            key = (attr.claim_id, attr.memory_id)
            if key in num_match_set:
                attr.numerical_match = True
            elif key in num_contra_set:
                attr.numerical_match = False

        # Ghost detection
        ghosts = self.ghost_detector.detect(memories, attributions, recent_traces)
        logger.info("Found %d ghost tokens", len(ghosts))

        # Contradiction detection
        contradictions = self.contradiction_detector.detect_from_entailments(
            memories, claims, entailments, attributions
        )
        logger.info("Found %d contradictions", len(contradictions))

        # Staleness detection
        stale = self.staleness_detector.detect(memories)
        logger.info("Found %d stale memories", len(stale))

        # Health score
        health = self._compute_health(
            memories, attributions, ghosts, contradictions, stale
        )

        latency_ms = (time.time() - start) * 1000

        return TraceResult(
            query=query,
            response=response,
            claims=claims,
            attributions=attributions,
            ghost_tokens=ghosts,
            contradictions=contradictions,
            stale_memories=stale,
            health_score=health,
            latency_ms=round(latency_ms, 1),
        )

    def audit(
        self,
        memories: list[Memory],
        recent_traces: list[TraceResult] | None = None,
    ) -> AuditResult:
        """Run a full health audit on a memory store.

        If recent_traces are provided, uses them for ghost detection.
        Otherwise runs a basic staleness + structure check.
        """
        total = len(memories)
        if total == 0:
            return AuditResult(
                total_memories=0,
                ghost_count=0,
                ghost_percentage=0.0,
                contradiction_count=0,
                stale_count=0,
                health_score=100.0,
                recommendations=["No memories to audit."],
            )

        # Staleness check (always possible)
        stale = self.staleness_detector.detect(memories)

        # Ghost + contradiction detection from recent traces
        all_ghosts = []
        all_contradictions = []
        ghost_ids: set[str] = set()

        if recent_traces:
            for trace in recent_traces:
                for g in trace.ghost_tokens:
                    if g.memory_id not in ghost_ids:
                        ghost_ids.add(g.memory_id)
                        all_ghosts.append(g)
                all_contradictions.extend(trace.contradictions)

        ghost_count = len(all_ghosts)
        ghost_pct = (ghost_count / total * 100) if total > 0 else 0.0

        # Deduplicate contradictions
        seen_contra: set[tuple[str, str]] = set()
        unique_contradictions = []
        for c in all_contradictions:
            key = tuple(sorted([c.memory_id_1, c.memory_id_2]))
            if key not in seen_contra:
                seen_contra.add(key)
                unique_contradictions.append(c)

        # Waste estimation
        waste_tokens, waste_cost = self.ghost_detector.estimate_waste(
            all_ghosts, memories
        )

        # Health score
        health = self._compute_health_from_counts(
            total, ghost_count, len(unique_contradictions), len(stale)
        )

        # Recommendations
        recs = []
        if ghost_count > 0:
            recs.append(
                f"Remove {ghost_count} ghost tokens to save ~{waste_tokens} tokens/query "
                f"(~${waste_cost:.2f}/month)"
            )
        if unique_contradictions:
            recs.append(
                f"Resolve {len(unique_contradictions)} contradiction(s) — "
                "conflicting memories cause inconsistent responses"
            )
        if stale:
            recs.append(
                f"Refresh {len(stale)} stale memor{'y' if len(stale) == 1 else 'ies'} — "
                "source data has changed"
            )
        if not recs:
            recs.append("Memory store looks healthy!")

        return AuditResult(
            total_memories=total,
            ghost_count=ghost_count,
            ghost_percentage=round(ghost_pct, 1),
            contradiction_count=len(unique_contradictions),
            contradictions=unique_contradictions,
            stale_count=len(stale),
            stale_memories=stale,
            health_score=health,
            estimated_waste_tokens=waste_tokens,
            estimated_waste_cost_monthly=waste_cost,
            recommendations=recs,
        )

    def _compute_health(
        self, memories, attributions, ghosts, contradictions, stale
    ) -> float:
        """Compute health score (0-100).

        health = 100
        health -= ghost_percentage * 0.5       (up to -50)
        health -= contradiction_count * 5      (cap at -30)
        health -= stale_percentage * 0.3       (up to -20)
        """
        total = len(memories)
        if total == 0:
            return 100.0
        return self._compute_health_from_counts(
            total, len(ghosts), len(contradictions), len(stale)
        )

    @staticmethod
    def _compute_health_from_counts(
        total: int, ghost_count: int, contradiction_count: int, stale_count: int
    ) -> float:
        if total == 0:
            return 100.0

        ghost_pct = ghost_count / total * 100
        stale_pct = stale_count / total * 100

        health = 100.0
        health -= ghost_pct * 0.5  # up to -50
        health -= min(contradiction_count * 5, 30)  # cap at -30
        health -= stale_pct * 0.3  # up to -20
        return round(max(0.0, min(100.0, health)), 1)
