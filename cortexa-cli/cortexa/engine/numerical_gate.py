"""Numerical verification gate — Tier 2 of the CAMA pipeline.

Fast pre-filter: extracts numbers from claims and memories, checks for
exact matches, approximate matches (within tolerance), and contradictions.
"""

import re

from cortexa.engine.models import Claim, Memory, NumericalMatch, NumericalResult

# Number extraction patterns
_CURRENCY_RE = re.compile(r"\$\s*([\d,]+\.?\d*)")
_PERCENT_RE = re.compile(r"([\d.]+)\s*%")
_TIME_12H_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*([ap]m)", re.IGNORECASE)
_DURATION_RE = re.compile(
    r"(\d+\.?\d*)\s*(?:-\s*\d+\.?\d*\s*)?(?:business\s+)?(days?|hours?|minutes?|weeks?|months?|years?)",
    re.IGNORECASE,
)
_PLAIN_NUMBER_RE = re.compile(r"(?<!\w)([\d,]+\.?\d*)(?!\w|%|\s*[ap]m)", re.IGNORECASE)


def _parse_currency(text: str) -> list[float]:
    return [float(m.replace(",", "")) for m in _CURRENCY_RE.findall(text)]


def _parse_percent(text: str) -> list[float]:
    return [float(m) / 100.0 for m in _PERCENT_RE.findall(text)]


def _parse_time(text: str) -> list[float]:
    """Parse 12h times to 24h float (e.g., 2pm → 14.0)."""
    results = []
    for hour, minute, ampm in _TIME_12H_RE.findall(text):
        h = int(hour)
        m = int(minute) if minute else 0
        if ampm.lower() == "pm" and h != 12:
            h += 12
        elif ampm.lower() == "am" and h == 12:
            h = 0
        results.append(h + m / 60.0)
    return results


def _parse_duration(text: str) -> list[float]:
    """Parse durations to a canonical number (just the numeric part)."""
    results = []
    for num, _ in _DURATION_RE.findall(text):
        results.append(float(num))
    return results


def _parse_plain_numbers(text: str) -> list[float]:
    """Parse plain numbers not captured by other patterns."""
    # Remove parts already captured by other patterns
    cleaned = _CURRENCY_RE.sub("", text)
    cleaned = _PERCENT_RE.sub("", cleaned)
    cleaned = _TIME_12H_RE.sub("", cleaned)
    cleaned = _DURATION_RE.sub("", cleaned)
    results = []
    for m in _PLAIN_NUMBER_RE.findall(cleaned):
        try:
            val = float(m.replace(",", ""))
            results.append(val)
        except ValueError:
            continue
    return results


def extract_numbers(text: str) -> dict[str, list[float]]:
    """Extract all numbers from text, categorized by type.

    Returns:
        Dict with keys: currency, percent, time, duration, plain.
    """
    return {
        "currency": _parse_currency(text),
        "percent": _parse_percent(text),
        "time": _parse_time(text),
        "duration": _parse_duration(text),
        "plain": _parse_plain_numbers(text),
    }


def _flatten_numbers(nums: dict[str, list[float]]) -> list[float]:
    """Flatten categorized numbers into a single list."""
    result = []
    for values in nums.values():
        result.extend(values)
    return result


def _numbers_match(a: float, b: float, tolerance: float = 0.05) -> str:
    """Compare two numbers. Returns 'exact', 'approximate', or 'contradiction'."""
    if a == b:
        return "exact"
    if a == 0 and b == 0:
        return "exact"
    # Relative tolerance
    denom = max(abs(a), abs(b))
    if denom == 0:
        return "exact"
    relative_diff = abs(a - b) / denom
    if relative_diff <= tolerance:
        return "approximate"
    return "contradiction"


class NumericalGate:
    """Fast numerical verification gate."""

    def __init__(self, tolerance: float = 0.05) -> None:
        self.tolerance = tolerance

    def check(self, claims: list[Claim], memories: list[Memory]) -> NumericalResult:
        """Check numerical consistency between claims and memories.

        For each claim with numbers, checks if those numbers appear in any memory.
        """
        matches: list[NumericalMatch] = []
        contradictions: list[NumericalMatch] = []
        unverified: list[str] = []

        for claim in claims:
            claim_nums = extract_numbers(claim.text)
            claim_flat = _flatten_numbers(claim_nums)

            if not claim_flat:
                continue  # no numbers in this claim

            found_any = False
            for memory in memories:
                mem_nums = extract_numbers(memory.content)
                mem_flat = _flatten_numbers(mem_nums)

                if not mem_flat:
                    continue

                # Compare same-category numbers first, then cross-category
                for category in claim_nums:
                    for cv in claim_nums[category]:
                        for mv in mem_nums.get(category, []):
                            result = _numbers_match(cv, mv, self.tolerance)
                            nm = NumericalMatch(
                                claim_id=claim.id,
                                memory_id=memory.id,
                                claim_value=cv,
                                memory_value=mv,
                                match_type=result,
                                tolerance=self.tolerance,
                            )
                            if result in ("exact", "approximate"):
                                matches.append(nm)
                                found_any = True
                            elif result == "contradiction":
                                contradictions.append(nm)
                                found_any = True

            if not found_any:
                unverified.append(claim.id)

        return NumericalResult(
            matches=matches,
            contradictions=contradictions,
            unverified=unverified,
        )
