"""Tests for cama/pipeline_v3.py — CAMAv3Pipeline (mock-based, no model loading)."""

from unittest.mock import MagicMock

import pytest

from cama.pipeline_v3 import CAMAv3Pipeline
from cama.types import (
    Contradiction,
    HallucinatedSpan,
    Memory,
    MemoryAttribution,
    SpanAttribution,
    TokenScore,
    TraceResult,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_span_attribution(
    sentence_text: str = "test sentence",
    memory_id: str = "m1",
    direction: str = "supporting",
    diagnosis: str = "supported",
    culprit: str | None = None,
) -> SpanAttribution:
    attr = MemoryAttribution(
        memory_id=memory_id,
        mas=0.5,
        delta=0.5 if direction == "supporting" else -0.5,
        direction=direction,
        raw_contradiction=2.0 if direction == "causing" else 0.1,
        raw_entailment=2.0 if direction == "supporting" else 0.1,
    )
    span = HallucinatedSpan(
        text=sentence_text,
        start_char=0,
        end_char=len(sentence_text),
        score=0.0,
        token_scores=[
            TokenScore(
                token=sentence_text.split()[0],
                index=0,
                hallucination_prob=0.0,
            )
        ],
    )
    return SpanAttribution(
        span=span,
        attributions=[attr],
        diagnosis=diagnosis,
        culprit_memory_id=culprit,
    )


@pytest.fixture
def pipeline():
    """CAMAv3Pipeline with all internals mocked (bypass __init__)."""
    p = CAMAv3Pipeline.__new__(CAMAv3Pipeline)
    p.similarity_threshold = 0.20
    p.matrix = MagicMock()
    p.matrix.nli = MagicMock()
    p.diagnoser = MagicMock()
    p.nli = p.matrix.nli
    # Clean defaults
    p.matrix.build.return_value = {"span_attributions": []}
    p.diagnoser.detect_ghosts.return_value = []
    p.diagnoser.detect_stale.return_value = []
    p.diagnoser.detect_contradictions.return_value = []
    p.diagnoser.build_memory_health_report.return_value = []
    p.diagnoser.compute_health.return_value = 100.0
    return p


# ─── TraceResult fields ───────────────────────────────────────────────────────

class TestTraceResultFields:
    def test_returns_trace_result(self, pipeline):
        result = pipeline.trace(query="q", response="r", memories=[])
        assert isinstance(result, TraceResult)

    def test_hallucinated_spans_always_empty(self, pipeline):
        result = pipeline.trace(query="q", response="r", memories=[])
        assert result.hallucinated_spans == []

    def test_hallucination_rate_always_zero(self, pipeline):
        result = pipeline.trace(query="q", response="r", memories=[])
        assert result.hallucination_rate == 0.0

    def test_detection_method_is_nlipairmatrix(self, pipeline):
        result = pipeline.trace(query="q", response="r", memories=[])
        assert result.detection_method == "NLIPairMatrix"

    def test_attribution_method_is_summac_direct(self, pipeline):
        result = pipeline.trace(query="q", response="r", memories=[])
        assert result.attribution_method == "SummaC-Direct"

    def test_query_and_response_preserved(self, pipeline):
        result = pipeline.trace(query="my query", response="my response", memories=[])
        assert result.query == "my query"
        assert result.response == "my response"

    def test_latency_ms_positive(self, pipeline):
        result = pipeline.trace(query="q", response="r", memories=[])
        assert result.latency_ms > 0


# ─── Memory handling ──────────────────────────────────────────────────────────

class TestMemoryHandling:
    def test_memories_used_contains_ids_from_dicts(self, pipeline):
        result = pipeline.trace(
            query="q",
            response="r",
            memories=[
                {"id": "m1", "content": "fact one"},
                {"id": "m2", "content": "fact two"},
            ],
        )
        assert result.memories_used == ["m1", "m2"]

    def test_accepts_memory_objects(self, pipeline):
        result = pipeline.trace(
            query="q",
            response="r",
            memories=[Memory(id="m1", content="fact")],
        )
        assert result.memories_used == ["m1"]

    def test_empty_memories(self, pipeline):
        result = pipeline.trace(query="q", response="r", memories=[])
        assert result.memories_used == []


# ─── Diagnostic propagation ───────────────────────────────────────────────────

class TestDiagnosticPropagation:
    def test_ghost_memories_propagated(self, pipeline):
        pipeline.diagnoser.detect_ghosts.return_value = ["m2"]
        result = pipeline.trace(
            query="q",
            response="r",
            memories=[
                {"id": "m1", "content": "relevant"},
                {"id": "m2", "content": "irrelevant"},
            ],
        )
        assert result.ghost_memories == ["m2"]

    def test_stale_memories_propagated(self, pipeline):
        pipeline.diagnoser.detect_stale.return_value = ["m1"]
        result = pipeline.trace(
            query="q",
            response="r",
            memories=[{"id": "m1", "content": "old fact"}],
        )
        assert result.stale_memories == ["m1"]

    def test_contradictions_propagated(self, pipeline):
        pipeline.diagnoser.detect_contradictions.return_value = [
            Contradiction(memory_id_1="m1", memory_id_2="m2", explanation="conflict"),
        ]
        result = pipeline.trace(
            query="q",
            response="r",
            memories=[
                {"id": "m1", "content": "A"},
                {"id": "m2", "content": "B"},
            ],
        )
        assert len(result.contradictions) == 1

    def test_health_score_from_diagnoser(self, pipeline):
        pipeline.diagnoser.compute_health.return_value = 75.0
        result = pipeline.trace(query="q", response="r", memories=[])
        assert result.health_score == 75.0

    def test_span_attributions_from_matrix(self, pipeline):
        sa = _make_span_attribution("sentence one")
        pipeline.matrix.build.return_value = {"span_attributions": [sa]}
        result = pipeline.trace(
            query="q",
            response="sentence one.",
            memories=[{"id": "m1", "content": "fact"}],
        )
        assert len(result.span_attributions) == 1


# ─── Stale culprit upgrade ────────────────────────────────────────────────────

class TestStaleCulpritUpgrade:
    def test_stale_culprit_upgrades_diagnosis_to_stale_memory(self, pipeline):
        """Spans whose culprit is in stale set should become 'stale_memory'."""
        sa = _make_span_attribution(
            sentence_text="The price is low.",
            memory_id="m1",
            direction="causing",
            diagnosis="wrong_memory",
            culprit="m1",
        )
        pipeline.matrix.build.return_value = {"span_attributions": [sa]}
        pipeline.diagnoser.detect_stale.return_value = ["m1"]

        result = pipeline.trace(
            query="q",
            response="The price is low.",
            memories=[{"id": "m1", "content": "old price info"}],
        )
        assert result.span_attributions[0].diagnosis == "stale_memory"

    def test_non_stale_culprit_keeps_wrong_memory_diagnosis(self, pipeline):
        """Spans whose culprit is NOT stale keep their original diagnosis."""
        sa = _make_span_attribution(
            sentence_text="The price is low.",
            memory_id="m1",
            direction="causing",
            diagnosis="wrong_memory",
            culprit="m1",
        )
        pipeline.matrix.build.return_value = {"span_attributions": [sa]}
        pipeline.diagnoser.detect_stale.return_value = []  # nothing stale

        result = pipeline.trace(
            query="q",
            response="The price is low.",
            memories=[{"id": "m1", "content": "correct current info"}],
        )
        assert result.span_attributions[0].diagnosis == "wrong_memory"

    def test_only_stale_culprit_upgraded_not_supported(self, pipeline):
        """Spans with diagnosis='supported' and culprit in stale set remain 'supported'."""
        sa_supported = _make_span_attribution(
            sentence_text="Good sentence.",
            memory_id="m2",
            direction="supporting",
            diagnosis="supported",
            culprit=None,  # no culprit
        )
        sa_culprit = _make_span_attribution(
            sentence_text="Bad sentence.",
            memory_id="m1",
            direction="causing",
            diagnosis="wrong_memory",
            culprit="m1",
        )
        pipeline.matrix.build.return_value = {
            "span_attributions": [sa_supported, sa_culprit],
        }
        pipeline.diagnoser.detect_stale.return_value = ["m1"]

        result = pipeline.trace(
            query="q",
            response="Good sentence. Bad sentence.",
            memories=[
                {"id": "m1", "content": "stale fact"},
                {"id": "m2", "content": "fresh fact"},
            ],
        )
        # sa_supported: culprit is None, not in stale_set → stays "supported"
        assert result.span_attributions[0].diagnosis == "supported"
        # sa_culprit: culprit "m1" in stale_set → upgraded
        assert result.span_attributions[1].diagnosis == "stale_memory"
