"""
Tests for src/algorithms/word_deduplication.py's deduplicate_words --
the presentation filter PlayState runs the generated preset word batch
through before sorting it, so a run never types the same word twice.
"""
from src.algorithms.sort_task import generate_words
from src.algorithms.word_deduplication import deduplicate_words


def test_deduplicate_words_removes_repeats():
    words = ["MAYO", "SOL", "MAYO", "MAYO", "LUZ", "SOL"]
    assert deduplicate_words(words) == ["MAYO", "SOL", "LUZ"]


def test_deduplicate_words_preserves_first_occurrence_order():
    words = ["C", "A", "B", "A", "C", "D"]
    assert deduplicate_words(words) == ["C", "A", "B", "D"]


def test_deduplicate_words_handles_empty_list():
    assert deduplicate_words([]) == []


def test_deduplicate_words_handles_no_duplicates():
    words = ["UNO", "DOS", "TRES"]
    assert deduplicate_words(words) == words


def test_deduplicate_words_handles_all_duplicates():
    assert deduplicate_words(["IGUAL"] * 10) == ["IGUAL"]


def test_deduplicate_words_on_a_real_generated_batch_leaves_no_repeats():
    words = generate_words(500)
    unique_words = deduplicate_words(words)

    assert len(unique_words) == len(set(unique_words))
    assert len(unique_words) <= len(words)
