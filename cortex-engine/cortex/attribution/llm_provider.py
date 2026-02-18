"""LLM Provider abstraction for ContextCite log-probability scoring.

Each provider implements `score_response()` — given a context and response,
return the mean log-probability of the response tokens.  This is the core
operation needed for ContextCite's ablation sensitivity analysis.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np


@dataclass
class ScoringResult:
    """Result from a single log-probability scoring call."""
    mean_log_prob: float
    tokens_scored: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ProviderUsage:
    """Accumulated token usage for cost tracking."""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_calls: int = 0

    def add(self, result: ScoringResult) -> None:
        self.total_input_tokens += result.input_tokens
        self.total_output_tokens += result.output_tokens
        self.total_calls += 1

    def cost_usd(self, input_price_per_1k: float, output_price_per_1k: float) -> float:
        return (
            self.total_input_tokens * input_price_per_1k / 1000
            + self.total_output_tokens * output_price_per_1k / 1000
        )


class LLMProvider(ABC):
    """Protocol for LLM log-probability scoring."""

    usage: ProviderUsage

    @abstractmethod
    async def score_response(self, context: str, response: str) -> ScoringResult:
        """Score how likely `response` is given `context`.

        Returns the mean log-probability of the response tokens conditioned
        on the context.  Higher = more likely.
        """
        ...


class OpenAIProvider(LLMProvider):
    """OpenAI chat completions with logprobs on a prefilled assistant message."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
        self.usage = ProviderUsage()
        self._input_price_per_1k = 0.00015  # gpt-4o-mini
        self._output_price_per_1k = 0.0006

    async def score_response(self, context: str, response: str) -> ScoringResult:
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": context},
                        {"role": "assistant", "content": response},
                    ],
                    "logprobs": True,
                    "max_tokens": 1,
                    "temperature": 0,
                },
                timeout=30.0,
            )
            data = resp.json()

        # Extract log-probs from the response
        log_probs: list[float] = []
        choices = data.get("choices", [])
        if choices:
            logprobs_data = choices[0].get("logprobs", {})
            content_lps = logprobs_data.get("content", [])
            for token_lp in content_lps:
                log_probs.append(token_lp.get("logprob", -10.0))

        usage = data.get("usage", {})
        result = ScoringResult(
            mean_log_prob=float(np.mean(log_probs)) if log_probs else -10.0,
            tokens_scored=len(log_probs),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )
        self.usage.add(result)
        return result


class AnthropicProvider(LLMProvider):
    """Anthropic Claude — embedding-based log-prob proxy.

    The Anthropic Messages API does not expose token-level log-probabilities
    on prefilled assistant messages (unlike OpenAI's completions endpoint).
    We use embedding cosine similarity as a content-aware proxy:

    - Embed(context, response) → cosine similarity → mapped to log-prob range
    - This captures CONTENT relevance: removing an important memory changes
      the context embedding, lowering similarity to the original response
    - The API call is still made for accurate token usage / cost tracking

    For exact ContextCite attribution, use the OpenAI provider (has real logprobs).
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929"):
        self.api_key = api_key
        self.model = model
        self.usage = ProviderUsage()
        self._input_price_per_1k = 0.003
        self._output_price_per_1k = 0.015
        self._embed_fn = None

    def _get_embed(self):
        if self._embed_fn is None:
            from cortex.attribution import embed
            self._embed_fn = embed
        return self._embed_fn

    async def score_response(self, context: str, response: str) -> ScoringResult:
        # 1. Make API call for token usage tracking (non-blocking cost accounting)
        input_tok = 0
        output_tok = 0
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "max_tokens": 1,
                        "system": context,
                        "messages": [
                            {"role": "user", "content": "Score this response."},
                        ],
                    },
                    timeout=30.0,
                )
                data = resp.json()
                usage = data.get("usage", {})
                input_tok = usage.get("input_tokens", 0)
                output_tok = usage.get("output_tokens", 0)
        except Exception:
            # API call failed — fall back to token estimation
            input_tok = len(context.split()) + len(response.split())
            output_tok = 0

        # 2. Compute content-aware log-prob proxy via embedding similarity
        embed = self._get_embed()
        vectors = embed([context, response])
        ctx_vec = np.array(vectors[0])
        resp_vec = np.array(vectors[1])

        norm_ctx = np.linalg.norm(ctx_vec)
        norm_resp = np.linalg.norm(resp_vec)
        if norm_ctx == 0 or norm_resp == 0:
            cos_sim = 0.0
        else:
            cos_sim = float(np.dot(ctx_vec, resp_vec) / (norm_ctx * norm_resp))

        # Map cosine similarity [-1, 1] to log-prob range [-10, 0]
        mean_log_prob = (cos_sim + 1) / 2 * 10 - 10

        response_tokens = len(response.split())
        result = ScoringResult(
            mean_log_prob=mean_log_prob,
            tokens_scored=response_tokens,
            input_tokens=input_tok,
            output_tokens=output_tok,
        )
        self.usage.add(result)
        return result


class MockProvider(LLMProvider):
    """Cosine-similarity approximation for testing without API keys.

    Converts cosine similarity to a log-probability-like score.
    """

    def __init__(self):
        self.usage = ProviderUsage()
        self._embed_fn = None

    def _get_embed(self):
        if self._embed_fn is None:
            from cortex.attribution import embed
            self._embed_fn = embed
        return self._embed_fn

    async def score_response(self, context: str, response: str) -> ScoringResult:
        embed = self._get_embed()
        vectors = embed([context, response])
        ctx_vec = np.array(vectors[0])
        resp_vec = np.array(vectors[1])

        # Cosine similarity → log-prob approximation
        norm_ctx = np.linalg.norm(ctx_vec)
        norm_resp = np.linalg.norm(resp_vec)
        if norm_ctx == 0 or norm_resp == 0:
            cos_sim = 0.0
        else:
            cos_sim = float(np.dot(ctx_vec, resp_vec) / (norm_ctx * norm_resp))

        # Map cosine similarity [−1, 1] to log-prob range [−10, 0]
        mean_log_prob = (cos_sim + 1) / 2 * 10 - 10  # -10 to 0

        context_tokens = len(context.split())
        response_tokens = len(response.split())
        result = ScoringResult(
            mean_log_prob=mean_log_prob,
            tokens_scored=response_tokens,
            input_tokens=context_tokens + response_tokens,
            output_tokens=0,
        )
        self.usage.add(result)
        return result


def get_provider(name: str, api_key: str = "") -> LLMProvider:
    """Factory: create an LLM provider by name."""
    providers = {
        "openai": lambda: OpenAIProvider(api_key),
        "anthropic": lambda: AnthropicProvider(api_key),
        "mock": lambda: MockProvider(),
    }
    factory = providers.get(name.lower())
    if factory is None:
        raise ValueError(f"Unknown provider: {name}. Available: {list(providers.keys())}")
    return factory()
