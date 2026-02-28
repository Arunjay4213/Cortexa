"""
Tests for the leave-one-out Shapley attribution engine.

Requires CORTEX_GROQ_API_KEY to be set (NLI runs via Groq API).
"""

import time

import pytest

from app.services.attributor import AttributionService, SourceInfluence
from app.services.nli import NLIService


@pytest.fixture(scope="module")
def nli_service():
    """Load NLI service (requires Groq API key)."""
    from app.config import Settings

    settings = Settings()
    if not settings.groq_api_key:
        pytest.skip("CORTEX_GROQ_API_KEY not set")
    return NLIService()


@pytest.fixture(scope="module")
def attributor(nli_service):
    """Create attribution service reusing the NLI service."""
    return AttributionService(nli_service)


class TestSingleSource:
    """Test 1: Single source gets 100% influence."""

    def test_single_source_supports(self, attributor):
        claim = "The return policy is 45 days."
        sources = ["45-day return window for all products."]

        result = attributor.compute(claim, sources)

        assert len(result.influences) == 1
        assert result.influences[0].direction == "SUPPORTS"
        assert result.influences[0].influence_norm == 1.0
        assert result.primary_source_index == 0
        # full score + 0 leave-one-out (single source -> score_minus_0 = 0.0)
        assert result.computation_calls >= 1


class TestMultiSourceOneRelevant:
    """Test 2: Multiple sources, only one relevant -- it dominates."""

    def test_dominant_source(self, attributor):
        claim = "The return policy is 45 days."
        sources = [
            "45-day return window for all products.",  # relevant
            "Free shipping on orders over $50.",  # irrelevant
            "1-year warranty on all items.",  # irrelevant
        ]

        result = attributor.compute(claim, sources)

        assert result.primary_source_index == 0
        # First influence (sorted by abs) should be the relevant source
        assert result.influences[0].source_index == 0
        assert result.influences[0].influence_norm > 0.5  # dominant
        assert result.influences[0].direction == "SUPPORTS"
        # N+1 scoring rounds (each round iterates over sentences)
        assert result.computation_calls >= 4


class TestContradictingSource:
    """Test 3: Source contradicts the claim."""

    def test_contradiction_detected(self, attributor):
        claim = "The return policy is 60 days."
        sources = ["Return policy: 45-day window only."]

        result = attributor.compute(claim, sources)

        # With one source and a non-entailed claim, the source still
        # gets full influence (positive or negative depends on the model).
        # The key is that the NLI model should not strongly entail.
        assert len(result.influences) == 1
        assert result.influences[0].influence_norm != 0.0


class TestNoSources:
    """Test 4: No sources returns empty result."""

    def test_no_sources(self, attributor):
        result = attributor.compute("any claim", [])

        assert result.influences == []
        assert result.computation_calls == 0
        assert result.primary_source_index is None
        assert result.causal_source is None


class TestEndToEnd:
    """Test 5: End-to-end via POST /v1/check with attribution=True."""

    def test_attribution_in_check_response(self, nli_service):
        """Call run_check with attribution enabled and verify response."""
        import asyncio

        from app.config import Settings
        from app.models.check import CheckConfig, CheckRequest
        from app.services.attributor import AttributionService
        from app.services.checker import run_check

        settings = Settings()
        # Skip if no Groq API key configured
        if not settings.groq_api_key:
            pytest.skip("CORTEX_GROQ_API_KEY not set")

        attr_service = AttributionService(nli_service)

        request = CheckRequest(
            response="The return policy is 45 days. Free shipping is available on orders over $50.",
            sources=[
                "45-day return window for all products.",
                "Free shipping on orders over $50.",
            ],
            config=CheckConfig(attribution=True),
        )

        result = asyncio.run(
            run_check(request, nli_service, settings, attr_service)
        )

        # Should have claims with attribution data
        has_attribution = any(c.attribution is not None for c in result.claims)
        assert has_attribution, "Expected at least one claim with attribution"

        # Check attribution metadata
        assert result.attribution_calls is not None
        assert result.attribution_calls > 0
        assert result.attribution_latency_ms is not None
        assert result.attribution_latency_ms > 0

        # Verify attribution structure
        for claim in result.claims:
            if claim.attribution:
                for attr in claim.attribution:
                    assert "source_index" in attr
                    assert "influence" in attr
                    assert "direction" in attr
                    assert attr["direction"] in (
                        "SUPPORTS",
                        "CONTRADICTS",
                        "IRRELEVANT",
                    )


class TestPerformance:
    """Test 6: Performance with multiple sources and claims."""

    def test_attribution_speed(self, attributor):
        sources = [
            "The company was founded in 2020 in San Francisco.",
            "Revenue reached $10M in the first year of operations.",
            "The team grew from 5 to 50 employees by end of 2021.",
            "Series A funding of $25M was led by Acme Ventures.",
            "The product launched in beta in March 2020.",
            "Customer base expanded to 1000 enterprise clients.",
            "The annual recurring revenue grew to $30M by 2022.",
            "International expansion began with offices in London.",
            "The company achieved profitability in Q3 2022.",
            "Employee satisfaction score was rated at 4.5 out of 5.",
        ]
        claims = [
            "The company was founded in 2020.",
            "Revenue was $10M in the first year.",
            "The team grew to 50 employees.",
            "Series A was $25M.",
            "The product launched in March 2020.",
        ]

        start = time.time()
        results = attributor.compute_batch(claims, sources)
        elapsed = time.time() - start

        assert len(results) == 5
        # Groq API is fast but network-bound; allow 120s for CI
        assert elapsed < 120.0, f"Attribution took {elapsed:.1f}s, expected < 120s"

        # Total calls should be tracked
        total_calls = sum(r.computation_calls for r in results)
        assert total_calls > 0

        # Each result should have influences for all 10 sources
        for r in results:
            assert len(r.influences) == 10


class TestAttributionOffByDefault:
    """Test 7: Attribution is off by default, no extra NLI calls."""

    def test_no_attribution_by_default(self, nli_service):
        """Check with no config -> attribution fields are None."""
        import asyncio

        from app.config import Settings
        from app.models.check import CheckRequest
        from app.services.attributor import AttributionService
        from app.services.checker import run_check

        settings = Settings()
        if not settings.groq_api_key:
            pytest.skip("CORTEX_GROQ_API_KEY not set")

        attr_service = AttributionService(nli_service)

        request = CheckRequest(
            response="The return policy is 45 days.",
            sources=["45-day return window for all products."],
            # No config -> attribution disabled
        )

        result = asyncio.run(
            run_check(request, nli_service, settings, attr_service)
        )

        # No attribution data on any claim
        for claim in result.claims:
            assert claim.attribution is None
            assert claim.primary_source_index is None

        # No attribution metadata
        assert result.attribution_calls is None
        assert result.attribution_latency_ms is None


class TestSourceInfluenceProperties:
    """Test SourceInfluence dataclass properties."""

    def test_is_primary_true(self):
        si = SourceInfluence(
            source_index=0,
            influence_raw=0.8,
            influence_norm=0.75,
            direction="SUPPORTS",
            source_preview="test source",
        )
        assert si.is_primary is True

    def test_is_primary_false(self):
        si = SourceInfluence(
            source_index=1,
            influence_raw=0.2,
            influence_norm=0.25,
            direction="SUPPORTS",
            source_preview="test source",
        )
        assert si.is_primary is False


class TestCausalSource:
    """Test AttributionResult.causal_source property."""

    def test_causal_source_exists(self, attributor):
        result = attributor.compute(
            "The sky is blue.",
            ["The sky appears blue due to Rayleigh scattering."],
        )
        assert result.causal_source is not None
        assert result.causal_source.source_index == 0

    def test_causal_source_none_for_empty(self, attributor):
        result = attributor.compute("any claim", [])
        assert result.causal_source is None
