"""Tests for cama/text.py — text utilities."""

import pytest

from cama.text import (
    char_to_token_mapping,
    extract_numbers,
    merge_token_spans,
    split_sentences,
)


class TestSplitSentences:
    def test_single_sentence(self):
        result = split_sentences("Hello world.")
        assert len(result) == 1
        assert result[0][0] == "Hello world."
        assert result[0][1] == 0
        assert result[0][2] == 12

    def test_multiple_sentences(self):
        text = "First sentence. Second sentence. Third sentence."
        result = split_sentences(text)
        assert len(result) == 3
        assert result[0][0] == "First sentence."
        assert result[1][0] == "Second sentence."
        assert result[2][0] == "Third sentence."

    def test_question_and_exclamation(self):
        text = "Is it true? Yes! Absolutely."
        result = split_sentences(text)
        assert len(result) == 3

    def test_preserves_offsets(self):
        text = "First. Second."
        result = split_sentences(text)
        for sent, start, end in result:
            assert text[start:end] == sent

    def test_empty_string(self):
        assert split_sentences("") == []
        assert split_sentences("   ") == []

    def test_no_period(self):
        result = split_sentences("No period here")
        assert len(result) == 1
        assert result[0][0] == "No period here"

    def test_abbreviations_not_split(self):
        # Abbreviations like "e.g." shouldn't cause extra splits
        # when not followed by space + uppercase
        text = "The price is $5.99 per item."
        result = split_sentences(text)
        assert len(result) == 1

    def test_mixed_punctuation(self):
        text = "What happened? It crashed! The server is down."
        result = split_sentences(text)
        assert len(result) == 3


class TestExtractNumbers:
    def test_integer(self):
        result = extract_numbers("There are 42 items")
        assert len(result) == 1
        assert result[0][0] == "42"
        assert result[0][1] == 42.0

    def test_float(self):
        result = extract_numbers("Pi is 3.14")
        assert len(result) == 1
        assert result[0][1] == 3.14

    def test_percentage(self):
        result = extract_numbers("Growth was 15.5%")
        assert len(result) == 1
        assert result[0][1] == 15.5

    def test_currency(self):
        result = extract_numbers("Price is $49.99")
        assert len(result) == 1
        assert result[0][0] == "$49.99"
        assert result[0][1] == 49.99

    def test_comma_separated(self):
        result = extract_numbers("Population is 1,000,000")
        assert any(r[1] == 1_000_000 for r in result)

    def test_ordinal(self):
        result = extract_numbers("He finished 3rd")
        assert any(r[1] == 3.0 for r in result)

    def test_time(self):
        result = extract_numbers("Meeting at 2:30")
        assert len(result) == 1
        assert result[0][1] == 2.5

    def test_multiple_numbers(self):
        result = extract_numbers("From 10 to 20, total $99.99")
        assert len(result) >= 3

    def test_no_numbers(self):
        result = extract_numbers("No numbers here")
        assert result == []

    def test_positions_correct(self):
        text = "The value is 42."
        result = extract_numbers(text)
        for orig, val, start, end in result:
            assert text[start:end] == orig

    def test_no_overlap(self):
        result = extract_numbers("$1,234.56 costs money")
        # Should not double-count sub-parts
        positions = [(r[2], r[3]) for r in result]
        for i, (s1, e1) in enumerate(positions):
            for j, (s2, e2) in enumerate(positions):
                if i != j:
                    assert not (s1 <= s2 < e1) and not (s1 < e2 <= e1)


class TestCharToTokenMapping:
    def test_simple(self):
        text = "hello world"
        tokens = ["hello", "world"]
        mapping = char_to_token_mapping(text, tokens)
        # 'h','e','l','l','o' → token 0
        for i in range(5):
            assert mapping[i] == 0
        # ' ' might map to token 1
        # 'w','o','r','l','d' → token 1
        for i in range(6, 11):
            assert mapping[i] == 1

    def test_empty_tokens(self):
        mapping = char_to_token_mapping("", [])
        assert mapping == {}

    def test_single_token(self):
        mapping = char_to_token_mapping("hi", ["hi"])
        assert mapping[0] == 0
        assert mapping[1] == 0


class TestMergeTokenSpans:
    def test_single_span(self):
        tokens = [
            ("good", 0, 0.1),
            ("bad", 1, 0.8),
            ("bad2", 2, 0.9),
            ("good2", 3, 0.2),
        ]
        spans = merge_token_spans(tokens, "good bad bad2 good2")
        assert len(spans) == 1
        assert spans[0][3] > 0.5  # avg score

    def test_two_spans(self):
        tokens = [
            ("a", 0, 0.8),
            ("b", 1, 0.1),
            ("c", 2, 0.9),
        ]
        spans = merge_token_spans(tokens, "a b c")
        assert len(spans) == 2

    def test_no_spans(self):
        tokens = [("ok", 0, 0.1), ("fine", 1, 0.2)]
        spans = merge_token_spans(tokens, "ok fine")
        assert len(spans) == 0

    def test_all_hallucinated(self):
        tokens = [("x", 0, 0.8), ("y", 1, 0.9)]
        spans = merge_token_spans(tokens, "x y")
        assert len(spans) == 1

    def test_empty(self):
        assert merge_token_spans([], "text") == []
