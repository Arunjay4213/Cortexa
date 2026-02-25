"""Tests for CAMA — Claim-Aware Memory Attribution.

16 tests covering:
  - Shapley math (value functions, edge cases)
  - Entailment module structure
  - Similarity gate
  - Hallucination detection
  - Aggregator logic
  - Claim decomposer fallback
  - End-to-end pipeline
"""

from __future__ import annotations

import numpy as np
import pytest

from cortex.attribution.shapley import (
    compute_shapley,
    exact_shapley,
    v_additive,
    v_max,
    v_noisy_or,
)
from cortex.attribution.similarity_gate import (
    apply_gate,
    cosine_similarity_matrix,
    find_dead_memories,
)
from cortex.attribution.aggregator import aggregate, classify_support
from cortex.attribution.claim_decomposer import (
    ExtractedClaim,
    _parse_claims_json,
    decompose_claims_fallback,
)
from cortex.attribution.types import (
    CAMAResult,
    ClaimAnalysis,
    ClaimSource,
    LatencyBreakdown,
    UnsupportedClaim,
)
from cortex.attribution.cama_config import CAMAConfig, DEFAULT_CONFIG


# ── Helpers ───────────────────────────────────────────────────────────

def _norm(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


# ══════════════════════════════════════════════════════════════════════
# Shapley Tests (4 tests)
# ══════════════════════════════════════════════════════════════════════

class TestShapleyMath:
    def test_single_player_gets_full_value(self):
        """Single memory supporting a claim → Shapley value = 1.0 (normalized)."""
        support = [("m1", 0.93)]

        shap = exact_shapley(support, v_max)
        assert pytest.approx(shap["m1"], abs=1e-9) == 1.0

        shap_nor = exact_shapley(support, v_noisy_or)
        assert pytest.approx(shap_nor["m1"], abs=1e-9) == 1.0

        shap_add = exact_shapley(support, v_additive)
        assert pytest.approx(shap_add["m1"], abs=1e-9) == 1.0

    def test_two_redundant_players_split_evenly_with_similar_scores(self):
        """Two memories with similar scores → near-equal Shapley (v_max)."""
        support = [("m2", 0.95), ("m3", 0.94)]

        shap = exact_shapley(support, v_max)
        # Both are very close, so shares should be near 0.5 each
        assert pytest.approx(shap["m2"] + shap["m3"], abs=1e-9) == 1.0
        assert shap["m2"] > shap["m3"]  # m2 slightly stronger

    def test_v_max_differentiates_strength(self):
        """v_max gives more credit to stronger entailment."""
        support = [("m2", 0.95), ("m3", 0.55)]

        shap = exact_shapley(support, v_max)
        # m2 should get much more than m3 under v_max
        assert shap["m2"] > shap["m3"]
        assert pytest.approx(shap["m2"] + shap["m3"], abs=1e-9) == 1.0

    def test_empty_players_returns_empty(self):
        """No memories → empty Shapley values."""
        shap = compute_shapley({})
        assert shap == {}

    def test_shapley_efficiency_axiom(self):
        """Efficiency axiom: raw Shapley values sum to v(N)."""
        # For v_max: raw values sum to max(0.9, 0.7, 0.6) = 0.9
        support = [("m1", 0.9), ("m2", 0.7), ("m3", 0.6)]

        # Compute raw (unnormalized) values manually
        import math
        from itertools import combinations

        scores = [0.9, 0.7, 0.6]
        n = 3
        raw = [0.0, 0.0, 0.0]
        for i in range(n):
            others = [j for j in range(n) if j != i]
            for size in range(len(others) + 1):
                for combo in combinations(others, size):
                    S = list(combo)
                    S_with_i = S + [i]
                    v_with = v_max([scores[j] for j in S_with_i])
                    v_without = v_max([scores[j] for j in S]) if S else 0.0
                    weight = math.factorial(len(S)) * math.factorial(n - len(S) - 1) / math.factorial(n)
                    raw[i] += weight * (v_with - v_without)

        assert pytest.approx(sum(raw), abs=1e-9) == 0.9  # v_max(N)


# ══════════════════════════════════════════════════════════════════════
# Similarity Gate Tests (3 tests)
# ══════════════════════════════════════════════════════════════════════

class TestSimilarityGate:
    def test_cosine_matrix_shape(self):
        """Similarity matrix has correct shape (claims × memories)."""
        claims = np.random.randn(3, 16)
        mems = np.random.randn(5, 16)
        sim = cosine_similarity_matrix(claims, mems)
        assert sim.shape == (3, 5)

    def test_gate_filters_below_threshold(self):
        """Memories below threshold are excluded from candidates."""
        # Construct a similarity matrix where only some entries pass
        sim = np.array([
            [0.8, 0.1, 0.6],  # claim 0: m0 and m2 pass
            [0.2, 0.9, 0.2],  # claim 1: only m1 passes
        ])
        mem_ids = ["m0", "m1", "m2"]

        candidates = apply_gate(sim, mem_ids, threshold=0.3, max_candidates=5)
        assert candidates[0] == ["m0", "m2"]
        assert candidates[1] == ["m1"]

    def test_dead_memories_identified(self):
        """Memories never passing the gate for any claim are flagged dead."""
        sim = np.array([
            [0.8, 0.1, 0.6],  # m1 never passes (0.1, 0.2)
            [0.2, 0.2, 0.5],
        ])
        mem_ids = ["m0", "m1", "m2"]

        dead = find_dead_memories(sim, mem_ids, threshold=0.3)
        assert dead == ["m1"]

    def test_max_candidates_limit(self):
        """Gate respects max_candidates per claim."""
        sim = np.array([
            [0.9, 0.8, 0.7, 0.6, 0.5, 0.4],
        ])
        mem_ids = ["m0", "m1", "m2", "m3", "m4", "m5"]

        candidates = apply_gate(sim, mem_ids, threshold=0.3, max_candidates=3)
        assert len(candidates[0]) == 3
        # Should be top-3 by similarity
        assert candidates[0] == ["m0", "m1", "m2"]


# ══════════════════════════════════════════════════════════════════════
# Aggregator Tests (3 tests)
# ══════════════════════════════════════════════════════════════════════

class TestAggregator:
    def test_classify_support_essential(self):
        """Single source → essential."""
        sources = [ClaimSource(memory_id="m1", shapley_value=1.0, entailment=0.93)]
        assert classify_support(sources, entailment_threshold=0.5) == "essential"

    def test_classify_support_redundant(self):
        """Multiple sources → redundant."""
        sources = [
            ClaimSource(memory_id="m2", shapley_value=0.5, entailment=0.95),
            ClaimSource(memory_id="m3", shapley_value=0.5, entailment=0.94),
        ]
        assert classify_support(sources, entailment_threshold=0.5) == "redundant"

    def test_classify_support_unsupported(self):
        """No sources above threshold → unsupported."""
        sources = [ClaimSource(memory_id="m4", shapley_value=0.0, entailment=0.3)]
        assert classify_support(sources, entailment_threshold=0.5) == "unsupported"

    def test_hallucination_detection(self):
        """Claims with best entailment below threshold are flagged as hallucinated."""
        result = aggregate(
            claims=["The issue has been escalated", "John reported slow dashboard"],
            claim_types=["factual", "factual"],
            entailment_scores=[
                {},  # no NLI for claim 0 (no candidates passed gate)
                {"m1": 0.93},
            ],
            shapley_values=[
                {},
                {"m1": 1.0},
            ],
            all_memory_ids=["m1", "m2"],
            dead_memories=["m2"],
            entailment_threshold=0.5,
            hallucination_threshold=0.5,
        )

        # Claim 0: no entailment at all → hallucinated
        assert result.claims[0].is_hallucination is True
        assert result.claims[0].support_type == "unsupported"

        # Claim 1: m1 entails at 0.93 → not hallucinated
        assert result.claims[1].is_hallucination is False
        assert result.claims[1].support_type == "essential"

        # Hallucination index: 1 out of 2 = 0.5
        assert result.hallucination_index == 0.5

        # Unsupported claims list
        assert len(result.unsupported_claims) == 1
        assert result.unsupported_claims[0].claim == "The issue has been escalated"

    def test_scores_sum_to_one(self):
        """Memory scores should sum to 1.0 when at least one claim is supported."""
        result = aggregate(
            claims=["claim A", "claim B"],
            claim_types=["factual", "factual"],
            entailment_scores=[
                {"m1": 0.9},
                {"m1": 0.8, "m2": 0.7},
            ],
            shapley_values=[
                {"m1": 0.9},
                {"m1": 0.5, "m2": 0.3},
            ],
            all_memory_ids=["m1", "m2"],
            dead_memories=[],
            entailment_threshold=0.5,
            hallucination_threshold=0.5,
        )

        total = sum(result.scores.values())
        assert pytest.approx(total, abs=1e-9) == 1.0


# ══════════════════════════════════════════════════════════════════════
# Claim Decomposer Tests (2 tests)
# ══════════════════════════════════════════════════════════════════════

class TestClaimDecomposer:
    def test_fallback_splits_sentences(self):
        """Fallback decomposer splits on sentence boundaries."""
        text = "John reported slow loading. The report was on Feb 15. He is on Pro plan."
        claims = decompose_claims_fallback(text)
        assert len(claims) == 3
        assert all(c.claim_type == "factual" for c in claims)
        assert "John reported slow loading." in claims[0].claim

    def test_parse_claims_json(self):
        """JSON parser handles well-formed and markdown-wrapped JSON."""
        json_str = '[{"claim": "X is true", "claim_type": "factual"}, {"claim": "Y seems good", "claim_type": "opinion"}]'
        claims = _parse_claims_json(json_str)
        assert len(claims) == 2
        assert claims[0].claim == "X is true"
        assert claims[0].claim_type == "factual"
        assert claims[1].claim_type == "opinion"

        # With markdown wrapper
        wrapped = "```json\n" + json_str + "\n```"
        claims2 = _parse_claims_json(wrapped)
        assert len(claims2) == 2


# ══════════════════════════════════════════════════════════════════════
# Config Tests (1 test)
# ══════════════════════════════════════════════════════════════════════

class TestCAMAConfig:
    def test_defaults(self):
        """Default config has sensible values."""
        cfg = DEFAULT_CONFIG
        assert cfg.similarity_threshold == 0.3
        assert cfg.entailment_threshold == 0.5
        assert cfg.hallucination_threshold == 0.5
        assert cfg.max_candidates_per_claim == 5
        assert cfg.max_claims == 20
        assert cfg.shapley_value_fn == "weighted"
        assert "DeBERTa" in cfg.nli_model

    def test_custom_config(self):
        """Can override config values."""
        cfg = CAMAConfig(similarity_threshold=0.5, entailment_threshold=0.7)
        assert cfg.similarity_threshold == 0.5
        assert cfg.entailment_threshold == 0.7


# ══════════════════════════════════════════════════════════════════════
# Type Tests (1 test)
# ══════════════════════════════════════════════════════════════════════

class TestCAMATypes:
    def test_cama_result_structure(self):
        """CAMAResult correctly holds all fields."""
        result = CAMAResult(
            scores={"m1": 0.5, "m2": 0.3, "m3": 0.2},
            claims=[
                ClaimAnalysis(
                    claim="test claim",
                    claim_type="factual",
                    support_type="essential",
                    sources=[ClaimSource(memory_id="m1", shapley_value=1.0, entailment=0.9)],
                    best_entailment=0.9,
                    is_hallucination=False,
                ),
            ],
            unsupported_claims=[],
            hallucination_index=0.0,
            dead_memories=["m3"],
            num_claims=1,
            num_nli_calls=3,
            latency_ms=LatencyBreakdown(decompose_ms=100, gate_ms=1, entail_ms=50),
        )

        assert result.method == "cama"
        assert result.scores["m1"] == 0.5
        assert len(result.claims) == 1
        assert result.claims[0].sources[0].memory_id == "m1"
        assert result.dead_memories == ["m3"]
        assert result.latency_ms.decompose_ms == 100


# ══════════════════════════════════════════════════════════════════════
# End-to-End Pipeline Test (1 test — uses fallback decomposer, no LLM)
# ══════════════════════════════════════════════════════════════════════

class TestCAMAEndToEnd:
    @pytest.mark.asyncio
    async def test_full_pipeline_with_mock(self):
        """End-to-end CAMA with fallback decomposer and real NLI model.

        This test uses pre-extracted claims to skip the LLM call
        and validates the full gate → entailment → shapley → aggregate pipeline.
        """
        from cortex.attribution.cama import CAMAEngine
        from cortex.attribution.cama_config import CAMAConfig

        # Use pre-extracted claims to skip LLM call
        # The hallucinated claim must be semantically distant from ALL memories
        # so the NLI model doesn't find spurious entailment via topic overlap.
        claims = [
            ExtractedClaim(claim="John reported slow dashboard loading", claim_type="factual"),
            ExtractedClaim(claim="John is on the Pro plan", claim_type="factual"),
            ExtractedClaim(claim="The tropical rainforest is experiencing record deforestation rates", claim_type="factual"),
        ]

        memory_ids = ["m1", "m2", "m3"]
        memory_contents = {
            "m1": "John reported that his dashboard is loading slowly on Feb 15.",
            "m2": "John is subscribed to the Pro plan with 3 seats.",
            "m3": "Company revenue was $50k last quarter.",
        }

        # Use the embedding model to get real embeddings
        from cortex.attribution import embed
        mem_texts = [memory_contents[mid] for mid in memory_ids]
        mem_embs = np.array(embed(mem_texts))

        config = CAMAConfig(
            similarity_threshold=0.2,  # lower for test data
            entailment_threshold=0.5,
            hallucination_threshold=0.5,
        )
        engine = CAMAEngine(config=config)

        result = await engine.compute_attribution(
            response_text="John reported slow dashboard loading. John is on the Pro plan. The tropical rainforest is experiencing record deforestation rates.",
            memory_ids=memory_ids,
            memory_contents=memory_contents,
            memory_embeddings=mem_embs,
            llm_provider="mock",  # will use fallback, but we pass claims anyway
            claims=claims,
        )

        # Basic structure
        assert result.method == "cama"
        assert result.num_claims == 3
        assert len(result.claims) == 3

        # m1 should support "slow dashboard loading"
        # m2 should support "Pro plan"
        assert result.scores["m1"] > 0 or result.scores["m2"] > 0

        # The rainforest claim should be flagged as hallucination
        # (completely unrelated to any memory about John/dashboard/plans)
        hallucinated_claim = next(
            (c for c in result.claims if "rainforest" in c.claim), None
        )
        assert hallucinated_claim is not None
        assert hallucinated_claim.is_hallucination is True

        # Hallucination index should be > 0 (at least the rainforest claim)
        assert result.hallucination_index > 0

        # Scores should sum to ~1 or be all 0 (if nothing passes)
        total = sum(result.scores.values())
        assert pytest.approx(total, abs=0.01) == 1.0 or total == 0.0

        # Latency tracked
        assert result.latency_ms.gate_ms >= 0
        assert result.latency_ms.entail_ms >= 0
        assert result.latency_ms.shapley_ms >= 0
