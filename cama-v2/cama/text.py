"""Text utilities: sentence splitting, number extraction, char-to-token mapping."""

from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)


def split_sentences(text: str) -> list[tuple[str, int, int]]:
    """Split text into sentences with character offsets.

    Returns list of (sentence_text, start_char, end_char).
    Uses regex-based splitting on sentence-ending punctuation followed by
    whitespace and an uppercase letter (or end of string).
    """
    if not text or not text.strip():
        return []

    # Match sentence boundaries: punctuation followed by space+uppercase or end
    # We split on the boundary but keep the punctuation with the preceding sentence.
    pattern = r'(?<=[.!?])\s+(?=[A-Z"])'
    parts = re.split(pattern, text)

    results: list[tuple[str, int, int]] = []
    offset = 0
    for part in parts:
        part_stripped = part.strip()
        if not part_stripped:
            offset += len(part)
            continue
        # Find actual start in original text
        start = text.index(part_stripped, offset)
        end = start + len(part_stripped)
        results.append((part_stripped, start, end))
        offset = end

    return results


def extract_numbers(text: str) -> list[tuple[str, float, int, int]]:
    """Extract numeric values from text with positions.

    Returns list of (original_string, normalized_value, start_char, end_char).
    Handles: integers, floats, percentages, currency ($49.99), ordinals,
    time expressions, and common written forms.
    """
    results: list[tuple[str, float, int, int]] = []
    seen_spans: set[tuple[int, int]] = set()

    patterns = [
        # Currency: $1,234.56 or $49.99
        (r'\$[\d,]+\.?\d*', lambda m: float(m.group().replace('$', '').replace(',', ''))),
        # Percentages: 45.6% or 100%
        (r'\d+\.?\d*\s*%', lambda m: float(m.group().replace('%', '').strip())),
        # Time: 2:30, 14:00
        (r'\b\d{1,2}:\d{2}\b', lambda m: float(m.group().split(':')[0]) + float(m.group().split(':')[1]) / 60),
        # Ordinals: 1st, 2nd, 3rd, 4th, 21st, etc.
        (r'\b\d+(?:st|nd|rd|th)\b', lambda m: float(re.match(r'\d+', m.group()).group())),
        # Numbers with units: 750mg, 500ml, 10kg, etc.
        (r'\b\d+\.?\d*(?:mg|ml|kg|lb|oz|cm|mm|km|mi|hr|min|sec|ms|gb|mb|kb|tb)\b',
         lambda m: float(re.match(r'[\d.]+', m.group()).group())),
        # Decimal numbers: 3.14, 0.5
        (r'\b\d+\.\d+\b', lambda m: float(m.group())),
        # Integers with commas: 1,000,000
        (r'\b\d{1,3}(?:,\d{3})+\b', lambda m: float(m.group().replace(',', ''))),
        # Plain integers
        (r'\b\d+\b', lambda m: float(m.group())),
    ]

    for pattern, normalizer in patterns:
        for match in re.finditer(pattern, text):
            span = (match.start(), match.end())
            # Skip if this span overlaps with an already-found number
            if any(s[0] <= span[0] < s[1] or s[0] < span[1] <= s[1] for s in seen_spans):
                continue
            try:
                value = normalizer(match)
                results.append((match.group(), value, span[0], span[1]))
                seen_spans.add(span)
            except (ValueError, AttributeError):
                continue

    # Sort by position
    results.sort(key=lambda x: x[2])
    return results


def char_to_token_mapping(text: str, tokens: list[str]) -> dict[int, int]:
    """Map character positions in text to token indices.

    Given the original text and a list of tokens (that when joined reconstruct
    the text approximately), returns a dict mapping each character index to
    the token index it belongs to.
    """
    mapping: dict[int, int] = {}
    char_pos = 0

    for token_idx, token in enumerate(tokens):
        # Handle special token prefixes (e.g., '##', 'Ġ' from BPE)
        clean_token = token.lstrip('#').replace('Ġ', ' ').replace('▁', ' ')
        if clean_token.startswith(' '):
            clean_token = clean_token.lstrip(' ')
            # Skip whitespace in text
            while char_pos < len(text) and text[char_pos] == ' ':
                mapping[char_pos] = token_idx
                char_pos += 1

        # Map characters of this token
        for char in clean_token:
            if char_pos < len(text):
                # Try exact match
                if text[char_pos].lower() == char.lower():
                    mapping[char_pos] = token_idx
                    char_pos += 1
                else:
                    # Skip whitespace in text
                    while char_pos < len(text) and text[char_pos] in ' \t\n':
                        mapping[char_pos] = token_idx
                        char_pos += 1
                    if char_pos < len(text):
                        mapping[char_pos] = token_idx
                        char_pos += 1

    # Map any remaining characters to the last token
    while char_pos < len(text):
        mapping[char_pos] = len(tokens) - 1 if tokens else 0
        char_pos += 1

    return mapping


def merge_token_spans(
    token_scores: list[tuple[str, int, float]],
    text: str,
    threshold: float = 0.5,
) -> list[tuple[str, int, int, float, list[tuple[str, int, float]]]]:
    """Merge consecutive tokens above threshold into spans.

    Args:
        token_scores: list of (token_text, token_index, hallucination_prob)
        text: the original answer text
        threshold: probability threshold for flagging

    Returns:
        list of (span_text, start_char, end_char, avg_score, token_scores_in_span)
    """
    if not token_scores:
        return []

    spans = []
    current_span_tokens: list[tuple[str, int, float]] = []

    for token_text, token_idx, prob in token_scores:
        if prob > threshold:
            current_span_tokens.append((token_text, token_idx, prob))
        else:
            if current_span_tokens:
                spans.append(current_span_tokens)
                current_span_tokens = []

    if current_span_tokens:
        spans.append(current_span_tokens)

    # Convert token spans to character spans
    results = []
    for span_tokens in spans:
        span_text = ''.join(
            t.replace('Ġ', ' ').replace('▁', ' ').lstrip('#')
            for t, _, _ in span_tokens
        ).strip()

        if not span_text:
            continue

        # Find span in original text (approximate match)
        avg_score = sum(p for _, _, p in span_tokens) / len(span_tokens)

        # Try to locate in original text
        start = text.lower().find(span_text.lower())
        if start == -1:
            # Fallback: use first few words to find approximate location
            words = span_text.split()[:3]
            search = ' '.join(words)
            start = text.lower().find(search.lower())
            if start == -1:
                start = 0

        end = start + len(span_text)
        actual_text = text[start:end] if end <= len(text) else span_text

        results.append((actual_text, start, end, avg_score, span_tokens))

    return results
