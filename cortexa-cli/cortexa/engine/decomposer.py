"""Claim decomposition — Tier 1 of the CAMA pipeline.

Two modes:
1. Fast mode (default): Rule-based sentence splitting + regex classification.
2. LLM mode: Claude Haiku for atomic claim decomposition.
"""

import logging
import re

from cortexa.engine.models import Claim

logger = logging.getLogger(__name__)

# Patterns for claim classification
_NUMBER_RE = re.compile(
    r"""
    \$[\d,]+\.?\d*       |   # currency: $49.99
    \d+\.?\d*\s*%        |   # percentage: 23%
    \d{1,2}:\d{2}\s*[ap]m|   # time: 2pm, 2:30pm
    \d+\.?\d*\s*(?:days?|hours?|minutes?|weeks?|months?|years?) |  # durations
    \d[\d,]*\.?\d*            # plain numbers: 1000, 3.14
    """,
    re.VERBOSE | re.IGNORECASE,
)

_TEMPORAL_RE = re.compile(
    r"""
    \b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b |
    \b(?:january|february|march|april|may|june|july|august|
         september|october|november|december)\b |
    \b(?:today|tomorrow|yesterday|next\s+week|last\s+week|
         this\s+month|next\s+month)\b |
    \b\d{1,2}/\d{1,2}/\d{2,4}\b |
    \b\d{4}-\d{2}-\d{2}\b |
    \bQ[1-4]\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

_RELATIONAL_RE = re.compile(
    r"""
    \b(?:more\s+than|less\s+than|greater\s+than|fewer\s+than|
         higher\s+than|lower\s+than|better\s+than|worse\s+than|
         beating|exceeded|surpassed|compared\s+to|versus|vs\.?)\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

_OPINION_RE = re.compile(
    r"""
    \b(?:I\s+think|I\s+believe|in\s+my\s+opinion|probably|
         seems?\s+like|might\s+be|could\s+be|possibly|
         I\s+feel|arguably|likely|unlikely)\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Sentence boundary detection — lightweight, no spaCy
_SENT_BOUNDARY_RE = re.compile(
    r"""
    (?<=[.!?])       # after sentence-ending punctuation
    \s+              # followed by whitespace
    (?=[A-Z"])        # followed by uppercase letter or quote
    """,
    re.VERBOSE,
)

# Split on conjunctions that introduce separate claims
_CONJUNCTION_SPLIT_RE = re.compile(
    r"""
    ,\s*(?:and|but|while|whereas|although)\s+  |  # comma + conjunction
    ;\s+                                        |  # semicolon
    \s+—\s+                                        # em dash
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Split compound claims with "with" introducing a separate fact
_WITH_SPLIT_RE = re.compile(
    r",?\s+with\s+", re.IGNORECASE
)


def _classify_claim(text: str) -> str:
    """Classify a claim by type based on regex patterns."""
    if _OPINION_RE.search(text):
        return "opinion"
    if _NUMBER_RE.search(text):
        if _TEMPORAL_RE.search(text):
            return "temporal"
        return "numerical"
    if _TEMPORAL_RE.search(text):
        return "temporal"
    if _RELATIONAL_RE.search(text):
        return "relational"
    return "factual"


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using lightweight boundary detection."""
    # First split on obvious boundaries
    sentences = _SENT_BOUNDARY_RE.split(text)
    result = []
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        # Further split on conjunctions that introduce independent claims
        parts = _CONJUNCTION_SPLIT_RE.split(sent)
        for part in parts:
            part = part.strip().strip(",").strip()
            if len(part) > 5:  # skip trivially short fragments
                result.append(part)
    return result


def _split_with_clauses(claims: list[str]) -> list[str]:
    """Split claims containing 'with' that introduces a separate fact."""
    result = []
    for claim in claims:
        parts = _WITH_SPLIT_RE.split(claim)
        if len(parts) > 1 and all(len(p.strip()) > 5 for p in parts):
            result.extend(p.strip() for p in parts)
        else:
            result.append(claim)
    return result


def _clean_claim(text: str) -> str:
    """Clean up a claim text: strip, remove trailing conjunctions."""
    text = text.strip()
    # Remove leading conjunctions
    text = re.sub(r"^(?:and|but|also|then|so)\s+", "", text, flags=re.IGNORECASE)
    # Ensure first letter is capitalized
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text


class ClaimDecomposer:
    """Decomposes LLM responses into atomic, verifiable claims."""

    def __init__(self, mode: str = "fast") -> None:
        """Initialize decomposer.

        Args:
            mode: "fast" for rule-based, "llm" for Claude Haiku.
        """
        self.mode = mode

    def decompose(self, response: str) -> list[Claim]:
        """Decompose a response into atomic claims.

        Args:
            response: The LLM response text to decompose.

        Returns:
            List of Claim objects.
        """
        if self.mode == "fast":
            return self._fast_decompose(response)
        return self._llm_decompose(response)

    def _fast_decompose(self, response: str) -> list[Claim]:
        """Rule-based decomposition — no LLM calls."""
        # Step 1: Split into sentences
        raw_claims = _split_sentences(response)

        # Step 2: Split "with" clauses
        raw_claims = _split_with_clauses(raw_claims)

        # Step 3: Clean up each claim
        claims = []
        seen = set()
        for text in raw_claims:
            text = _clean_claim(text)
            if not text or len(text) < 5:
                continue
            # Deduplicate
            key = text.lower().strip(".")
            if key in seen:
                continue
            seen.add(key)

            claim_type = _classify_claim(text)
            claims.append(
                Claim(
                    text=text,
                    source_response=response,
                    claim_type=claim_type,
                )
            )

        # If no claims were extracted (single short sentence), use the whole response
        if not claims and response.strip():
            claims.append(
                Claim(
                    text=response.strip(),
                    source_response=response,
                    claim_type=_classify_claim(response),
                )
            )

        return claims

    def _llm_decompose(self, response: str) -> list[Claim]:
        """LLM-based decomposition via Claude Haiku.

        Falls back to fast mode if API is unavailable.
        """
        try:
            import anthropic
        except ImportError:
            logger.warning("anthropic not installed, falling back to fast mode")
            return self._fast_decompose(response)

        try:
            client = anthropic.Anthropic()
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Decompose this text into atomic, verifiable claims. "
                            "Each claim should be a single fact that can be independently verified. "
                            "Return ONLY a JSON array of strings, nothing else.\n\n"
                            f"Text: {response}"
                        ),
                    }
                ],
            )

            import json

            raw = message.content[0].text.strip()
            # Extract JSON array from response
            if raw.startswith("["):
                claim_texts = json.loads(raw)
            else:
                # Try to find JSON in the response
                match = re.search(r"\[.*\]", raw, re.DOTALL)
                if match:
                    claim_texts = json.loads(match.group())
                else:
                    logger.warning("Could not parse LLM response, falling back to fast mode")
                    return self._fast_decompose(response)

            return [
                Claim(
                    text=text,
                    source_response=response,
                    claim_type=_classify_claim(text),
                )
                for text in claim_texts
                if isinstance(text, str) and len(text) > 5
            ]

        except Exception as e:
            logger.warning("LLM decomposition failed: %s, falling back to fast mode", e)
            return self._fast_decompose(response)
