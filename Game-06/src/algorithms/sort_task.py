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
    result = list(words)
    buffer: List[Optional[str]] = [None] * len(result)
    _merge_sort(result, buffer, 0, len(result))
    return result


def _merge_sort(items: List[str], buffer: List[Optional[str]], start: int, end: int) -> None:
    """
    Sorts items[start:end] in place, by len(). Splits by index instead of
    slicing (words[:mid] / words[mid:]) so each recursive call reuses the
    same pair of lists instead of allocating two fresh ones per level --
    the usual top-down mergesort has O(n log n) list allocations just from
    slicing; this has one buffer allocated once, in sort_words_by_length.
    """
    if end - start <= 1:
        return

    mid = (start + end) // 2
    _merge_sort(items, buffer, start, mid)
    _merge_sort(items, buffer, mid, end)
    _merge_by_length(items, buffer, start, mid, end)


def _merge_by_length(
    items: List[str], buffer: List[Optional[str]], start: int, mid: int, end: int
) -> None:
    """Merges the already-length-sorted items[start:mid] and items[mid:end], stably, via buffer."""
    i, j, k = start, mid, start

    while i < mid and j < end:
        if len(items[i]) <= len(items[j]):
            buffer[k] = items[i]
            i += 1
        else:
            buffer[k] = items[j]
            j += 1
        k += 1

    while i < mid:
        buffer[k] = items[i]
        i += 1
        k += 1

    while j < end:
        buffer[k] = items[j]
        j += 1
        k += 1

    items[start:end] = buffer[start:end]


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
