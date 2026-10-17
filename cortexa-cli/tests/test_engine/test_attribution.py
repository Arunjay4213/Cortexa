"""Tests for cortexa.engine.attribution."""

import math

from cortexa.engine.attribution import AttributionComputer, _softmax_with_temperature
from cortexa.engine.models import Attribution, Claim, EntailmentScore, Memory


class TestSoftmaxWithTemperature:
    def test_uniform_input(self):
        result = _softmax_with_temperature([1.0, 1.0, 1.0], temperature=0.5)
        assert len(result) == 3
        assert all(abs(v - 1 / 3) < 0.001 for v in result)

    def test_sums_to_one(self):
        result = _softmax_with_temperature([0.1, 0.5, 0.9], temperature=0.5)
        assert abs(sum(result) - 1.0) < 0.001

    def test_higher_temp_flatter(self):
        vals = [0.1, 0.9]
        low_temp = _softmax_with_temperature(vals, temperature=0.1)
        high_temp = _softmax_with_temperature(vals, temperature=2.0)
        # Low temperature should make distribution more peaked
        assert low_temp[1] > high_temp[1]

    def test_empty(self):
        assert _softmax_with_temperature([]) == []

    def test_single_value(self):
        result = _softmax_with_temperature([0.5], temperature=0.5)
        assert len(result) == 1
        assert abs(result[0] - 1.0) < 0.001


class TestAttributionComputer:
    def setup_method(self):
        self.computer = AttributionComputer(temperature=0.5, ghost_threshold=0.05)

    def test_basic_attribution(self):
        claims = [Claim(id="c1", text="Price is $49.99", source_response="resp")]
        memories = [
            Memory(id="m1", content="Premium plan costs $49.99"),
            Memory(id="m2", content="Free shipping available"),
        ]
        entailments = [
            EntailmentScore(
                memory_id="m1", claim_id="c1",
                entailment=0.9, contradiction=0.05, neutral=0.05,
                label="entailment", confidence=0.9,
            ),
            EntailmentScore(
                memory_id="m2", claim_id="c1",
                entailment=0.1, contradiction=0.1, neutral=0.8,
                label="neutral", confidence=0.8,
            ),
        ]

        attrs = self.computer.compute(claims, memories, entailments)
        assert len(attrs) == 2

        # m1 should have higher MAS (entails the claim)
        m1_attr = next(a for a in attrs if a.memory_id == "m1")
        m2_attr = next(a for a in attrs if a.memory_id == "m2")
        assert m1_attr.mas_score > m2_attr.mas_score

    def test_mas_sums_to_one_per_claim(self):
        claims = [Claim(id="c1", text="test", source_response="resp")]
        memories = [Memory(id=f"m{i}", content=f"memory {i}") for i in range(5)]
        entailments = [
            EntailmentScore(
                memory_id=f"m{i}", claim_id="c1",
                entailment=0.2 * i, contradiction=0.1, neutral=0.9 - 0.2 * i,
                label="neutral", confidence=0.5,
            )
            for i in range(5)
        ]

        attrs = self.computer.compute(claims, memories, entailments)
        total_mas = sum(a.mas_score for a in attrs)
        assert abs(total_mas - 1.0) < 0.01

    def test_supporting_classification(self):
        claims = [Claim(id="c1", text="test", source_response="resp")]
        memories = [Memory(id="m1", content="test")]
        entailments = [
            EntailmentScore(
                memory_id="m1", claim_id="c1",
                entailment=0.8, contradiction=0.1, neutral=0.1,
                label="entailment", confidence=0.8,
            ),
        ]

        attrs = self.computer.compute(claims, memories, entailments)
        assert attrs[0].contribution_type == "supporting"

    def test_contradicting_classification(self):
        claims = [Claim(id="c1", text="test", source_response="resp")]
        memories = [Memory(id="m1", content="test")]
        entailments = [
            EntailmentScore(
                memory_id="m1", claim_id="c1",
                entailment=0.1, contradiction=0.8, neutral=0.1,
                label="contradiction", confidence=0.8,
            ),
        ]

        attrs = self.computer.compute(claims, memories, entailments)
        assert attrs[0].contribution_type == "contradicting"

    def test_ghost_classification(self):
        """With many memories, low-entailment ones get MAS < threshold."""
        claims = [Claim(id="c1", text="test", source_response="resp")]
        # Need enough memories and big entailment gap so softmax pushes low ones below 0.05
        memories = [Memory(id=f"m{i}", content=f"memory {i}") for i in range(10)]
        entailments = [
            EntailmentScore(
                memory_id="m0", claim_id="c1",
                entailment=0.95, contradiction=0.0, neutral=0.05,
                label="entailment", confidence=0.95,
            ),
            EntailmentScore(
                memory_id="m1", claim_id="c1",
                entailment=0.85, contradiction=0.0, neutral=0.15,
                label="entailment", confidence=0.85,
            ),
        ] + [
            EntailmentScore(
                memory_id=f"m{i}", claim_id="c1",
                entailment=0.0, contradiction=0.0, neutral=1.0,
                label="neutral", confidence=1.0,
            )
            for i in range(2, 10)
        ]

        attrs = self.computer.compute(claims, memories, entailments)
        m9_attr = next(a for a in attrs if a.memory_id == "m9")
        assert m9_attr.contribution_type == "ghost"
        assert m9_attr.mas_score < 0.05

    def test_aggregate_mas(self):
        attrs = [
            Attribution(
                claim_id="c1", memory_id="m1", mas_score=0.3,
                entailment_score=0.5, contribution_type="supporting",
            ),
            Attribution(
                claim_id="c2", memory_id="m1", mas_score=0.5,
                entailment_score=0.7, contribution_type="supporting",
            ),
            Attribution(
                claim_id="c1", memory_id="m2", mas_score=0.1,
                entailment_score=0.1, contribution_type="ghost",
            ),
        ]
        avg = self.computer.aggregate_mas(attrs, "m1")
        assert abs(avg - 0.4) < 0.001  # (0.3 + 0.5) / 2

    def test_aggregate_mas_unknown_memory(self):
        assert self.computer.aggregate_mas([], "unknown") == 0.0

    def test_missing_entailment_treated_as_neutral(self):
        claims = [Claim(id="c1", text="test", source_response="resp")]
        memories = [Memory(id="m1", content="test")]
        entailments = []  # no entailments provided

        attrs = self.computer.compute(claims, memories, entailments)
        assert len(attrs) == 1
        assert attrs[0].entailment_score == 0.0
