"""Full CAMA v2 pipeline: detect → attribute → diagnose."""

from __future__ import annotations

import logging
import time

from cama.attribute import Attributor, LOODetectorAttributor
from cama.detect import Detector, get_detector
from cama.diagnose import Diagnoser
from cama.types import Memory, TraceResult

logger = logging.getLogger(__name__)


class CAMAv2:
    """Main entry point for the CAMA v2 pipeline.

    Usage:
        cama = CAMAv2()
        result = cama.trace(
            query="What is the population of France?",
            response="France has 69 million people.",
            memories=[
                {"id": "m1", "content": "France has 67 million people."},
                {"id": "m2", "content": "The capital of France is Paris."},
            ],
        )
        print(result.health_score)
        print(result.hallucinated_spans)
    """

    def __init__(
        self,
        detector: str | Detector = "auto",
        device: str = "auto",
        nli_model: object | None = None,
        attributor: Attributor | None = None,
    ):
        if isinstance(detector, str):
            self._detector = get_detector(prefer_gpu=(device != "cpu"))
        else:
            self._detector = detector

        self._attributor = attributor or LOODetectorAttributor(self._detector)
        self._diagnoser = Diagnoser()
        self._nli_model = nli_model

    @property
    def detector(self) -> Detector:
        return self._detector

    def trace(
        self,
        query: str,
        response: str,
        memories: list[dict | Memory],
    ) -> TraceResult:
        """Run the full CAMA v2 pipeline.

        Args:
            query: The user's question.
            response: The LLM's response to verify.
            memories: List of Memory objects or dicts with at least 'id' and 'content'.

        Returns:
            TraceResult with hallucination spans, attributions, ghost/stale/contradictions,
            and a health score.
        """
        start = time.perf_counter()

        # Convert to Memory objects
        mems = [
            Memory(**m) if isinstance(m, dict) else m
            for m in memories
        ]
        mem_texts = [m.content for m in mems]

        # Stage 1: Detect hallucinations
        logger.info("Stage 1: Detecting hallucinations (%d memories)", len(mems))
        token_scores, spans = self._detector.detect(mem_texts, query, response)

        hallucination_rate = (
            sum(1 for ts in token_scores if ts.hallucination_prob > 0.5)
            / max(len(token_scores), 1)
        )

        # Stage 2: Attribute (only if there are hallucinated spans)
        span_attributions = []
        if spans:
            logger.info("Stage 2: Attributing %d hallucinated spans", len(spans))
            span_attributions = self._attributor.attribute(
                mems, query, response, token_scores, spans,
            )
        else:
            logger.info("Stage 2: No hallucinated spans — skipping attribution")

        # Stage 3: Diagnose
        logger.info("Stage 3: Running diagnosis")
        ghosts = self._diagnoser.detect_ghosts(
            mems, span_attributions,
            query=query,
            attribution_method=type(self._attributor).__name__,
        )
        contradictions = self._diagnoser.detect_contradictions(
            mems, span_attributions, nli_model=self._nli_model,
        )
        stale = self._diagnoser.detect_stale(mems)

        elapsed_ms = (time.perf_counter() - start) * 1000

        # Build per-memory health report
        memory_health = self._diagnoser.build_memory_health_report(
            mems, span_attributions, ghosts, stale, contradictions,
            attribution_method=type(self._attributor).__name__,
        )

        result = TraceResult(
            query=query,
            response=response,
            memories_used=[m.id for m in mems],
            hallucinated_spans=spans,
            span_attributions=span_attributions,
            ghost_memories=ghosts,
            contradictions=contradictions,
            stale_memories=stale,
            health_score=0.0,
            hallucination_rate=hallucination_rate,
            latency_ms=elapsed_ms,
            detection_method=type(self._detector).__name__,
            attribution_method=type(self._attributor).__name__,
            memory_health=memory_health,
        )
        result.health_score = self._diagnoser.compute_health(result)

        logger.info(
            "Pipeline complete: health=%s, spans=%d, ghosts=%d, latency=%.0fms",
            result.health_score,
            len(spans),
            len(ghosts),
            elapsed_ms,
        )

        return result
