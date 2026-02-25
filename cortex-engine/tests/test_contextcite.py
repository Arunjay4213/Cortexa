"""Tests for ContextCite engine — LASSO, mask generation, LDS, MockProvider."""

import asyncio

import numpy as np
import pytest

from cortex.attribution.contextcite import ContextCiteEngine


class TestMaskGeneration:
    def test_mask_dimensions(self):
        masks = ContextCiteEngine._generate_ablation_masks(5, 64)
        assert masks.shape == (64, 5)

    def test_first_row_all_zeros(self):
        masks = ContextCiteEngine._generate_ablation_masks(3, 10)
        assert (masks[0] == 0).all()

    def test_second_row_all_ones(self):
        masks = ContextCiteEngine._generate_ablation_masks(3, 10)
        assert (masks[1] == 1).all()

    def test_random_masks_binary(self):
        masks = ContextCiteEngine._generate_ablation_masks(10, 100)
        unique_vals = set(masks.flatten())
        assert unique_vals.issubset({0.0, 1.0})

    def test_single_memory(self):
        masks = ContextCiteEngine._generate_ablation_masks(1, 10)
        assert masks.shape == (10, 1)


class TestLASSOFit:
    def test_convergence_known_data(self):
        """LASSO should recover sparse weights from synthetic data."""
        np.random.seed(42)
        k = 5
        n = 100
        Z = (np.random.rand(n, k) > 0.5).astype(np.float64)
        true_weights = np.array([0.5, 0.0, 0.3, 0.0, 0.2])
        y = Z @ true_weights + np.random.normal(0, 0.01, n)

        weights = ContextCiteEngine._fit_lasso(Z, y, lambda_=0.01)

        # Should be close to true weights
        np.testing.assert_allclose(weights, true_weights, atol=0.1)

    def test_sparsity(self):
        """LASSO with high lambda should produce sparse weights."""
        np.random.seed(42)
        k = 10
        n = 64
        Z = (np.random.rand(n, k) > 0.5).astype(np.float64)
        true_weights = np.zeros(k)
        true_weights[0] = 1.0
        y = Z @ true_weights + np.random.normal(0, 0.01, n)

        weights = ContextCiteEngine._fit_lasso(Z, y, lambda_=0.5)

        # Most weights should be zero
        zero_count = np.sum(np.abs(weights) < 0.01)
        assert zero_count >= 5

    def test_empty_input(self):
        Z = np.zeros((0, 0))
        y = np.array([])
        weights = ContextCiteEngine._fit_lasso(Z, y, 0.1)
        assert weights.shape == (0,)


class TestLDS:
    def test_perfect_fit(self):
        """Perfect linear relationship should give LDS ≈ 1."""
        Z = np.array([[0, 1], [1, 0], [1, 1], [0, 0]], dtype=np.float64)
        weights = np.array([0.3, 0.7])
        y = Z @ weights

        lds = ContextCiteEngine._compute_lds(Z, y, weights)
        assert lds > 0.99

    def test_no_correlation(self):
        """Random noise should give low LDS."""
        np.random.seed(42)
        Z = np.random.rand(50, 3)
        y = np.random.rand(50)
        weights = np.zeros(3)

        lds = ContextCiteEngine._compute_lds(Z, y, weights)
        assert abs(lds) < 0.5

    def test_too_few_samples(self):
        Z = np.array([[1, 0]], dtype=np.float64)
        y = np.array([0.5])
        weights = np.array([0.5, 0.0])

        lds = ContextCiteEngine._compute_lds(Z, y, weights)
        assert lds == 0.0


class TestMockProviderEndToEnd:
    @pytest.mark.asyncio
    async def test_compute_attribution(self):
        """End-to-end test with MockProvider (no API key needed)."""
        engine = ContextCiteEngine(
            num_samples=16,  # fewer for test speed
            lasso_lambda=0.1,
            provider_name="mock",
        )

        result = await engine.compute_attribution(
            query_text="What is the capital of France?",
            memories_text=[
                "Paris is the capital of France.",
                "The Eiffel Tower is in Paris.",
                "Berlin is the capital of Germany.",
            ],
            memory_ids=["m1", "m2", "m3"],
            response_text="The capital of France is Paris.",
        )

        assert len(result.scores) == 3
        assert len(result.raw_scores) == 3
        assert result.compute_ms > 0
        assert result.cost_usd >= 0
        assert result.num_samples == 16

        # Scores should either sum to ~1.0 (LASSO found signal)
        # or be all zeros (LASSO found no explanatory power at this lambda).
        # Both are valid — zeros are honest, unlike a fake uniform distribution.
        total = sum(result.scores)
        assert abs(total - 1.0) < 0.01 or total == 0.0

    @pytest.mark.asyncio
    async def test_empty_memories(self):
        engine = ContextCiteEngine(num_samples=8, provider_name="mock")

        result = await engine.compute_attribution(
            query_text="test",
            memories_text=[],
            memory_ids=[],
            response_text="test response",
        )

        assert result.scores == []
        assert result.cost_usd == 0.0


class TestCostTracking:
    @pytest.mark.asyncio
    async def test_cost_increases_with_samples(self):
        engine = ContextCiteEngine(num_samples=8, provider_name="mock")

        result = await engine.compute_attribution(
            query_text="test query",
            memories_text=["memory 1", "memory 2"],
            memory_ids=["m1", "m2"],
            response_text="response text",
        )

        # MockProvider tracks usage
        assert engine.provider.usage.total_calls == 8
        assert engine.provider.usage.total_input_tokens > 0
