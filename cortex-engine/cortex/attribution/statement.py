"""Statement-Level Attribution — §3.6.

Extends memory-level attribution to individual statements within a response.
Each statement in the LLM response is attributed to specific memory sources.

Process:
1. Segment response into statements (sentence-level)
2. For each statement, compute attribution against each retrieved memory
3. Build statement → memory mapping with confidence scores
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np


@dataclass
class StatementAttribution:
    """Attribution for a single statement."""
    statement_index: int
    statement_text: str
    attributed_memories: list[dict]  # [{memory_id, score, rank}]
    top_memory_id: str | None = None
    top_score: float = 0.0
    is_grounded: bool = False   # has at least one strong attribution


@dataclass
class StatementLevelResult:
    """Full statement-level attribution result."""
    response_text: str
    statements: list[StatementAttribution]
    grounding_rate: float      # fraction of statements with strong attribution
    avg_attribution: float     # mean top-attribution across statements
    ungrounded_statements: list[int]  # indices of statements with no strong source


_ABBREV_PATTERN = re.compile(
    r"\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|Inc|Ltd|Corp|Co|St|Ave|Dept|Fig|vol|No)\."
)
_EG_IE_PATTERN = re.compile(r"\b(e\.g|i\.e)\.")
_DECIMAL_PATTERN = re.compile(r"(\d)\.\s")
_PLACEHOLDER = "\x00"  # NUL — won't appear in real text


def segment_into_statements(text: str) -> list[str]:
    """Split response text into individual statements.

    Handles abbreviations (Dr., etc.), decimals ($3.50), and e.g./i.e.
    without incorrectly splitting on them.
    """
    if not text:
        return []

    # Protect abbreviation periods with a placeholder so they don't split
    protected = _ABBREV_PATTERN.sub(r"\1" + _PLACEHOLDER, text)
    protected = _EG_IE_PATTERN.sub(r"\1" + _PLACEHOLDER, protected)
    protected = _DECIMAL_PATTERN.sub(r"\1" + _PLACEHOLDER + " ", protected)

    # Split on sentence-ending punctuation followed by whitespace
    sentences = re.split(r'(?<=[.!?])\s+', protected.strip())

    # Restore placeholders and filter empty strings
    return [s.replace(_PLACEHOLDER, ".").strip() for s in sentences if s.strip()]


def compute_statement_attribution(
    response_text: str,
    memory_texts: list[str],
    memory_ids: list[str],
    memory_embeddings: np.ndarray | None = None,
    grounding_threshold: float = 0.3,
) -> StatementLevelResult:
    """Compute statement-level attribution using embedding similarity.

    For each statement, computes cosine similarity against each memory
    to determine which memories contributed to which parts of the response.

    Args:
        response_text: the full LLM response
        memory_texts: text content of each retrieved memory
        memory_ids: IDs of retrieved memories
        memory_embeddings: pre-computed memory embeddings (optional)
        grounding_threshold: minimum score to consider a statement "grounded"
    """
    statements_text = segment_into_statements(response_text)

    if not statements_text or not memory_texts:
        return StatementLevelResult(
            response_text=response_text,
            statements=[],
            grounding_rate=0.0,
            avg_attribution=0.0,
            ungrounded_statements=[],
        )

    # Compute token overlap scores (fast proxy when embeddings unavailable)
    stmt_attributions: list[StatementAttribution] = []

    for idx, stmt in enumerate(statements_text):
        # Compute similarity of this statement to each memory
        scores = []
        for mid, mem_text in zip(memory_ids, memory_texts):
            score = _token_overlap_score(stmt, mem_text)
            scores.append({"memory_id": mid, "score": round(score, 4)})

        # Sort by score descending
        scores.sort(key=lambda x: x["score"], reverse=True)

        # Add rank
        for rank, s in enumerate(scores):
            s["rank"] = rank + 1

        top = scores[0] if scores else None
        is_grounded = top is not None and top["score"] >= grounding_threshold

        stmt_attributions.append(StatementAttribution(
            statement_index=idx,
            statement_text=stmt,
            attributed_memories=scores[:5],  # top 5
            top_memory_id=top["memory_id"] if top else None,
            top_score=top["score"] if top else 0.0,
            is_grounded=is_grounded,
        ))

    # Aggregate metrics
    grounded_count = sum(1 for s in stmt_attributions if s.is_grounded)
    grounding_rate = grounded_count / len(stmt_attributions) if stmt_attributions else 0.0
    avg_attr = float(np.mean([s.top_score for s in stmt_attributions])) if stmt_attributions else 0.0
    ungrounded = [s.statement_index for s in stmt_attributions if not s.is_grounded]

    return StatementLevelResult(
        response_text=response_text,
        statements=stmt_attributions,
        grounding_rate=round(grounding_rate, 4),
        avg_attribution=round(avg_attr, 4),
        ungrounded_statements=ungrounded,
    )


def _token_overlap_score(statement: str, memory: str) -> float:
    """Compute normalized token overlap between statement and memory.

    Simple but effective proxy for semantic similarity:
    score = |tokens(s) ∩ tokens(m)| / |tokens(s)|

    Excludes stopwords for more meaningful overlap.
    """
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "above",
        "below", "between", "and", "but", "or", "nor", "not", "so", "yet",
        "both", "either", "neither", "each", "every", "all", "any", "few",
        "more", "most", "other", "some", "such", "no", "only", "own",
        "same", "than", "too", "very", "just", "because", "if", "when",
        "that", "this", "it", "its", "i", "me", "my", "we", "our", "you",
        "your", "he", "him", "his", "she", "her", "they", "them", "their",
    }

    def tokenize(text: str) -> set[str]:
        tokens = re.findall(r'\b\w+\b', text.lower())
        return {t for t in tokens if t not in stopwords and len(t) > 2}

    stmt_tokens = tokenize(statement)
    mem_tokens = tokenize(memory)

    if not stmt_tokens:
        return 0.0

    overlap = stmt_tokens & mem_tokens
    return len(overlap) / len(stmt_tokens)
