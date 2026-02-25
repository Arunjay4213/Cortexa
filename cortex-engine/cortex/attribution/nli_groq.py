"""
Groq-based NLI entailment scoring for CAMA.

Replaces local DeBERTa model with Groq API calls.
Used when USE_LOCAL_MODELS=false (default for Railway deployment).
"""

from __future__ import annotations

import json
import logging
import re

import httpx

log = logging.getLogger("cortex")

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_DEFAULT_MODEL = "qwen-qwq-32b"


def _parse_response(text: str) -> dict:
    """Parse JSON from Groq response, handling <think> blocks."""
    # Strip <think>...</think> blocks (qwen models)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # Try to find JSON object in the response
    match = re.search(r"\{[^{}]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {"supported": False, "confidence": 0.0, "reason": "parse_error"}


def check_entailment_groq(
    claim: str,
    memory: str,
    api_key: str,
    model: str = _DEFAULT_MODEL,
) -> float:
    """Return entailment score 0.0-1.0 using Groq LLM.

    Args:
        claim: the claim to verify
        memory: the context/memory to check against
        api_key: Groq API key
        model: Groq model to use

    Returns:
        Float score 0.0-1.0
    """
    prompt = (
        "You are a strict factual verification system.\n\n"
        "Does the CONTEXT logically support the CLAIM?\n"
        "Be very strict. The context must DIRECTLY state or clearly imply the claim.\n\n"
        f"CONTEXT: {memory}\n"
        f"CLAIM: {claim}\n\n"
        'Respond with ONLY a JSON object:\n'
        '{"supported": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}'
    )

    try:
        resp = httpx.post(
            _GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 150,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        parsed = _parse_response(content)
        if parsed.get("supported"):
            return float(parsed.get("confidence", 0.7))
        return 0.0
    except Exception as e:
        log.warning(f"Groq NLI call failed: {e}")
        return 0.0


def batch_entailment_groq(
    premises: list[str],
    hypotheses: list[str],
    api_key: str,
    model: str = _DEFAULT_MODEL,
) -> list[float]:
    """Check multiple (premise, hypothesis) pairs.

    Calls Groq sequentially for each pair.
    Compatible with the same interface as entailment.batch_entailment.
    """
    if not premises:
        return []

    assert len(premises) == len(hypotheses)

    scores = []
    for premise, hypothesis in zip(premises, hypotheses):
        score = check_entailment_groq(hypothesis, premise, api_key, model)
        scores.append(score)

    return scores


def score_claim_memory_pairs_groq(
    claims: list[str],
    candidate_memories: list[list[str]],
    memory_contents: dict[str, str],
    api_key: str,
    model: str = _DEFAULT_MODEL,
) -> tuple[list[dict[str, float]], int]:
    """Score all (claim, memory) pairs using Groq API.

    Drop-in replacement for entailment.score_claim_memory_pairs.
    """
    all_premises: list[str] = []
    all_hypotheses: list[str] = []
    pair_map: list[tuple[int, str]] = []

    for claim_idx, mem_ids in enumerate(candidate_memories):
        for mem_id in mem_ids:
            content = memory_contents.get(mem_id, "")
            if content:
                all_premises.append(content)
                all_hypotheses.append(claims[claim_idx])
                pair_map.append((claim_idx, mem_id))

    num_nli_calls = len(all_premises)

    if num_nli_calls == 0:
        return [{} for _ in claims], 0

    scores = batch_entailment_groq(all_premises, all_hypotheses, api_key, model)

    results: list[dict[str, float]] = [{} for _ in claims]
    for idx, (claim_idx, mem_id) in enumerate(pair_map):
        results[claim_idx][mem_id] = scores[idx]

    return results, num_nli_calls
