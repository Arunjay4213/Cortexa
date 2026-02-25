import pytest
from cortex.attribution.statement import (
    segment_into_statements,
    compute_statement_attribution,
    _token_overlap_score,
)

# --- Segmentation Tests ---

def test_segment_empty():
    assert segment_into_statements("") == []

def test_segment_single_sentence():
    result = segment_into_statements("Hello world.")
    assert result == ["Hello world."]

def test_segment_multiple_sentences():
    result = segment_into_statements("First sentence. Second sentence. Third sentence.")
    assert len(result) == 3

def test_segment_question_marks():
    result = segment_into_statements("What is this? It is a test. Really!")
    assert len(result) == 3

def test_segment_no_trailing_period():
    result = segment_into_statements("Hello world")
    assert result == ["Hello world"]

def test_segment_preserves_content():
    text = "The cat sat. The dog ran."
    result = segment_into_statements(text)
    assert "cat" in result[0]
    assert "dog" in result[1]

# --- Token Overlap Tests ---

def test_overlap_identical():
    """Identical texts should have high overlap."""
    score = _token_overlap_score("Python is great for data science", "Python is great for data science")
    assert score > 0.8

def test_overlap_disjoint():
    """Completely different texts should have low overlap."""
    score = _token_overlap_score("astronomy telescope galaxies", "cooking recipe ingredients")
    assert score < 0.1

def test_overlap_partial():
    """Partially overlapping texts should have medium score."""
    score = _token_overlap_score(
        "Python machine learning algorithms",
        "Python programming language algorithms data structures"
    )
    assert 0.2 < score < 0.9

def test_overlap_empty():
    """Empty statement should return 0."""
    assert _token_overlap_score("", "anything") == 0.0

def test_overlap_stopwords_ignored():
    """Stopwords should not count toward overlap."""
    # Only stopwords - should give 0
    score = _token_overlap_score("the is a and or but", "the is a and or but")
    assert score == 0.0

# --- Statement Attribution Tests ---

def test_attribution_empty_response():
    result = compute_statement_attribution("", ["memory1"], ["m1"])
    assert len(result.statements) == 0

def test_attribution_empty_memories():
    result = compute_statement_attribution("Hello world.", [], [])
    assert len(result.statements) == 0

def test_attribution_basic():
    result = compute_statement_attribution(
        "Python is used for data science. Rust is used for systems programming.",
        ["Python is the top language for machine learning and data science",
         "Rust provides memory safety for systems code"],
        ["mem-py", "mem-rs"],
    )
    assert len(result.statements) == 2
    assert result.statements[0].top_memory_id == "mem-py"
    assert result.statements[1].top_memory_id == "mem-rs"

def test_attribution_grounding_rate():
    """Grounding rate should be fraction of grounded statements."""
    result = compute_statement_attribution(
        "Relevant statement. Completely unrelated gibberish xyz.",
        ["This is a relevant memory about statements"],
        ["m1"],
    )
    assert 0.0 <= result.grounding_rate <= 1.0

def test_attribution_top_5_limit():
    """Should return at most 5 attributed memories per statement."""
    memories = [f"Memory about topic {i}" for i in range(10)]
    ids = [f"m{i}" for i in range(10)]
    result = compute_statement_attribution("Topic 0 is great.", memories, ids)
    for stmt in result.statements:
        assert len(stmt.attributed_memories) <= 5

def test_attribution_ungrounded_list():
    """Ungrounded statements should be listed."""
    result = compute_statement_attribution(
        "First sentence. Second sentence.",
        ["memory about first"],
        ["m1"],
        grounding_threshold=0.99,  # very high threshold
    )
    # Most statements won't be grounded with threshold=0.99
    assert isinstance(result.ungrounded_statements, list)
