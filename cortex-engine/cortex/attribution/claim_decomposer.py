"""
Claim decomposition for CAMA — extract individual claims from an LLM response.

Uses an LLM call (via the existing provider abstraction) to decompose a
response into atomic claims, each classified as:
  - "factual":     verifiable statement of fact
  - "synthesis":   derived/inferred from multiple sources
  - "aggregation": combines or summarizes multiple data points
  - "opinion":     subjective statement

Falls back to sentence splitting if no LLM provider is available.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass
class ExtractedClaim:
    """A single claim extracted from the response."""
    claim: str
    claim_type: str  # "factual" | "synthesis" | "opinion"


DECOMPOSE_PROMPT = """You are a precise claim extractor. Decompose the response into atomic claims. Classify each as:
- "factual": a specific verifiable fact
- "synthesis": a conclusion or inference derived from combining information
- "aggregation": combines or summarizes multiple data points
- "opinion": a subjective judgment or recommendation

CRITICAL: Each claim must contain exactly ONE verifiable fact.
If a sentence contains AND, OR, or a comma joining two independent facts, split it into separate claims.
WRONG: "Slope is 2.1 deg and revenue is $1,016,400/year"
RIGHT: "Slope is 2.1 deg" AND "Revenue is $1,016,400/year"
Every number gets its own claim.

Return ONLY a JSON array: [{{"claim": "...", "claim_type": "factual|synthesis|aggregation|opinion"}}]

Response to decompose:
{response}

JSON array:"""


async def decompose_claims_llm(
    response_text: str,
    provider_name: str = "openai",
    api_key: str = "",
    model: str = "gpt-4o-mini",
    max_claims: int = 20,
) -> list[ExtractedClaim]:
    """Decompose response into claims using an LLM.

    Args:
        response_text: the LLM response to decompose
        provider_name: "openai" or "anthropic"
        api_key: API key for the provider
        model: model name to use
        max_claims: maximum claims to extract

    Returns:
        list of ExtractedClaim objects
    """
    import httpx

    prompt = DECOMPOSE_PROMPT.format(response=response_text)

    if provider_name == "openai":
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "max_tokens": 2000,
                },
                timeout=30.0,
            )
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

    elif provider_name == "anthropic":
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                },
                timeout=30.0,
            )
            data = resp.json()
            content = data["content"][0]["text"]
    else:
        # Fall back to sentence splitting for local/mock/unknown providers
        print(f"[CAMA] Claim decomposition fallback: no LLM API configured (provider={provider_name!r}), using sentence splitting", flush=True)
        return decompose_claims_fallback(response_text, max_claims=max_claims)

    return _parse_claims_json(content, max_claims=max_claims)


def _parse_claims_json(content: str, max_claims: int = 20) -> list[ExtractedClaim]:
    """Parse JSON array of claims from LLM output."""
    # Try to extract JSON array from the response
    # Sometimes LLMs wrap it in markdown code blocks
    content = content.strip()
    if content.startswith("```"):
        # Remove markdown code block
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

    try:
        claims_data = json.loads(content)
    except json.JSONDecodeError:
        # Try to find a JSON array in the content
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            try:
                claims_data = json.loads(match.group())
            except json.JSONDecodeError:
                return []
        else:
            return []

    if not isinstance(claims_data, list):
        return []

    claims: list[ExtractedClaim] = []
    valid_types = {"factual", "synthesis", "aggregation", "opinion"}

    for item in claims_data[:max_claims]:
        if not isinstance(item, dict):
            continue
        claim_text = item.get("claim", "").strip()
        claim_type = item.get("claim_type", "factual").strip().lower()
        if not claim_text:
            continue
        if claim_type not in valid_types:
            claim_type = "factual"
        claims.append(ExtractedClaim(claim=claim_text, claim_type=claim_type))

    return claims


def _strip_markdown(text: str) -> str:
    """Strip markdown/email formatting to get plain text."""
    # Remove markdown bold/italic
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    # Remove markdown headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove section separators (===FORMAL===, ---, etc.)
    text = re.sub(r"^[=\-]{3,}.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^===\w+===$", "", text, flags=re.MULTILINE)
    # Remove bullet point markers
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)
    # Remove email signature blocks (lines with just contact info)
    text = re.sub(r"^\s*\S+@\S+\.\S+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\(\d{3}\)\s*\d{3}[-.]\d{4}\s*$", "", text, flags=re.MULTILINE)
    # Collapse multiple newlines into single newline
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


# Patterns to filter out non-claim sentences
_GREETING_RE = re.compile(
    r"^(dear\s|hi\s|hello\s|i hope this|i.m reaching|my name is|"
    r"thank you|thanks for|best regards|sincerely|best,|regards,|"
    r"looking forward|would you be available|does sometime|"
    r"i.d love to|can we schedule|no obligations|are you available|"
    r"give me a ring|please contact|contact me)",
    re.IGNORECASE,
)

_SIGNOFF_RE = re.compile(
    r"(energy development|projects@|solarisq|\.energy\s*$|"
    r"^\s*\d{3}[-.]\d{3}[-.]\d{4}|^\s*$)",
    re.IGNORECASE,
)


def _is_claim_worthy(text: str) -> bool:
    """Check if a sentence is worth treating as a claim."""
    words = text.split()
    if len(words) < 4 or len(words) > 50:
        return False
    if _GREETING_RE.search(text):
        return False
    if _SIGNOFF_RE.search(text):
        return False
    # Must contain at least one noun-like word or number
    if not re.search(r"[\d$%]|acres|MW|kWh|MWh|county|property|solar|lease|revenue|irr|lcoe|substation|irradiance|score", text, re.IGNORECASE):
        return False
    return True


def _classify_claim(text: str) -> str:
    """Heuristic claim type classification."""
    lower = text.lower()

    # Subject lines are metadata, not claims
    if lower.startswith("subject:"):
        return "opinion"

    # Opinion: recommendations, subjective/marketing language
    _opinion_markers = (
        "should", "recommend", "ideal", "well-suited", "exceptional",
        "stands out", "appreciate", "minimal impact", "huge advantage",
        "excellent", "stable", "long-term income", "steady income",
        "non-intrusive", "no obligations", "your call", "we'd love",
        "we would love", "finest", "perfect fit", "best regards",
        "we believe", "we're confident", "excited", "great opportunity",
        "huge opportunity", "maintains your", "maintaining your",
        "that's a huge", "doing what it does best",
        "our ability to", "reliably over", "dramatically",
        "predictable income", "best decision", "game-changer",
        "make sure you have all", "changed dramatically",
    )
    if any(w in lower for w in _opinion_markers):
        return "opinion"

    # Marketing/pitch sentences with no verifiable number
    if not re.search(r"[\d$%]", text):
        _pitch_markers = (
            "partnership", "long-term", "minimal", "benefit",
            "advantage", "opportunity", "developing", "suitable",
            "identified", "proposing", "project", "dramatically",
            "predictable", "decision", "information", "personally",
            "game-changer", "changed", "all the information",
            "reach out", "make sure",
        )
        if any(w in lower for w in _pitch_markers):
            return "opinion"

    # Synthesis: derived conclusions
    if any(w in lower for w in ("therefore", "this means", "as a result", "combined", "overall")):
        return "synthesis"
    # Aggregation: summaries
    if any(w in lower for w in ("total", "across", "average", "combined")):
        return "aggregation"
    return "factual"


def decompose_claims_fallback(
    response_text: str,
    max_claims: int = 20,
) -> list[ExtractedClaim]:
    """Fallback: split response into atomic sentence-level claims.

    Used when no LLM provider is configured (e.g., testing with mock provider).
    Handles markdown/email formatting by stripping it before splitting.
    Filters out greetings, sign-offs, and non-verifiable filler.
    """
    print("[CAMA] FALLBACK: regex splitting used (no LLM API configured)", flush=True)

    # Strip markdown/email formatting first
    clean = _strip_markdown(response_text)

    # Split into sentences: handle period, exclamation, question mark, and newlines
    raw_sentences: list[str] = []
    for paragraph in clean.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        # Split paragraph into sentences
        parts = re.split(r"(?<=[.!?])\s+", paragraph)
        raw_sentences.extend(parts)

    # Deduplicate (emails often repeat the same facts across variants)
    seen: set[str] = set()
    claims: list[ExtractedClaim] = []

    for sent in raw_sentences:
        sent = sent.strip().rstrip(".")
        if not sent:
            continue

        # Further split compound sentences on " and " / " — " when both halves
        # contain numbers or verifiable facts
        sub_parts = re.split(r"\s+(?:and|—|–)\s+", sent)
        if len(sub_parts) == 1:
            sub_parts = [sent]

        for part in sub_parts:
            part = part.strip()
            if not _is_claim_worthy(part):
                continue

            # Normalize for dedup
            norm = re.sub(r"\s+", " ", part.lower().strip())
            if norm in seen:
                continue
            seen.add(norm)

            ctype = _classify_claim(part)
            claims.append(ExtractedClaim(claim=part, claim_type=ctype))

            if len(claims) >= max_claims:
                break
        if len(claims) >= max_claims:
            break

    # Log extracted claims
    for i, c in enumerate(claims):
        print(f"[CAMA] Claim {i}: [{c.claim_type}] {c.claim[:80]}", flush=True)

    print(f"[CAMA] Fallback decomposition: {len(claims)} claims extracted", flush=True)
    return claims
