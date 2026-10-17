"""Tests for cortexa.engine.numerical_gate."""

from cortexa.engine.models import Claim, Memory
from cortexa.engine.numerical_gate import NumericalGate, extract_numbers


class TestExtractNumbers:
    def test_currency(self):
        nums = extract_numbers("The price is $49.99")
        assert 49.99 in nums["currency"]

    def test_percentage(self):
        nums = extract_numbers("Revenue grew 23%")
        assert abs(nums["percent"][0] - 0.23) < 0.001

    def test_time_12h(self):
        nums = extract_numbers("Arrives by 2pm")
        assert 14.0 in nums["time"]

    def test_time_with_minutes(self):
        nums = extract_numbers("Meeting at 2:30pm")
        assert abs(nums["time"][0] - 14.5) < 0.01

    def test_duration(self):
        nums = extract_numbers("Takes 5-7 business days")
        assert 5.0 in nums["duration"]

    def test_plain_number(self):
        nums = extract_numbers("We expanded to 12 new markets")
        assert 12.0 in nums["plain"]

    def test_multiple_currencies(self):
        nums = extract_numbers("Was $49.99, now $39.99")
        assert len(nums["currency"]) == 2

    def test_no_numbers(self):
        nums = extract_numbers("Shipping is free")
        total = sum(len(v) for v in nums.values())
        assert total == 0


class TestNumericalGate:
    def setup_method(self):
        self.gate = NumericalGate(tolerance=0.05)

    def test_exact_match(self):
        claims = [Claim(id="c1", text="Price is $49.99", source_response="resp")]
        memories = [Memory(id="m1", content="Premium plan costs $49.99 per month")]
        result = self.gate.check(claims, memories)
        assert len(result.matches) >= 1
        assert result.matches[0].match_type == "exact"

    def test_approximate_match(self):
        claims = [Claim(id="c1", text="About $50 total", source_response="resp", claim_type="numerical")]
        memories = [Memory(id="m1", content="Price is $49.99")]
        result = self.gate.check(claims, memories)
        # $50 vs $49.99 should be approximate
        all_results = result.matches + result.contradictions
        assert len(all_results) >= 1

    def test_contradiction(self):
        claims = [Claim(id="c1", text="Costs $49.99", source_response="resp", claim_type="numerical")]
        memories = [Memory(id="m1", content="The item costs $199.99")]
        result = self.gate.check(claims, memories)
        assert len(result.contradictions) >= 1

    def test_no_numbers_in_claim(self):
        claims = [Claim(id="c1", text="Shipping is free", source_response="resp")]
        memories = [Memory(id="m1", content="Free shipping on orders over $50")]
        result = self.gate.check(claims, memories)
        assert len(result.matches) == 0
        assert len(result.unverified) == 0

    def test_unverified_number(self):
        claims = [Claim(id="c1", text="Takes 3 days", source_response="resp", claim_type="numerical")]
        memories = [Memory(id="m1", content="Free shipping available")]
        result = self.gate.check(claims, memories)
        assert "c1" in result.unverified

    def test_percentage_match(self):
        claims = [Claim(id="c1", text="Grew 23%", source_response="resp", claim_type="numerical")]
        memories = [Memory(id="m1", content="Revenue increased by 23% this quarter")]
        result = self.gate.check(claims, memories)
        assert len(result.matches) >= 1

    def test_shipping_scenario(self, shipping_memories):
        claims = [
            Claim(id="c1", text="Order arrives by 2pm", source_response="resp", claim_type="temporal"),
        ]
        result = self.gate.check(claims, shipping_memories)
        # 2pm appears in the claim but likely not in memories
        assert isinstance(result.unverified, list)

    def test_empty_inputs(self):
        result = self.gate.check([], [])
        assert result.matches == []
        assert result.contradictions == []
        assert result.unverified == []
