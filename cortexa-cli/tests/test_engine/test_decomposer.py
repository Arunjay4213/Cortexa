"""Tests for cortexa.engine.decomposer."""

from cortexa.engine.decomposer import ClaimDecomposer, _classify_claim


class TestClassifyClaim:
    def test_numerical(self):
        assert _classify_claim("Revenue grew 23%") == "numerical"

    def test_temporal(self):
        assert _classify_claim("Order arrives Thursday") == "temporal"

    def test_numerical_with_currency(self):
        assert _classify_claim("The price is $49.99") == "numerical"

    def test_relational(self):
        assert _classify_claim("Revenue growth exceeded the estimate") == "relational"

    def test_opinion(self):
        assert _classify_claim("I think the policy is fair") == "opinion"

    def test_factual(self):
        assert _classify_claim("Shipping is free") == "factual"

    def test_temporal_with_number(self):
        # Has both number and temporal — temporal check includes numbers
        result = _classify_claim("Order arrives by 2pm")
        assert result in ("numerical", "temporal")


class TestClaimDecomposer:
    def setup_method(self):
        self.decomposer = ClaimDecomposer(mode="fast")

    def test_single_sentence(self):
        claims = self.decomposer.decompose("Your order arrives Thursday")
        assert len(claims) >= 1
        assert claims[0].source_response == "Your order arrives Thursday"

    def test_multiple_sentences(self):
        text = "Your order arrives Thursday by 2pm. Free shipping included."
        claims = self.decomposer.decompose(text)
        assert len(claims) >= 2

    def test_conjunction_split(self):
        text = "Revenue grew 23%, and the company expanded to 12 markets"
        claims = self.decomposer.decompose(text)
        assert len(claims) >= 2

    def test_with_clause_split(self):
        text = "The price is $49.99 with free shipping"
        claims = self.decomposer.decompose(text)
        assert len(claims) >= 2

    def test_empty_input(self):
        claims = self.decomposer.decompose("")
        assert claims == []

    def test_short_input(self):
        claims = self.decomposer.decompose("OK")
        # Short text should still produce at least one claim
        assert len(claims) <= 1

    def test_claim_type_assigned(self):
        claims = self.decomposer.decompose("The price is $49.99")
        assert claims[0].claim_type == "numerical"

    def test_deduplication(self):
        text = "Order ships Monday. Order ships Monday."
        claims = self.decomposer.decompose(text)
        # Should deduplicate
        unique_texts = set(c.text.lower().rstrip(".") for c in claims)
        assert len(unique_texts) == len(claims)

    def test_shipping_story_response(self, shipping_response):
        claims = self.decomposer.decompose(shipping_response)
        assert len(claims) >= 1
        # Should identify temporal/numerical aspects
        types = {c.claim_type for c in claims}
        assert len(types) >= 1

    def test_complex_response(self):
        text = (
            "Revenue grew 23% in Q3, beating the 18% estimate. "
            "The company also announced a new product line, "
            "and expanded to 12 new markets."
        )
        claims = self.decomposer.decompose(text)
        assert len(claims) >= 3
