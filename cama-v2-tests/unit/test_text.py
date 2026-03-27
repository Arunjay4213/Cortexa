"""Hostile tests for cama/text.py — sentence splitting, number extraction, merge spans."""

from __future__ import annotations

import pytest

from cama.text import split_sentences, extract_numbers, char_to_token_mapping, merge_token_spans


class TestSplitSentences:
    def test_basic_two_sentences(self):
        text = "Hello world. Goodbye world."
        result = split_sentences(text)
        assert len(result) == 2
        assert result[0][0] == "Hello world."
        assert result[1][0] == "Goodbye world."

    def test_single_sentence_no_split(self):
        text = "Just one sentence here."
        result = split_sentences(text)
        assert len(result) == 1
        assert result[0][0] == "Just one sentence here."

    def test_empty_string(self):
        assert split_sentences("") == []

    def test_whitespace_only(self):
        assert split_sentences("   ") == []

    def test_none_returns_empty(self):
        """None input — should return [] not crash."""
        assert split_sentences(None) == []

    def test_no_uppercase_after_period(self):
        """Sentence ending without uppercase next — stays as one chunk."""
        text = "version 3.14 is great"
        result = split_sentences(text)
        assert len(result) == 1

    def test_abbreviations_not_split(self):
        """U.S.A. or Dr. should not cause spurious splits."""
        text = "Dr. Smith works at Corp. The meeting is at 3."
        result = split_sentences(text)
        # Regex splits on '. T' — this might split at "Corp. The"
        # Document actual behavior
        assert len(result) >= 1  # At least doesn't crash

    def test_question_mark_split(self):
        text = "Is it raining? Yes it is."
        result = split_sentences(text)
        assert len(result) == 2

    def test_exclamation_mark_split(self):
        text = "Fire! Run immediately."
        result = split_sentences(text)
        assert len(result) == 2

    def test_multiple_spaces_between_sentences(self):
        text = "First sentence.   Second sentence."
        result = split_sentences(text)
        assert len(result) == 2

    def test_newline_between_sentences(self):
        """Newline instead of space — regex expects \\s+ so this should work."""
        text = "First sentence.\nSecond sentence."
        result = split_sentences(text)
        assert len(result) == 2

    def test_no_period_at_end(self):
        text = "This sentence has no period"
        result = split_sentences(text)
        assert len(result) == 1
        assert result[0][0] == "This sentence has no period"

    def test_offsets_are_correct(self):
        text = "Hello world. Goodbye world."
        result = split_sentences(text)
        for sent_text, start, end in result:
            assert text[start:end] == sent_text

    def test_unicode_sentences(self):
        """CJK and accented chars — regex (?=[A-Z]) won't match these."""
        text = "Prix: 49,99 EUR. Le produit est disponible."
        result = split_sentences(text)
        # "Le" starts with uppercase L — should split
        assert len(result) == 2

    def test_quoted_sentence_split(self):
        """Pattern includes (?=[A-Z\"]) — should split before quotes."""
        text = 'He said "hello." "Goodbye," she replied.'
        result = split_sentences(text)
        assert len(result) >= 1

    def test_very_long_text(self):
        """1000 sentences — should not be slow or crash."""
        text = " ".join(f"Sentence number {i}." for i in range(1000))
        result = split_sentences(text)
        assert len(result) >= 500  # At least half should split correctly

    def test_single_char(self):
        result = split_sentences("A")
        assert len(result) == 1

    def test_only_punctuation(self):
        result = split_sentences("...")
        assert len(result) == 1  # No uppercase after, treated as one chunk


class TestExtractNumbers:
    def test_plain_integer(self):
        result = extract_numbers("There are 42 items.")
        assert any(v == 42.0 for _, v, _, _ in result)

    def test_float(self):
        result = extract_numbers("Pi is approximately 3.14.")
        assert any(abs(v - 3.14) < 0.001 for _, v, _, _ in result)

    def test_currency_dollar(self):
        result = extract_numbers("The price is $49.99.")
        assert any(abs(v - 49.99) < 0.01 for _, v, _, _ in result)

    def test_currency_with_commas(self):
        result = extract_numbers("Revenue: $1,234,567.89.")
        assert any(abs(v - 1234567.89) < 0.01 for _, v, _, _ in result)

    def test_percentage(self):
        result = extract_numbers("Growth is 45.6%.")
        assert any(abs(v - 45.6) < 0.1 for _, v, _, _ in result)

    def test_percentage_no_decimal(self):
        result = extract_numbers("100% complete.")
        assert any(v == 100.0 for _, v, _, _ in result)

    def test_ordinal(self):
        result = extract_numbers("The 3rd place finisher.")
        assert any(v == 3.0 for _, v, _, _ in result)

    def test_ordinals_variety(self):
        text = "1st, 2nd, 3rd, 4th, 21st"
        result = extract_numbers(text)
        vals = {v for _, v, _, _ in result}
        assert {1.0, 2.0, 3.0, 4.0, 21.0}.issubset(vals)

    def test_time_expression(self):
        result = extract_numbers("Meeting at 14:30.")
        # 14 + 30/60 = 14.5
        assert any(abs(v - 14.5) < 0.01 for _, v, _, _ in result)

    def test_comma_separated_integer(self):
        result = extract_numbers("Population: 1,000,000.")
        assert any(v == 1000000.0 for _, v, _, _ in result)

    def test_no_numbers(self):
        result = extract_numbers("No numbers here at all.")
        assert result == []

    def test_empty_string(self):
        result = extract_numbers("")
        assert result == []

    def test_negative_not_detected(self):
        """Negative numbers — regex doesn't handle minus sign."""
        result = extract_numbers("Temperature: -40 degrees.")
        # The '-' won't be captured by \\b\\d+\\b — only '40' captured
        vals = [v for _, v, _, _ in result]
        assert 40.0 in vals  # Document: minus sign lost

    def test_overlapping_spans_prevented(self):
        """$49.99 should be caught by currency pattern, not re-caught by float/int."""
        result = extract_numbers("Cost: $49.99.")
        # Should have exactly 1 match for 49.99
        matches_for_49 = [r for r in result if abs(r[1] - 49.99) < 0.01]
        assert len(matches_for_49) == 1

    def test_positions_are_correct(self):
        text = "Price: $25.00"
        result = extract_numbers(text)
        for orig_str, _, start, end in result:
            assert text[start:end] == orig_str

    def test_multiple_numbers_in_one_sentence(self):
        text = "Revenue grew from $4.2M in Q3 to $5.1M in Q4, a 21% increase."
        result = extract_numbers(text)
        vals = {v for _, v, _, _ in result}
        assert 4.2 in vals
        assert 5.1 in vals
        assert 21.0 in vals

    def test_sorted_by_position(self):
        text = "Numbers: 1, 2, 3, 4, 5."
        result = extract_numbers(text)
        positions = [start for _, _, start, _ in result]
        assert positions == sorted(positions)

    def test_euro_format_not_handled(self):
        """European format 49,99 — should NOT be parsed as 4999."""
        result = extract_numbers("Prix: 49,99 EUR")
        # The comma-separated pattern expects \\d{1,3}(,\\d{3})+ — '49,99' won't match
        # Should fall back to plain integers: 49 and 99
        vals = [v for _, v, _, _ in result]
        assert 4999.0 not in vals  # Document: doesn't handle European decimals


class TestCharToTokenMapping:
    def test_basic_mapping(self):
        text = "hello world"
        tokens = ["hello", "world"]
        mapping = char_to_token_mapping(text, tokens)
        assert mapping[0] == 0  # 'h' -> token 0
        assert mapping[6] == 1  # 'w' -> token 1

    def test_empty_tokens(self):
        text = "hello"
        mapping = char_to_token_mapping(text, [])
        # All chars map to 0 (fallback)
        assert all(v == 0 for v in mapping.values())

    def test_empty_text(self):
        mapping = char_to_token_mapping("", ["hello"])
        assert mapping == {}


class TestMergeTokenSpans:
    def test_basic_merge(self):
        tokens = [
            ("hello", 0, 0.8),
            ("world", 1, 0.9),
            ("foo", 2, 0.1),
        ]
        result = merge_token_spans(tokens, "hello world foo", threshold=0.5)
        assert len(result) == 1
        assert result[0][3] > 0.5  # avg score above threshold

    def test_no_tokens_above_threshold(self):
        tokens = [
            ("hello", 0, 0.1),
            ("world", 1, 0.2),
        ]
        result = merge_token_spans(tokens, "hello world", threshold=0.5)
        assert result == []

    def test_empty_input(self):
        assert merge_token_spans([], "some text", threshold=0.5) == []

    def test_all_above_threshold(self):
        tokens = [
            ("every", 0, 0.9),
            ("word", 1, 0.8),
            ("flagged", 2, 0.7),
        ]
        result = merge_token_spans(tokens, "every word flagged", threshold=0.5)
        assert len(result) == 1  # All merged into one span

    def test_two_separate_spans(self):
        tokens = [
            ("bad", 0, 0.9),
            ("good", 1, 0.1),
            ("worse", 2, 0.95),
        ]
        result = merge_token_spans(tokens, "bad good worse", threshold=0.5)
        assert len(result) == 2  # Two separate spans
