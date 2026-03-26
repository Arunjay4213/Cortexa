"""Tests for cama/matrix.py — NLIPairMatrix (mock-based, no model loading)."""

from unittest.mock import MagicMock

import pytest

from cama.matrix import NLIPairMatrix
from cama.types import Memory


@pytest.fixture
def matrix():
    """NLIPairMatrix with NLI model replaced by a MagicMock."""
    m = NLIPairMatrix(model_name="mock-model")
    m.nli = MagicMock()
    return m


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _supporting():
    return {"contradiction": 0.1, "entailment": 2.0, "neutral": 0.1}


def _causing():
    return {"contradiction": 2.0, "entailment": 0.1, "neutral": 0.1}


def _ghost():
    return {"contradiction": 0.1, "entailment": 0.1, "neutral": 5.0}


# ─── Empty / degenerate inputs ────────────────────────────────────────────────

class TestBuildEdgeCases:
    def test_empty_response(self, matrix):
        mems = [Memory(id="m1", content="some fact")]
        result = matrix.build("", mems)
        assert result["span_attributions"] == []

    def test_whitespace_response(self, matrix):
        mems = [Memory(id="m1", content="some fact")]
        result = matrix.build("   ", mems)
        assert result["span_attributions"] == []

    def test_empty_memories(self, matrix):
        result = matrix.build("The sky is blue.", [])
        assert result["span_attributions"] == []

    def test_returns_span_attributions_key(self, matrix):
        matrix.nli.predict_batch.return_value = [_supporting()]
        mems = [Memory(id="m1", content="sky is blue")]
        result = matrix.build("The sky is blue.", mems)
        assert "span_attributions" in result
        assert isinstance(result["span_attributions"], list)


# ─── Direction classification ─────────────────────────────────────────────────

class TestDirectionClassification:
    def test_supporting_direction(self, matrix):
        matrix.nli.predict_batch.return_value = [_supporting()]
        mems = [Memory(id="m1", content="sky is blue")]
        result = matrix.build("The sky is blue.", mems)
        sa = result["span_attributions"][0]
        m1_attr = next(a for a in sa.attributions if a.memory_id == "m1")
        assert m1_attr.direction == "supporting"

    def test_causing_direction(self, matrix):
        matrix.nli.predict_batch.return_value = [_causing()]
        mems = [Memory(id="m1", content="wrong fact")]
        result = matrix.build("The sky is blue.", mems)
        sa = result["span_attributions"][0]
        m1_attr = next(a for a in sa.attributions if a.memory_id == "m1")
        assert m1_attr.direction == "causing"

    def test_ghost_neutral_dominant(self, matrix):
        matrix.nli.predict_batch.return_value = [_ghost()]
        mems = [Memory(id="m1", content="irrelevant fact")]
        result = matrix.build("The sky is blue.", mems)
        sa = result["span_attributions"][0]
        m1_attr = next(a for a in sa.attributions if a.memory_id == "m1")
        assert m1_attr.direction == "ghost"

    def test_ghost_when_diff_below_threshold(self, matrix):
        # diff = entail - contra = 0.4 < default threshold 0.5 → ghost
        matrix.nli.predict_batch.return_value = [
            {"contradiction": 0.5, "entailment": 0.9, "neutral": 0.1},
        ]
        mems = [Memory(id="m1", content="ambiguous fact")]
        result = matrix.build("Some statement here.", mems)
        sa = result["span_attributions"][0]
        m1_attr = next(a for a in sa.attributions if a.memory_id == "m1")
        assert m1_attr.direction == "ghost"


# ─── Culprit and diagnosis ────────────────────────────────────────────────────

class TestCulpritAndDiagnosis:
    def test_causing_sets_culprit(self, matrix):
        matrix.nli.predict_batch.return_value = [_causing()]
        mems = [Memory(id="m1", content="wrong fact")]
        result = matrix.build("The sky is blue.", mems)
        sa = result["span_attributions"][0]
        assert sa.culprit_memory_id == "m1"
        assert sa.diagnosis == "wrong_memory"

    def test_no_culprit_when_only_supporting(self, matrix):
        matrix.nli.predict_batch.return_value = [_supporting()]
        mems = [Memory(id="m1", content="correct fact")]
        result = matrix.build("The sky is blue.", mems)
        sa = result["span_attributions"][0]
        assert sa.culprit_memory_id is None
        assert sa.diagnosis == "supported"

    def test_all_ghosts_fabricated_diagnosis(self, matrix):
        matrix.nli.predict_batch.return_value = [_ghost(), _ghost()]
        mems = [
            Memory(id="m1", content="irrelevant a"),
            Memory(id="m2", content="irrelevant b"),
        ]
        result = matrix.build("The sky is blue.", mems)
        sa = result["span_attributions"][0]
        assert sa.diagnosis == "fabricated"
        assert sa.culprit_memory_id is None

    def test_culprit_is_first_causing_memory(self, matrix):
        # m1 is ghost, m2 is causing → culprit = m2
        matrix.nli.predict_batch.return_value = [_ghost(), _causing()]
        mems = [
            Memory(id="m1", content="irrelevant"),
            Memory(id="m2", content="wrong fact"),
        ]
        result = matrix.build("Some statement.", mems)
        sa = result["span_attributions"][0]
        assert sa.culprit_memory_id == "m2"


# ─── Span content and structure ───────────────────────────────────────────────

class TestSpanStructure:
    def test_span_text_matches_sentence(self, matrix):
        matrix.nli.predict_batch.return_value = [_supporting()]
        mems = [Memory(id="m1", content="fact")]
        result = matrix.build("The sky is blue.", mems)
        sa = result["span_attributions"][0]
        assert sa.span.text == "The sky is blue."

    def test_span_char_offsets_set(self, matrix):
        matrix.nli.predict_batch.return_value = [_supporting()]
        mems = [Memory(id="m1", content="fact")]
        result = matrix.build("The sky is blue.", mems)
        sa = result["span_attributions"][0]
        assert sa.span.start_char == 0
        assert sa.span.end_char == len("The sky is blue.")

    def test_multiple_sentences_multiple_spans(self, matrix):
        # Two sentences → two SpanAttributions
        matrix.nli.predict_batch.return_value = [_supporting(), _supporting()]
        mems = [Memory(id="m1", content="fact")]
        result = matrix.build("First sentence. Second sentence.", mems)
        assert len(result["span_attributions"]) == 2


# ─── Sorting and MAS ─────────────────────────────────────────────────────────

class TestSortingAndMAS:
    def test_causing_ranks_before_supporting(self, matrix):
        matrix.nli.predict_batch.return_value = [
            _causing(),    # m1
            _supporting(), # m2
        ]
        mems = [
            Memory(id="m1", content="wrong fact"),
            Memory(id="m2", content="correct fact"),
        ]
        result = matrix.build("Some statement.", mems)
        sa = result["span_attributions"][0]
        assert sa.attributions[0].direction == "causing"

    def test_mas_nonnegative(self, matrix):
        matrix.nli.predict_batch.return_value = [_supporting(), _causing()]
        mems = [
            Memory(id="m1", content="correct"),
            Memory(id="m2", content="wrong"),
        ]
        result = matrix.build("Some statement.", mems)
        sa = result["span_attributions"][0]
        for attr in sa.attributions:
            assert attr.mas >= 0.0

    def test_attributions_count_matches_memories(self, matrix):
        matrix.nli.predict_batch.return_value = [
            _supporting(), _ghost(), _causing(),
        ]
        mems = [
            Memory(id="m1", content="a"),
            Memory(id="m2", content="b"),
            Memory(id="m3", content="c"),
        ]
        result = matrix.build("Some statement.", mems)
        sa = result["span_attributions"][0]
        assert len(sa.attributions) == 3
