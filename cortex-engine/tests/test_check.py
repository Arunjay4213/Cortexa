"""
Tests for the CortexOS verification pipeline.

Run:
    pytest tests/test_check.py -v
"""

from app.services.numerical import check_numerical, extract_numbers


class TestExtractNumbers:
    def test_plain_numbers(self):
        nums = extract_numbers("There are 45 items and 100 more")
        assert "45" in nums
        assert "100" in nums

    def test_dollar_amounts(self):
        nums = extract_numbers("The price is $899 and premium is $12,000")
        assert "899" in nums
        assert "12000" in nums

    def test_percentages(self):
        nums = extract_numbers("Growth of 94.2% and 100%")
        assert "94.2%" in nums
        assert "100%" in nums

    def test_day_ranges(self):
        nums = extract_numbers("A 45-day return and 60-day trial")
        assert "45-day" in nums
        assert "60-day" in nums

    def test_no_numbers(self):
        nums = extract_numbers("No numbers here at all")
        assert len(nums) == 0


class TestCheckNumerical:
    def test_matching_numbers(self):
        passed, reason = check_numerical(
            "The price is $899",
            "Sonos Arc retail price is $899.",
        )
        assert passed is True
        assert reason == ""

    def test_mismatched_price(self):
        passed, reason = check_numerical(
            "The Sonos Arc costs $999",
            "Sonos Arc retail price is $899.",
        )
        assert passed is False
        assert "NUM_MISMATCH" in reason

    def test_mismatched_days(self):
        passed, reason = check_numerical(
            "60-day return policy",
            "Return policy: 45-day return window.",
        )
        assert passed is False
        assert "NUM_MISMATCH" in reason

    def test_no_numbers_in_claim(self):
        passed, reason = check_numerical(
            "Free shipping on all orders",
            "Free shipping on orders over $50.",
        )
        assert passed is True
        assert reason == ""
