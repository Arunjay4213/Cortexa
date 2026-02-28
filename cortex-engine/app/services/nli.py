import re

import httpx

from app.config import Settings

_settings = Settings()

# Groq API endpoint (same pattern as decomposer.py)
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_NLI_MODEL = "llama-3.1-8b-instant"

_NLI_PROMPT = """Classify the relationship between the premise and hypothesis.

Premise: {premise}
Hypothesis: {hypothesis}

Reply with exactly one word: ENTAILMENT, CONTRADICTION, or NEUTRAL"""


class NLIService:
    """
    NLI classification via Groq LLM (replaces local ONNX DeBERTa).

    Zero memory footprint — all inference happens server-side on Groq.
    """

    def __init__(self):
        if not _settings.groq_api_key:
            raise RuntimeError(
                "CORTEX_GROQ_API_KEY is required for NLI service"
            )
        self._api_key = _settings.groq_api_key

    def predict(self, premise: str, hypothesis: str) -> dict:
        """
        Returns {"entailment": float, "neutral": float, "contradiction": float}
        """
        prompt = _NLI_PROMPT.format(premise=premise, hypothesis=hypothesis)

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                _GROQ_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _NLI_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "max_tokens": 10,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        label = data["choices"][0]["message"]["content"].strip().upper()

        if "ENTAILMENT" in label:
            return {"entailment": 0.95, "contradiction": 0.02, "neutral": 0.03}
        elif "CONTRADICTION" in label:
            return {"entailment": 0.02, "contradiction": 0.95, "neutral": 0.03}
        else:
            return {"entailment": 0.15, "contradiction": 0.15, "neutral": 0.70}

    def predict_batch(self, pairs: list[tuple[str, str]]) -> list[dict]:
        """Batch predict for efficiency."""
        return [self.predict(p, h) for p, h in pairs]


def check_nli(
    claim: str,
    sources: list[str],
    nli_service: NLIService,
    threshold: float = 0.7,
) -> tuple[bool, float, str | None]:
    """
    Check if any source sentence entails the claim.

    Strategy:
      1. Split each source into sentences
      2. For each sentence, run NLI(sentence, claim)
      3. If any sentence has entailment > threshold, GROUNDED
      4. Otherwise, UNSUPPORTED

    Returns: (grounded, confidence, best_source_sentence)
    """
    best_score = 0.0
    best_sentence = None

    for source in sources:
        sentences = re.split(r"[.!?]+", source)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        for sentence in sentences:
            result = nli_service.predict(sentence, claim)

            if result["entailment"] > best_score:
                best_score = result["entailment"]
                best_sentence = sentence

    grounded = best_score >= threshold
    return grounded, best_score, best_sentence if grounded else None
