"""
Tests for src/algorithms/sort_task.py -- the standalone "sort 500 word
lengths" exercise PlayState runs (see PlayState._begin_sort_task) before
every run starts.
"""
import random

import settings
from src.algorithms.sort_task import generate_word_lengths, run_sort_task, sort_task


def test_sort_task_sorts_ascending_against_a_random_list():
    values = [random.randint(1, 50) for _ in range(200)]
    assert sort_task(values) == sorted(values)


def test_sort_task_handles_empty_list():
    assert sort_task([]) == []


def test_sort_task_handles_single_element():
    assert sort_task([7]) == [7]


def test_sort_task_handles_already_sorted_input():
    values = list(range(50))
    assert sort_task(values) == values


def test_sort_task_handles_reverse_sorted_input():
    values = list(range(50, 0, -1))
    assert sort_task(values) == sorted(values)


def test_sort_task_handles_many_duplicates():
    # Word lengths in this game only ever range over a handful of
    # distinct values (see SHORT/LONG_WORD_LENGTH_RANGE), so this is the
    # realistic case, not an edge case -- a pivot-based sort has to
    # handle "mostly duplicates" correctly, not just distinct values.
    values = [5] * 100 + [3] * 50 + [8] * 30
    random.shuffle(values)
    assert sort_task(values) == sorted(values)


def test_sort_task_does_not_mutate_or_drop_elements():
    values = [4, 1, 4, 2, 1, 9, 4]
    result = sort_task(values)
    assert sorted(result) == sorted(values)
    assert len(result) == len(values)


def test_generate_word_lengths_returns_requested_count():
    lengths = generate_word_lengths(500, seed=1)
    assert len(lengths) == 500
    assert all(isinstance(n, int) for n in lengths)


def test_generate_word_lengths_stays_within_configured_word_length_ranges():
    short_low, short_high = settings.SHORT_WORD_LENGTH_RANGE
    long_low, long_high = settings.LONG_WORD_LENGTH_RANGE
    lengths = generate_word_lengths(100, seed=2)

    assert all(
        (short_low <= n <= short_high) or (long_low <= n <= long_high) for n in lengths
    )


def test_run_sort_task_returns_sorted_result_and_a_nonnegative_duration():
    lengths = generate_word_lengths(settings.SORT_TASK_WORD_COUNT, seed=3)
    result, elapsed = run_sort_task(lengths)

    assert result == sorted(lengths)
    assert elapsed >= 0.0


def test_run_sort_task_reports_none_when_sort_task_is_unimplemented_via_pass(monkeypatch):
    """A stub `def sort_task(lengths): pass` -- implicitly returns None."""
    monkeypatch.setattr("src.algorithms.sort_task.sort_task", lambda lengths: None)

    result, elapsed = run_sort_task([3, 1, 2])

    assert result is None
    assert elapsed >= 0.0


def test_run_sort_task_reports_none_when_sort_task_raises(monkeypatch):
    def _raises(lengths):
        raise NotImplementedError

    monkeypatch.setattr("src.algorithms.sort_task.sort_task", _raises)

    result, elapsed = run_sort_task([3, 1, 2])

    assert result is None
    assert elapsed == 0.0
