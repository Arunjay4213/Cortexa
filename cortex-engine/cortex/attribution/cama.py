"""
CAMA — Claim-Aware Memory Attribution.

Orchestrator that wires all stages:
  1. Claim decomposition (LLM call)
  2. Similarity gate (cosine pre-filter)
  3. NLI entailment (DeBERTa-v3 batch inference)
  4. Mini-Shapley computation (per-claim, over support sets)
  5. Aggregation (claim→memory scores, hallucination detection)

Total latency budget: ~700ms (dominated by claim decomposition LLM call).
"""

from __future__ import annotations

import time

import numpy as np

from cortex.attribution.aggregator import aggregate
from cortex.attribution.cama_config import CAMAConfig, DEFAULT_CONFIG
from cortex.attribution.claim_decomposer import (
    ExtractedClaim,
    decompose_claims_fallback,
    decompose_claims_llm,
)
import os
from cortex.attribution.shapley import compute_shapley
from cortex.attribution.similarity_gate import (
    apply_gate,
    cosine_similarity_matrix,
    find_dead_memories,
)
from cortex.attribution.types import CAMAResult, LatencyBreakdown


class CAMAEngine:
    """Claim-Aware Memory Attribution engine.

    Usage::

        engine = CAMAEngine(config=CAMAConfig(...))
        result = await engine.compute_attribution(
            response_text="John reported slow dashboard loading on Feb 15...",
            memory_ids=["m1", "m2", "m3"],
            memory_contents={"m1": "...", "m2": "...", "m3": "..."},
            memory_embeddings=np.array([[...], [...]]),
            llm_provider="openai",
            llm_api_key="sk-...",
        )
    """

    def __init__(self, config: CAMAConfig | None = None):
        self.config = config or DEFAULT_CONFIG

    async def compute_attribution(
        self,
        response_text: str,
        memory_ids: list[str],
        memory_contents: dict[str, str],
        memory_embeddings: np.ndarray,
        llm_provider: str = "mock",
        llm_api_key: str = "",
        llm_model: str = "gpt-4o-mini",
        claims: list[ExtractedClaim] | None = None,
    ) -> CAMAResult:
        """Run the full CAMA pipeline.

        Args:
            response_text: the LLM response to attribute
            memory_ids: list of retrieved memory IDs
            memory_contents: memory_id → content text
            memory_embeddings: (k, d) array of memory embeddings
            llm_provider: "openai", "anthropic", or "mock"
            llm_api_key: API key for claim decomposition
            llm_model: model for claim decomposition
            claims: pre-extracted claims (skips decomposition if provided)

        Returns:
            CAMAResult with scores, claims, hallucination index, etc.
        """
        latency = LatencyBreakdown()

        # ── Stage 1: Claim decomposition ──────────────────────────────
        t0 = time.perf_counter()

        if claims is not None:
            extracted_claims = claims
            print(f"[CAMA] Using pre-extracted claims: {len(extracted_claims)}", flush=True)
        elif llm_provider in ("openai", "anthropic") and llm_api_key:
            print(f"[CAMA] LLM decomposition: provider={llm_provider}, model={llm_model}", flush=True)
            try:
                extracted_claims = await decompose_claims_llm(
                    response_text=response_text,
                    provider_name=llm_provider,
                    api_key=llm_api_key,
                    model=llm_model,
                    max_claims=self.config.max_claims,
                )
                print(f"[CAMA] LLM decomposition: {len(extracted_claims)} claims extracted", flush=True)
            except Exception as e:
                print(f"[CAMA] LLM decomposition FAILED: {e}, falling back to regex", flush=True)
                extracted_claims = decompose_claims_fallback(
                    response_text=response_text,
                    max_claims=self.config.max_claims,
                )
        else:
            print(f"[CAMA] No LLM configured (provider={llm_provider!r}), using fallback", flush=True)
            extracted_claims = decompose_claims_fallback(
                response_text=response_text,
                max_claims=self.config.max_claims,
            )

        if not extracted_claims:
            # No claims extracted — return empty result
            return CAMAResult(
                scores={mid: 0.0 for mid in memory_ids},
                claims=[],
                unsupported_claims=[],
                hallucination_index=0.0,
                dead_memories=list(memory_ids),
                num_claims=0,
                num_nli_calls=0,
                latency_ms=latency,
            )

        latency.decompose_ms = (time.perf_counter() - t0) * 1000

        claim_texts = [c.claim for c in extracted_claims]
        claim_types = [c.claim_type for c in extracted_claims]

        # ── Stage 1.5: Deterministic numerical gate ──────────────────
        from cortex.attribution.numerical_gate import apply_numerical_gate

        num_skip_indices, num_gate_details = apply_numerical_gate(
            claim_texts, claim_types, memory_contents,
        )
        # Build hallucination_reasons dict for claims flagged by numerical gate
        hallucination_reasons: dict[int, str] = {
            i: "numerical_ungrounded" for i in num_skip_indices
        }

        # Log numerical gate results
        if num_skip_indices:
            for idx in num_skip_indices:
                nums = num_gate_details.get(idx, [])
                print(f"[CAMA] Numerical gate: claim {idx} flagged — ungrounded numbers: {nums}", flush=True)
            print(f"[CAMA] Numerical gate: {len(num_skip_indices)}/{len(claim_texts)} claims flagged", flush=True)
        else:
            print(f"[CAMA] Numerical gate: 0/{len(claim_texts)} claims flagged (all numbers grounded or no numbers)", flush=True)

        # ── Stage 2: Similarity gate ──────────────────────────────────
        t0 = time.perf_counter()

        # Embed claims using the same embedding model as memories
        from cortex.attribution import embed
        claim_embs = np.array(embed(claim_texts))

        M = np.asarray(memory_embeddings, dtype=np.float64)
        if M.ndim == 1:
            M = M.reshape(1, -1)

        sim_matrix = cosine_similarity_matrix(claim_embs, M)

        candidates = apply_gate(
            sim_matrix,
            memory_ids,
            threshold=self.config.similarity_threshold,
            max_candidates=self.config.max_candidates_per_claim,
        )

        dead = find_dead_memories(
            sim_matrix,
            memory_ids,
            threshold=self.config.similarity_threshold,
        )

        latency.gate_ms = (time.perf_counter() - t0) * 1000

        # ── Stage 3: NLI entailment ──────────────────────────────────
        t0 = time.perf_counter()

        # Filter out numerically-flagged claims from NLI (save compute)
        nli_claim_texts = []
        nli_candidates = []
        nli_original_indices = []
        for i in range(len(claim_texts)):
            if i not in num_skip_indices:
                nli_claim_texts.append(claim_texts[i])
                nli_candidates.append(candidates[i])
                nli_original_indices.append(i)

        if nli_claim_texts:
            _use_local = os.environ.get("USE_LOCAL_MODELS", "false").lower() == "true"
            if _use_local:
                from cortex.attribution.entailment import score_claim_memory_pairs
                nli_ent_scores, num_nli_calls = score_claim_memory_pairs(
                    claims=nli_claim_texts,
                    candidate_memories=nli_candidates,
                    memory_contents=memory_contents,
                    model_name=self.config.nli_model,
                )
            else:
                from cortex.attribution.nli_groq import score_claim_memory_pairs_groq
                from cortex.config import settings
                nli_ent_scores, num_nli_calls = score_claim_memory_pairs_groq(
                    claims=nli_claim_texts,
                    candidate_memories=nli_candidates,
                    memory_contents=memory_contents,
                    api_key=settings.groq_api_key,
                )
        else:
            nli_ent_scores = []
            num_nli_calls = 0

        # Rebuild full entailment_scores list (empty dict for skipped claims)
        entailment_scores: list[dict[str, float]] = [{} for _ in range(len(claim_texts))]
        for j, orig_i in enumerate(nli_original_indices):
            entailment_scores[orig_i] = nli_ent_scores[j]

        latency.entail_ms = (time.perf_counter() - t0) * 1000

        # ── Stage 3.5: Numerical grounding boost ────────────────────
        # If a claim has all numbers grounded (passed numerical gate)
        # but NLI scored it below threshold (due to paraphrasing),
        # boost the best-matching memory's entailment to rescue it.
        from cortex.attribution.numerical_gate import (
            find_grounded_claims_with_numbers,
            find_best_memory_for_claim,
        )

        num_grounded_claims = find_grounded_claims_with_numbers(
            claim_texts, claim_types, num_skip_indices,
        )
        boost_count = 0
        for i in num_grounded_claims:
            ent = entailment_scores[i]
            best_ent = max(ent.values()) if ent else 0.0
            if best_ent < self.config.entailment_threshold:
                # NLI failed but numbers are grounded — find the best memory
                best_mem = find_best_memory_for_claim(
                    claim_texts[i], memory_contents,
                )
                if best_mem:
                    entailment_scores[i][best_mem] = 0.8
                    boost_count += 1
                    print(
                        f"[CAMA] NumBoost claim {i}: NLI={best_ent:.3f} "
                        f"but numbers grounded → boosted {best_mem[:12]} to 0.8",
                        flush=True,
                    )

        if boost_count:
            print(f"[CAMA] Numerical grounding boost: {boost_count} claims rescued", flush=True)

        # ── Stage 4: Mini-Shapley per claim ───────────────────────────
        t0 = time.perf_counter()

        shapley_values: list[dict[str, float]] = []
        for i in range(len(claim_texts)):
            # Skip Shapley for numerically-flagged claims
            if i in num_skip_indices:
                shapley_values.append({})
                continue

            ent = entailment_scores[i]
            ctype = claim_types[i] if i < len(claim_types) else "factual"
            # Filter to only memories above entailment threshold
            supported = {
                mid: score
                for mid, score in ent.items()
                if score >= self.config.entailment_threshold
            }
            if supported:
                shap = compute_shapley(
                    supported,
                    value_fn=self.config.shapley_value_fn,
                    threshold=self.config.entailment_threshold,
                    claim_type=ctype,
                )
            else:
                shap = {}
            shapley_values.append(shap)

        latency.shapley_ms = (time.perf_counter() - t0) * 1000

        # ── Stage 5: Aggregation ──────────────────────────────────────
        t0 = time.perf_counter()

        result = aggregate(
            claims=claim_texts,
            claim_types=claim_types,
            entailment_scores=entailment_scores,
            shapley_values=shapley_values,
            all_memory_ids=memory_ids,
            dead_memories=dead,
            entailment_threshold=self.config.entailment_threshold,
            hallucination_threshold=self.config.hallucination_threshold,
            latency=latency,
            num_nli_calls=num_nli_calls,
            hallucination_reasons=hallucination_reasons,
        )

        latency.aggregate_ms = (time.perf_counter() - t0) * 1000

        return result
