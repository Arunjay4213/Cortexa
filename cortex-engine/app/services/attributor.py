"""
Leave-one-out Shapley attribution engine.

For a grounded claim, identifies which source document is most
responsible for the entailment. For a hallucinated claim,
identifies which source (if any) is contradicting it.

Complexity: O(N+1) NLI calls per claim, where N = number of sources.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from app.services.nli import NLIService


@dataclass
class SourceInfluence:
    """Attribution score for a single source's influence on a claim."""

    source_index: int
    influence_raw: float  # score_full - score_minus_i (signed)
    influence_norm: float  # normalized: influence / sum(|influences|)
    direction: str  # "SUPPORTS", "CONTRADICTS", "IRRELEVANT"
    source_preview: str  # first 120 chars of the source

    @property
    def is_primary(self) -> bool:
        """True if this source is the dominant contributor (>50% influence)."""
        return self.influence_norm > 0.5


@dataclass
class AttributionResult:
    """Attribution result for a single claim across all sources."""

    claim_text: str
    influences: list[SourceInfluence]  # sorted by abs(influence_norm) desc
    primary_source_index: int | None  # index of highest-influence SUPPORTS source
    computation_calls: int  # how many NLI calls were made

    @property
    def causal_source(self) -> SourceInfluence | None:
        """The single most causally responsible source, if any."""
        if self.influences:
            return self.influences[0]
        return None


class AttributionService:
    """
    Leave-one-out Shapley attribution.

    For each claim, computes:
      score_full    = best_entailment(all sources, claim)
      score_minus_i = best_entailment(sources except i, claim)
      influence_i   = score_full - score_minus_i
      phi_i         = influence_i / sum(|influence_j| for all j)

    phi > 0: removing source hurts entailment -> it SUPPORTS the claim
    phi < 0: removing source helps entailment -> it CONTRADICTS the claim
    phi ~ 0: source is IRRELEVANT to this claim
    """

    IRRELEVANCE_THRESHOLD = 0.05

    def __init__(self, nli_service: NLIService):
        self.nli = nli_service

    async def compute(
        self,
        claim: str,
        sources: list[str],
    ) -> AttributionResult:
        """
        Compute leave-one-out Shapley influence scores for a single claim.

        Args:
            claim:   The atomic claim text to attribute.
            sources: List of source documents to score against.

        Returns:
            AttributionResult with influence score per source.

        NLI calls made: varies (sentence-level), tracked in computation_calls.
        """
        if not sources:
            return AttributionResult(
                claim_text=claim,
                influences=[],
                primary_source_index=None,
                computation_calls=0,
            )

        call_count = 0

        # Step 1: Score with ALL sources combined
        score_full, calls = await self._best_entailment_score(claim, sources)
        call_count += calls

        # Step 2: Score with each source removed (leave-one-out)
        influences_raw: list[float] = []
        for i in range(len(sources)):
            sources_minus_i = [s for j, s in enumerate(sources) if j != i]

            if not sources_minus_i:
                # Only one source — it gets full influence
                score_minus_i = 0.0
                # No NLI calls needed
            else:
                score_minus_i, calls = await self._best_entailment_score(
                    claim, sources_minus_i
                )
                call_count += calls

            influences_raw.append(score_full - score_minus_i)

        # Step 3: Normalize
        total_abs = sum(abs(x) for x in influences_raw)
        influences_norm = [
            x / total_abs if total_abs > 0 else 0.0 for x in influences_raw
        ]

        # Step 4: Build result objects
        source_influences: list[SourceInfluence] = []
        for i, (raw, norm) in enumerate(zip(influences_raw, influences_norm)):
            if abs(norm) < self.IRRELEVANCE_THRESHOLD:
                direction = "IRRELEVANT"
            elif raw > 0:
                direction = "SUPPORTS"
            else:
                direction = "CONTRADICTS"

            source_influences.append(
                SourceInfluence(
                    source_index=i,
                    influence_raw=round(raw, 4),
                    influence_norm=round(norm, 4),
                    direction=direction,
                    source_preview=sources[i][:120].strip(),
                )
            )

        # Sort by absolute influence descending
        source_influences.sort(
            key=lambda x: abs(x.influence_norm), reverse=True
        )

        # Primary source = highest absolute influence that SUPPORTS
        primary = next(
            (s for s in source_influences if s.direction == "SUPPORTS"),
            None,
        )

        return AttributionResult(
            claim_text=claim,
            influences=source_influences,
            primary_source_index=primary.source_index if primary else None,
            computation_calls=call_count,
        )

    async def compute_batch(
        self,
        claims: list[str],
        sources: list[str],
    ) -> list[AttributionResult]:
        """
        Compute attribution for multiple claims against the same sources.

        Args:
            claims:  List of atomic claim texts.
            sources: List of source documents.

        Returns:
            List of AttributionResult, one per claim.
        """
        results = []
        for claim in claims:
            result = await self.compute(claim, sources)
            results.append(result)
        return results

    async def _best_entailment_score(
        self,
        claim: str,
        sources: list[str],
    ) -> tuple[float, int]:
        """
        Find the maximum entailment score across all sentences
        in all sources for this claim.

        Uses raw P(entailment) — same as check_nli() in nli.py.

        Returns:
            (best_score, nli_call_count)
        """
        best = 0.0
        call_count = 0

        for source in sources:
            sentences = re.split(r"[.!?]+", source)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

            for sentence in sentences:
                result = await self.nli.predict(sentence, claim)
                call_count += 1
                score = result["entailment"]
                best = max(best, score)

        return best, call_count
