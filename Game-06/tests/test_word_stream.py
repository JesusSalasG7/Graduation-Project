"""
Tests for src/entities/word_stream.py's Faker-backed word generation.
"""
import settings
from src.entities.word_stream import WordStream


def test_next_word_is_uppercase_letters_only():
    stream = WordStream(seed=1)

    for _ in range(30):
        word = stream.next_word()
        assert word.isalpha()
        assert word == word.upper()


def test_next_word_alternates_short_and_long_length_buckets():
    stream = WordStream(seed=2)
    short_low, short_high = settings.SHORT_WORD_LENGTH_RANGE
    long_low, long_high = settings.LONG_WORD_LENGTH_RANGE

    lengths = [len(stream.next_word()) for _ in range(20)]
    buckets = [
        "short" if short_low <= n <= short_high else "long" if long_low <= n <= long_high else "other"
        for n in lengths
    ]

    assert "other" not in buckets
    # Every consecutive pair must differ -- that's what "alternates" means,
    # regardless of whether this particular seed happens to start on the
    # short or the long bucket.
    assert all(a != b for a, b in zip(buckets, buckets[1:]))


def test_next_word_never_empty():
    stream = WordStream(seed=3)
    assert all(stream.next_word() for _ in range(50))
