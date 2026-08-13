"""
Sanity checks on the word bank PlayState draws rounds from: big enough,
no repeats, an actual mix of stable/altered words, all uppercase.
"""
from src.signal_check import is_stable_signal
from src.states.play_state import TOTAL_ROUNDS, WORD_POOL


def test_pool_has_no_duplicates():
    assert len(WORD_POOL) == len(set(WORD_POOL))


def test_pool_is_big_enough_for_one_match():
    assert len(WORD_POOL) >= TOTAL_ROUNDS


def test_pool_mixes_stable_and_altered_words():
    stable = [word for word in WORD_POOL if is_stable_signal(word)]
    altered = [word for word in WORD_POOL if not is_stable_signal(word)]
    # Both sides need to be comfortably larger than a single match's
    # share, or a random draw could end up skewed to one side almost
    # every time.
    assert len(stable) >= TOTAL_ROUNDS // 2
    assert len(altered) >= TOTAL_ROUNDS // 2


def test_pool_words_are_uppercase():
    # PlayState renders words as-is (no .upper() call) -- a lowercase
    # word here would break "TRANSMISIÓN RECIBIDA: x" styling and,
    # since is_stable_signal is case-sensitive, likely its classification.
    assert all(word == word.upper() for word in WORD_POOL)
