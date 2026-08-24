"""
Tests for src/algorithms/word_length_variety.py's group_in_ascending_blocks
-- the presentation filter PlayState runs a length-sorted preset word
batch through so it plays out as fixed-size blocks (shortest length
first) instead of one long same-length run per length.
"""
from collections import Counter

from src.algorithms.sort_task import generate_words
from src.algorithms.word_length_variety import group_in_ascending_blocks


def test_group_in_ascending_blocks_produces_five_then_five_pattern():
    sorted_words = ["ABC"] * 12 + ["ABCD"] * 12 + ["ABCDEFG"] * 3
    result = group_in_ascending_blocks(sorted_words, block_size=5)

    lengths = [len(w) for w in result]
    assert lengths == [
        3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 7, 7, 7, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 3, 3, 4, 4,
    ]


def test_group_in_ascending_blocks_keeps_every_word_exactly_once():
    sorted_words = ["ABC"] * 12 + ["ABCD"] * 7 + ["ABCDEFG"] * 3
    result = group_in_ascending_blocks(sorted_words, block_size=5)

    assert Counter(result) == Counter(sorted_words)
    assert len(result) == len(sorted_words)


def test_group_in_ascending_blocks_preserves_relative_order_within_a_length():
    sorted_words = ["AAA", "BBB", "CCC", "DDDD", "EEEE", "FFFF"]
    result = group_in_ascending_blocks(sorted_words, block_size=2)

    threes = [w for w in result if len(w) == 3]
    fours = [w for w in result if len(w) == 4]
    assert threes == ["AAA", "BBB", "CCC"]
    assert fours == ["DDDD", "EEEE", "FFFF"]


def test_group_in_ascending_blocks_handles_empty_list():
    assert group_in_ascending_blocks([], block_size=5) == []


def test_group_in_ascending_blocks_handles_single_length_group():
    sorted_words = ["AB"] * 11
    result = group_in_ascending_blocks(sorted_words, block_size=5)
    assert result == sorted_words


def test_group_in_ascending_blocks_handles_fewer_words_than_block_size():
    sorted_words = ["AB", "CD", "EFG"]
    assert group_in_ascending_blocks(sorted_words, block_size=5) == sorted_words


def test_group_in_ascending_blocks_on_a_real_generated_batch_stays_lossless():
    words = generate_words(500)
    # Independent of the sort_words_by_length exercise (see
    # src/algorithms/sort_task.py) -- this file only exercises
    # group_in_ascending_blocks itself, so it supplies its own
    # known-correct sort rather than depending on that exercise being
    # solved.
    sorted_words = sorted(words, key=len)
    result = group_in_ascending_blocks(sorted_words, block_size=5)

    assert Counter(result) == Counter(sorted_words)
    assert len(result) == len(sorted_words)
