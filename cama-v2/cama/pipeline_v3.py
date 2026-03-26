"""CAMAv3 pipeline — SummaC-inspired NLI pair matrix, no hallucination detector.

Design:
- NLIPairMatrix.build() replaces detect+attribute pipeline
- hallucinated_spans=[] (v3 doesn't classify tokens as hallucinations)
- hallucination_rate=0.0 (not computed in v3)
- Ghost detection via embedding cosine sim to query
- Contradiction detection via attribution-based + optional NLI pairwise
"""

from __future__ import annotations

import logging
import time

from cama.diagnose import Diagnoser
from cama.matrix import NLIPairMatrix
from cama.types import Memory, TraceResult

logger = logging.getLogger(__name__)


class CAMAv3Pipeline:
    """CAMAv3: direct NLI attribution without hallucination detection.

    Replaces the detect→attribute pipeline with a single NLIPairMatrix pass.
    """

    def __init__(
        self,
        top_k: int = 10,
        model_name: str = "cross-encoder/nli-deberta-v3-xsmall",
        similarity_threshold: float = 0.20,
    ):
        self.matrix = NLIPairMatrix(top_k=top_k, model_name=model_name)
        self.diagnoser = Diagnoser()
        self.nli = self.matrix.nli
        self.similarity_threshold = similarity_threshold

    def trace(
        self,
        query: str,
        response: str,
        memories: list,
    ) -> TraceResult:
        """Run CAMA v3 trace: NLIPairMatrix → diagnose → TraceResult."""
        start = time.perf_counter()

        # Normalize memories to Memory objects
        mems = [Memory(**m) if isinstance(m, dict) else m for m in memories]

        # Stage 1: NLI pair matrix → span_attributions
        result = self.matrix.build(response, mems)
        span_attributions = result["span_attributions"]

        # Stage 2: Ghost detection via embedding cosine sim to query
        ghosts = self.diagnoser.detect_ghosts(
            mems,
            span_attributions,
            query=query,
            similarity_threshold=self.similarity_threshold,
        )

        # Stage 3: Staleness detection + upgrade culprit diagnoses
        stale = self.diagnoser.detect_stale(mems)
        stale_set = set(stale)
        for sa in span_attributions:
            if sa.culprit_memory_id in stale_set:
                sa.diagnosis = "stale_memory"

        # Stage 4: Contradiction detection
        contradictions = self.diagnoser.detect_contradictions(
            mems,
            span_attributions,
            nli_model=self.nli,
        )

        # Stage 5: Per-memory health report
        memory_health = self.diagnoser.build_memory_health_report(
            mems,
            span_attributions,
            ghosts,
            stale,
            contradictions,
            attribution_method="SummaC-Direct",
        )

        elapsed_ms = (time.perf_counter() - start) * 1000

        tr = TraceResult(
            query=query,
            response=response,
            memories_used=[m.id for m in mems],
            hallucinated_spans=[],
            span_attributions=span_attributions,
            ghost_memories=ghosts,
            contradictions=contradictions,
            stale_memories=stale,
            health_score=0.0,  # computed below
            hallucination_rate=0.0,
            latency_ms=elapsed_ms,
            detection_method="NLIPairMatrix",
            attribution_method="SummaC-Direct",
            memory_health=memory_health,
        )
        tr.health_score = self.diagnoser.compute_health(tr)
        return tr
