"""
Standalone sorting exercise layered on top of the game's own word
generation: generate_words() draws settings.SORT_TASK_WORD_COUNT real
words from WordStream, and sort_words_by_length() is what actually
sorts them ascending by len(word).

sort_words_by_length() is deliberately the one function PlayState ever
calls to do that (see PlayState._begin_sort_task) -- swap its body for
any other correct ascending-by-length sort (quicksort, heapsort,
bubble...) and nothing else in the game has to change, since nothing
else knows or cares that this one happens to be mergesort. It's also
deliberately safe
to leave unimplemented: run_sort_words_by_length below is what PlayState
actually calls, and it treats "raises", "returns None" (an empty `pass`
body falls through to that implicitly), and "returns something that
isn't a list of words" all the same way -- no sorted result, so
PlayState skips the loading screen entirely, but still plays the same
already-generated word batch, just in generation order instead of
sorted/blocked (see PlayState._begin_sort_task).

sort_words_by_length works directly on the words PlayState is about to
hand World as its preset word supply (see World.__init__ / WordStream),
not on their lengths, so the order a run's words actually fall in is
never a separate computation from what the loading screen just reported
timing for -- there's only ever one sort, over the one batch.
"""
import time
from typing import List, Optional, Tuple

from src.entities.word_stream import WordStream


def generate_words(count: int, seed: Optional[int] = None) -> List[str]:
    """`count` freshly generated words, in generation order."""
    stream = WordStream(seed=seed)
    return [stream.next_word() for _ in range(count)]


def sort_words_by_length(words: List[str]) -> List[str]:
    """Mergesort, keyed by len(word) instead of the word itself."""
    if len(words) <= 1:
        return list(words)

    mid = len(words) // 2
    left = sort_words_by_length(words[:mid])
    right = sort_words_by_length(words[mid:])

    return _merge_by_length(left, right)


def _merge_by_length(left: List[str], right: List[str]) -> List[str]:
    """Merges two already-length-sorted lists into one, stably."""
    merged = []
    i = j = 0

    while i < len(left) and j < len(right):
        if len(left[i]) <= len(right[j]):
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1

    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged


def run_sort_words_by_length(words: List[str]) -> Tuple[Optional[List[str]], float]:
    """
    Times sort_words_by_length(words) without ever letting it take the
    caller down with it:
      - sort_words_by_length raises
        -> (None, 0.0)
      - sort_words_by_length returns nothing (a stub that's just `pass`,
        say), or returns something that isn't a list of strings
        -> (None, elapsed)
      - sort_words_by_length is for real implemented
        -> (sorted_words, elapsed)
    PlayState's loading screen -- and the sorted/blocked preset word
    order -- only ever appear for that last case; every other case still
    plays the run with the same word batch as preset (see
    PlayState._begin_sort_task), just not sorted or blocked.
    """
    start = time.perf_counter()

    try:
        result = sort_words_by_length(words)
    except Exception:
        return None, 0.0

    elapsed = time.perf_counter() - start

    if not isinstance(result, list) or not all(isinstance(word, str) for word in result):
        return None, elapsed

    return result, elapsed
