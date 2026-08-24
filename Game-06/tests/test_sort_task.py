"""
Tests for src/algorithms/sort_task.py -- the standalone "sort 500 real
words by length" exercise PlayState runs (see PlayState._begin_sort_task)
before every run starts.
"""
import random

import settings
from src.algorithms.sort_task import generate_words, run_sort_words_by_length, sort_words_by_length


def _random_words(count: int) -> list:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return ["".join(random.choices(alphabet, k=random.randint(1, 12))) for _ in range(count)]


def test_sort_words_by_length_sorts_ascending_against_a_random_list():
    words = _random_words(200)
    assert [len(w) for w in sort_words_by_length(words)] == sorted(len(w) for w in words)


def test_sort_words_by_length_handles_empty_list():
    assert sort_words_by_length([]) == []


def test_sort_words_by_length_handles_single_element():
    assert sort_words_by_length(["HELLO"]) == ["HELLO"]


def test_sort_words_by_length_handles_already_sorted_input():
    words = ["A", "BB", "CCC", "DDDD", "EEEEE"]
    assert [len(w) for w in sort_words_by_length(words)] == [len(w) for w in words]


def test_sort_words_by_length_handles_reverse_sorted_input():
    words = ["EEEEE", "DDDD", "CCC", "BB", "A"]
    assert [len(w) for w in sort_words_by_length(words)] == sorted(len(w) for w in words)


def test_sort_words_by_length_handles_many_duplicate_lengths():
    # Word lengths in this game only ever range over a handful of
    # distinct values (see SHORT/LONG_WORD_LENGTH_RANGE), so this is the
    # realistic case, not an edge case -- a pivot-based sort has to
    # handle "mostly duplicate lengths" correctly, not just distinct ones.
    words = ["AAAAA"] * 100 + ["BBB"] * 50 + ["CCCCCCCC"] * 30
    random.shuffle(words)
    assert [len(w) for w in sort_words_by_length(words)] == sorted(len(w) for w in words)


def test_sort_words_by_length_does_not_mutate_or_drop_elements():
    from collections import Counter

    words = ["AB", "C", "AB", "DEFG", "C", "HIJKLMNOP", "AB"]
    original = list(words)
    result = sort_words_by_length(words)

    assert words == original
    assert Counter(result) == Counter(original)
    assert len(result) == len(original)


def test_generate_words_returns_requested_count():
    words = generate_words(500, seed=1)
    assert len(words) == 500
    assert all(isinstance(w, str) for w in words)


def test_run_sort_words_by_length_returns_sorted_result_and_a_nonnegative_duration():
    words = generate_words(settings.SORT_TASK_WORD_COUNT, seed=3)
    result, elapsed = run_sort_words_by_length(words)

    assert [len(w) for w in result] == sorted(len(w) for w in words)
    assert elapsed >= 0.0


def test_run_sort_words_by_length_reports_none_when_unimplemented_via_pass(monkeypatch):
    """A stub `def sort_words_by_length(words): pass` -- implicitly returns None."""
    monkeypatch.setattr("src.algorithms.sort_task.sort_words_by_length", lambda words: None)

    result, elapsed = run_sort_words_by_length(["A", "BB", "C"])

    assert result is None
    assert elapsed >= 0.0


def test_run_sort_words_by_length_reports_none_when_it_raises(monkeypatch):
    def _raises(words):
        raise NotImplementedError

    monkeypatch.setattr("src.algorithms.sort_task.sort_words_by_length", _raises)

    result, elapsed = run_sort_words_by_length(["A", "BB", "C"])

    assert result is None
    assert elapsed == 0.0


def test_run_sort_words_by_length_reports_none_when_the_result_has_the_wrong_type(monkeypatch):
    """A buggy implementation returning e.g. lengths instead of words shouldn't crash the game."""
    monkeypatch.setattr("src.algorithms.sort_task.sort_words_by_length", lambda words: [len(w) for w in words])

    result, elapsed = run_sort_words_by_length(["A", "BB", "C"])

    assert result is None
    assert elapsed >= 0.0


def test_run_sort_words_by_length_reports_none_when_the_result_is_not_a_list(monkeypatch):
    monkeypatch.setattr("src.algorithms.sort_task.sort_words_by_length", lambda words: "not a list")

    result, elapsed = run_sort_words_by_length(["A", "BB", "C"])

    assert result is None
    assert elapsed >= 0.0
