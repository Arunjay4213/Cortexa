"""ContextCite Engine — slow-path attribution via ablation sensitivity + LASSO.

The real ContextCite algorithm sends N ablated prompts to the LLM API, each
with a different subset of memories removed, and gets back the mean
log-probability of the original response tokens under each ablated context.

Cost: ~64 forward passes per attribution run.  At ~4K token context and
$0.003/1K input tokens, that's ~$0.77 per run.  Cost is tracked and surfaced.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from cortex.attribution.llm_provider import LLMProvider, get_provider


@dataclass
class ContextCiteResult:
    """Result of a ContextCite attribution run."""
    scores: list[float]       # normalized attribution scores (sum ≈ 1)
    raw_scores: list[float]   # raw LASSO weights
    lds: float                # Linear Datamodeling Score (Pearson r)
    compute_ms: float         # wall-clock time
    cost_usd: float           # estimated API cost
    num_samples: int          # ablation samples used
    memory_ids: list[str]     # corresponding memory IDs


class ContextCiteEngine:
    """Slow-path attribution via ablation sensitivity analysis + LASSO."""

    def __init__(
        self,
        num_samples: int = 64,
        lasso_lambda: float = 0.1,
        provider_name: str = "mock",
        api_key: str = "",
        input_price_per_1k: float = 0.003,
        output_price_per_1k: float = 0.015,
    ):
        self.num_samples = num_samples
        self.lasso_lambda = lasso_lambda
        self.provider = get_provider(provider_name, api_key)
        self.input_price_per_1k = input_price_per_1k
        self.output_price_per_1k = output_price_per_1k

    async def compute_attribution(
        self,
        query_text: str,
        memories_text: list[str],
        memory_ids: list[str],
        response_text: str,
    ) -> ContextCiteResult:
        """Run full ContextCite attribution.

        1. Generate ablation masks
        2. Score each ablated context via LLM
        3. Fit LASSO regression
        4. Compute LDS quality metric
        """
        t0 = time.perf_counter()
        k = len(memories_text)

        if k == 0:
            return ContextCiteResult(
                scores=[], raw_scores=[], lds=0.0,
                compute_ms=0.0, cost_usd=0.0, num_samples=0, memory_ids=[],
            )

        # Step 1: Generate ablation masks
        Z = self._generate_ablation_masks(k, self.num_samples)

        # Step 2: Compute log-probs for each ablated context
        y = await self._compute_log_probs(Z, query_text, memories_text, response_text)

        # Step 3: Fit LASSO regression
        weights = self._fit_lasso(Z, np.array(y), self.lasso_lambda)

        # Step 4: Compute LDS
        lds = self._compute_lds(Z, np.array(y), weights)

        # Normalize scores
        raw_scores = weights.tolist()
        abs_weights = np.abs(weights)
        total = abs_weights.sum()
        if total > 0:
            scores = (abs_weights / total).tolist()
        else:
            # LASSO found no explanatory power — return zeros, not
            # a misleading uniform distribution that implies equal attribution.
            scores = [0.0] * k

        elapsed_ms = (time.perf_counter() - t0) * 1000
        cost = self.provider.usage.cost_usd(
            self.input_price_per_1k, self.output_price_per_1k
        )

        return ContextCiteResult(
            scores=scores,
            raw_scores=raw_scores,
            lds=float(lds),
            compute_ms=elapsed_ms,
            cost_usd=cost,
            num_samples=self.num_samples,
            memory_ids=memory_ids,
        )

    @staticmethod
    def _generate_ablation_masks(k: int, num_samples: int) -> np.ndarray:
        """Generate binary ablation mask matrix (num_samples x k).

        Row 0: all-zeros (no memories)
        Row 1: all-ones (all memories)
        Rows 2+: random Bernoulli(0.5) masks
        """
        Z = np.zeros((num_samples, k), dtype=np.float64)
        Z[0, :] = 0.0  # baseline: no memories
        if num_samples > 1:
            Z[1, :] = 1.0  # baseline: all memories

        if num_samples > 2:
            Z[2:, :] = (np.random.rand(num_samples - 2, k) > 0.5).astype(np.float64)

        return Z

    async def _compute_log_probs(
        self,
        masks: np.ndarray,
        query_text: str,
        memories_text: list[str],
        response_text: str,
    ) -> list[float]:
        """Score each ablated context via the LLM provider.

        For each mask: build ablated context (query + subset of memories),
        call provider to score the original response.
        Returns mean log-prob of response tokens under each ablated context.
        """
        log_probs: list[float] = []

        for i in range(masks.shape[0]):
            mask = masks[i]
            # Build ablated context
            included_memories = [
                memories_text[j]
                for j in range(len(memories_text))
                if mask[j] > 0.5
            ]
            context = f"Query: {query_text}\n\nRelevant memories:\n"
            if included_memories:
                context += "\n".join(f"- {m}" for m in included_memories)
            else:
                context += "(no memories available)"

            result = await self.provider.score_response(context, response_text)
            log_probs.append(result.mean_log_prob)

        return log_probs

    @staticmethod
    def _fit_lasso(Z: np.ndarray, y: np.ndarray, lambda_: float) -> np.ndarray:
        """Coordinate descent LASSO solver.

        Minimizes: (1/2n)||y - Zw||² + λ||w||₁

        Returns sparse weight vector w of shape (k,).
        """
        n, k = Z.shape
        if n == 0 or k == 0:
            return np.zeros(k)

        # Standardize
        y_centered = y - y.mean()
        Z_centered = Z - Z.mean(axis=0)

        w = np.zeros(k)
        max_iter = 1000
        tol = 1e-6

        for _ in range(max_iter):
            w_old = w.copy()
            for j in range(k):
                # Compute partial residual
                residual = y_centered - Z_centered @ w + Z_centered[:, j] * w[j]
                rho = Z_centered[:, j] @ residual / n

                # Soft thresholding
                z_sq = (Z_centered[:, j] ** 2).sum() / n
                if z_sq == 0:
                    w[j] = 0.0
                else:
                    if rho > lambda_:
                        w[j] = (rho - lambda_) / z_sq
                    elif rho < -lambda_:
                        w[j] = (rho + lambda_) / z_sq
                    else:
                        w[j] = 0.0

            # Check convergence
            if np.max(np.abs(w - w_old)) < tol:
                break

        return w

    @staticmethod
    def _compute_lds(Z: np.ndarray, y: np.ndarray, weights: np.ndarray) -> float:
        """Linear Datamodeling Score — Pearson correlation between predicted and actual.

        LDS measures how well the linear model fits the ablation data.
        LDS > 0.85 indicates reliable attribution.
        """
        if Z.shape[0] < 3:
            return 0.0

        y_pred = Z @ weights

        # Pearson correlation
        y_mean = y.mean()
        yp_mean = y_pred.mean()
        y_diff = y - y_mean
        yp_diff = y_pred - yp_mean

        numerator = (y_diff * yp_diff).sum()
        denominator = np.sqrt((y_diff ** 2).sum() * (yp_diff ** 2).sum())

        if denominator < 1e-10:
            return 0.0

        return float(numerator / denominator)
