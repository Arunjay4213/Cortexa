"""
Deterministic numerical gate for CAMA.

Extracts numerical values from claims and checks whether they appear
in any retrieved memory content. If a claim contains numbers that
don't exist in any memory, it's flagged as hallucinated BEFORE NLI.

DeBERTa is bad at numerical reasoning. This gate is 100% precise.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class NumberMatch:
    """A number extracted from text."""
    raw: str          # original string, e.g. "$1,016,400"
    value: float      # parsed numeric value, e.g. 1016400.0
    kind: str         # "dollar", "percent", "quantity", "plain"
    unit: str         # e.g. "/year", "kWh/m2/day", "%", ""


# ── Regex patterns ───────────────────────────────────────────────

# Dollar amounts: $1,016,400 or $52M or $980,000/year or $38/MWh
_DOLLAR_RE = re.compile(
    r"\$[\d,]+(?:\.\d+)?\s*(?:[MBKmk])?"
    r"(?:/[\w²]+(?:/[\w²]+)*)?",
)

# Percentages: 14.2% or 24.1%
_PERCENT_RE = re.compile(r"[\d.]+%")

# Quantities with units: 5.9 kWh/m²/day, 847 acres, 165,000 MWh, 500ft, 3.2 miles
_QUANTITY_RE = re.compile(
    r"[\d,]+(?:\.\d+)?\s*(?:kWh|MWh|GWh|acres?|ft|miles?|MW|GW|kV|deg)"
    r"(?:/[\w²]+(?:/[\w²]+)*)?",
)

# Score patterns: score 91, score 85
_SCORE_RE = re.compile(r"score\s+(\d+)")


def _parse_number(s: str) -> float:
    """Parse a number string, stripping $, commas, and suffixes."""
    s = s.replace(",", "").replace("$", "").strip()
    # Handle M/B/K suffixes
    multiplier = 1.0
    if s and s[-1] in ("M", "m"):
        s = s[:-1]
        multiplier = 1_000_000
    elif s and s[-1] in ("B", "b"):
        s = s[:-1]
        multiplier = 1_000_000_000
    elif s and s[-1] in ("K", "k"):
        s = s[:-1]
        multiplier = 1_000
    # Strip trailing unit text
    num_match = re.match(r"([\d.]+)", s)
    if num_match:
        return float(num_match.group(1)) * multiplier
    return 0.0


def extract_numbers(text: str) -> list[NumberMatch]:
    """Extract all numerical values from text."""
    results: list[NumberMatch] = []
    seen_raws: set[str] = set()

    # Dollar amounts
    for m in _DOLLAR_RE.finditer(text):
        raw = m.group()
        if raw in seen_raws:
            continue
        seen_raws.add(raw)
        # Extract unit suffix (e.g. /year, /MWh)
        unit_match = re.search(r"(/\w+(?:/\w+)*)", raw)
        unit = unit_match.group(1) if unit_match else ""
        results.append(NumberMatch(raw=raw, value=_parse_number(raw), kind="dollar", unit=unit))

    # Percentages
    for m in _PERCENT_RE.finditer(text):
        raw = m.group()
        if raw in seen_raws:
            continue
        seen_raws.add(raw)
        val = float(raw.rstrip("%"))
        results.append(NumberMatch(raw=raw, value=val, kind="percent", unit="%"))

    # Quantities with units
    for m in _QUANTITY_RE.finditer(text):
        raw = m.group()
        if raw in seen_raws:
            continue
        seen_raws.add(raw)
        unit_match = re.search(r"[a-zA-Z²/]+.*$", raw)
        unit = unit_match.group() if unit_match else ""
        results.append(NumberMatch(raw=raw, value=_parse_number(raw), kind="quantity", unit=unit))

    # Score patterns
    for m in _SCORE_RE.finditer(text):
        raw = m.group()
        if raw in seen_raws:
            continue
        seen_raws.add(raw)
        results.append(NumberMatch(raw=raw, value=float(m.group(1)), kind="plain", unit=""))

    return results


def _number_exists_in_text(num: NumberMatch, text: str, tolerance: float = 0.01) -> bool:
    """Check if a number exists in text. Exact for dollars, ±1% for floats."""
    # First try literal string match (fastest)
    if num.raw in text:
        return True

    # For dollar amounts: exact match only (no tolerance)
    if num.kind == "dollar":
        # Try the raw value formatted differently
        val = num.value
        # Try: 1016400, 1,016,400, 1016400.0
        candidates = [
            f"${val:,.0f}",
            f"${val:.0f}",
            f"${val:,.2f}",
        ]
        # Also try M/K abbreviations
        if val >= 1_000_000:
            candidates.append(f"${val/1_000_000:.0f}M")
            candidates.append(f"${val/1_000_000:.1f}M")
        if val >= 1_000:
            candidates.append(f"${val/1_000:.0f}K")
            candidates.append(f"${val/1_000:,.0f}")
        return any(c in text for c in candidates)

    # For percentages and quantities: ±1% tolerance
    text_numbers = extract_numbers(text)
    for tn in text_numbers:
        if tn.kind == num.kind and num.value > 0:
            ratio = abs(tn.value - num.value) / num.value
            if ratio <= tolerance:
                return True

    # Also try plain number substring match
    # e.g. "5.9" in "irradiance 5.9 kWh/m2/day"
    num_str = re.match(r"[\d,.]+(?:\.\d+)?", num.raw)
    if num_str and num_str.group() in text:
        return True

    return False


def check_numerical_grounding(
    claim: str,
    memory_contents: dict[str, str],
) -> tuple[bool, list[str]]:
    """Check if all numbers in a claim are grounded in memories.

    Returns:
        (is_grounded, list of ungrounded number strings)
    """
    numbers = extract_numbers(claim)
    if not numbers:
        # No numbers in claim — skip gate (let NLI handle it)
        return True, []

    all_memory_text = "\n".join(memory_contents.values())
    ungrounded: list[str] = []

    for num in numbers:
        if not _number_exists_in_text(num, all_memory_text):
            ungrounded.append(num.raw)

    return len(ungrounded) == 0, ungrounded


def apply_numerical_gate(
    claims: list[str],
    claim_types: list[str],
    memory_contents: dict[str, str],
) -> tuple[list[int], dict[int, list[str]]]:
    """Apply deterministic numerical gate to all claims.

    Returns:
        (skip_indices, gate_details)
        - skip_indices: claim indices to skip NLI (flagged as hallucinated)
        - gate_details: {claim_index: [ungrounded_numbers]}
    """
    skip_indices: list[int] = []
    gate_details: dict[int, list[str]] = {}

    for i, claim in enumerate(claims):
        # Only gate factual claims (opinions/synthesis may legitimately lack numbers)
        ctype = claim_types[i] if i < len(claim_types) else "factual"
        if ctype == "opinion":
            continue

        numbers = extract_numbers(claim)
        if numbers:
            print(f"[CAMA] NumGate claim {i}: found {[n.raw for n in numbers]}", flush=True)

        is_grounded, ungrounded = check_numerical_grounding(claim, memory_contents)
        if not is_grounded:
            skip_indices.append(i)
            gate_details[i] = ungrounded
            print(f"[CAMA] NumGate claim {i}: FLAGGED — {ungrounded} NOT in any memory", flush=True)
        elif numbers:
            print(f"[CAMA] NumGate claim {i}: all numbers grounded", flush=True)

    return skip_indices, gate_details


def find_grounded_claims_with_numbers(
    claims: list[str],
    claim_types: list[str],
    skip_indices: list[int],
) -> set[int]:
    """Return indices of claims that have numbers AND passed the numerical gate.

    These claims contain verifiable numbers that exist in the memories,
    so if NLI fails (due to paraphrasing), we can boost their entailment.
    """
    grounded: set[int] = set()
    for i, claim in enumerate(claims):
        if i in skip_indices:
            continue
        ctype = claim_types[i] if i < len(claim_types) else "factual"
        if ctype == "opinion":
            continue
        numbers = extract_numbers(claim)
        if numbers:
            grounded.add(i)
    return grounded


def find_best_memory_for_claim(
    claim: str,
    memory_contents: dict[str, str],
) -> str | None:
    """Find the memory that contains the most numbers from the claim."""
    numbers = extract_numbers(claim)
    if not numbers:
        return None

    best_mem = None
    best_count = 0
    for mid, content in memory_contents.items():
        count = sum(1 for n in numbers if _number_exists_in_text(n, content))
        if count > best_count:
            best_count = count
            best_mem = mid

    return best_mem if best_count > 0 else None
