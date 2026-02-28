import re


def extract_numbers(text: str) -> set[str]:
    """
    Extract all numbers from text in normalized form.
    Handles: 45, 45.5, $12,000, 94.2%, $899, 60-day, etc.
    Returns set of normalized number strings.
    """
    patterns = [
        r"\$[\d,]+(?:\.\d+)?",  # $12,000 or $899.99
        r"[\d,]+(?:\.\d+)?%",  # 94.2% or 100%
        r"[\d,]+(?:\.\d+)?(?:\s*-\s*(?:day|year|month|week|hour|minute))",  # 45-day
        r"(?<!\w)[\d,]+(?:\.\d+)?(?!\w)",  # plain numbers
    ]
    numbers = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            num = match.group()
            # Normalize: remove $ and commas, keep the number
            normalized = re.sub(r"[$,]", "", num).strip()
            numbers.add(normalized)
    return numbers


def check_numerical(claim: str, sources_text: str) -> tuple[bool, str]:
    """
    Check if numbers in claim exist in sources.

    Returns (passed, reason):
      (True, "") if no numbers or all numbers found
      (False, "NUM_MISMATCH: ...") if numbers don't match
    """
    claim_nums = extract_numbers(claim)
    if not claim_nums:
        return True, ""

    source_nums = extract_numbers(sources_text)

    missing = claim_nums - source_nums
    if missing:
        found = claim_nums & source_nums
        context = found if found else source_nums
        return (
            False,
            f"NUM_MISMATCH: {missing} not found in sources. Sources contain: {context}",
        )

    return True, ""
