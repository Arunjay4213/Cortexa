"""NLI classification via Groq LLM (async)."""

from __future__ import annotations

import re

import httpx

from app.config import Settings

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

_NLI_PROMPT = """Classify the relationship between the premise and hypothesis as ENTAILMENT, CONTRADICTION, or NEUTRAL.
Also rate your confidence from 0.0 to 1.0.

Premise: {premise}
Hypothesis: {hypothesis}

Reply in exactly this format, nothing else:
LABEL: <ENTAILMENT|CONTRADICTION|NEUTRAL>
CONFIDENCE: <0.0 to 1.0>"""


class NLIService:
    def __init__(self, settings: Settings | None = None) -> None:
        s = settings or Settings()
        if not s.groq_api_key:
            raise RuntimeError("CORTEX_GROQ_API_KEY is required for NLI service")
        self._api_key = s.groq_api_key
        self.model = s.nli_model

    async def predict(self, premise: str, hypothesis: str) -> dict:
        """Returns {"entailment": float, "contradiction": float, "neutral": float}."""
        prompt = _NLI_PROMPT.format(premise=premise, hypothesis=hypothesis)
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                _GROQ_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 50,
                    "temperature": 0.0,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        text = data["choices"][0]["message"]["content"].strip()

        label_match = re.search(r"LABEL:\s*(ENTAILMENT|CONTRADICTION|NEUTRAL)", text, re.IGNORECASE)
        label = label_match.group(1).upper() if label_match else "NEUTRAL"

        conf_match = re.search(r"CONFIDENCE:\s*([\d.]+)", text)
        raw_conf = float(conf_match.group(1)) if conf_match else 0.5
        conf = max(0.0, min(1.0, raw_conf))

        if label == "ENTAILMENT":
            return {
                "entailment": conf,
                "contradiction": (1.0 - conf) * 0.3,
                "neutral": (1.0 - conf) * 0.7,
            }
        elif label == "CONTRADICTION":
            return {
                "entailment": (1.0 - conf) * 0.3,
                "contradiction": conf,
                "neutral": (1.0 - conf) * 0.7,
            }
        else:
            return {
                "entailment": (1.0 - conf) * 0.4,
                "contradiction": (1.0 - conf) * 0.4,
                "neutral": conf,
            }

    async def predict_batch(self, pairs: list[tuple[str, str]]) -> list[dict]:
        results = []
        for premise, hypothesis in pairs:
            result = await self.predict(premise, hypothesis)
            results.append(result)
        return results


async def check_nli(
    claim: str,
    sources: list[str],
    nli_service: NLIService,
    threshold: float = 0.7,
) -> tuple[bool, float, str | None]:
    """
    Check if any source sentence entails the claim.

    Returns: (grounded, confidence, best_source_sentence)
    """
    best_score = 0.0
    best_sentence = None

    for source in sources:
        sentences = re.split(r"[.!?]+", source)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        for sentence in sentences:
            result = await nli_service.predict(sentence, claim)
            if result["entailment"] > best_score:
                best_score = result["entailment"]
                best_sentence = sentence

    grounded = best_score >= threshold
    return grounded, best_score, best_sentence if grounded else None
