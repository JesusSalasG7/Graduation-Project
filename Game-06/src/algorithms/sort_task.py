"""
Standalone sorting exercise layered on top of the game's own word
generation: generate_words() draws settings.SORT_TASK_WORD_COUNT real
words from WordStream; their LENGTHS are what sort_task() actually sorts
ascending (generate_word_lengths() is the same thing when only the
numbers matter, e.g. under test).

sort_task() is deliberately the one function PlayState ever calls to do
that (see PlayState._begin_sort_task) -- swap its body for any other
correct ascending sort (quicksort, merge, bubble...) and nothing
else in the game has to change, since nothing else knows or cares that
this one happens to be selection sort. It's also deliberately safe to leave
unimplemented: run_sort_task below is what PlayState actually calls, and
it treats "raises" and "returns None" (an empty `pass` body falls
through to that implicitly) the same way -- no sorted result, so
PlayState skips the loading screen entirely and drops straight into the
game, exactly as it behaved before this module existed.

That "no sorted result" case is also why sort_words_by_length is its own
function rather than something PlayState derives from sort_task's output
(e.g. by re-looking-up a word for each sorted length): it needs to be
callable ONLY once sort_task has proven itself implemented, on the exact
same words sort_task's lengths came from, so the words a run actually
falls in are the same order the loading screen just reported timing
for -- not two independent, potentially-inconsistent sorts.
"""
import time
from typing import List, Optional, Tuple

from src.entities.word_stream import WordStream


def generate_words(count: int, seed: Optional[int] = None) -> List[str]:
    """`count` freshly generated words, in generation order."""
    stream = WordStream(seed=seed)
    return [stream.next_word() for _ in range(count)]


def generate_word_lengths(count: int, seed: Optional[int] = None) -> List[int]:
    """The LENGTHS (not the words themselves) of `count` freshly generated words."""
    return [len(word) for word in generate_words(count, seed=seed)]


def sort_task(lengths: List[int]) -> List[int]:
    pass

def run_sort_task(lengths: List[int]) -> Tuple[Optional[List[int]], float]:
    """
    Times sort_task(lengths) without ever letting it take the caller
    down with it:
      - sort_task raises  -> (None, 0.0)
      - sort_task returns nothing (a stub that's just `pass`, say)
        -> (None, elapsed)
      - sort_task is for real implemented -> (sorted_list, elapsed)
    PlayState's loading screen only ever appears for that last case.
    """
    start = time.perf_counter()

    try:
        result = sort_task(lengths)
    except Exception:
        return None, 0.0

    elapsed = time.perf_counter() - start
    return result, elapsed


def sort_words_by_length(words: List[str]) -> List[str]:
    """
    Same quicksort shape as sort_task, keyed by len(word) instead of a
    bare int -- what PlayState actually feeds World as its preset word
    supply (see World.__init__ / WordStream) once sort_task has proven
    itself implemented, so the words a run falls in during play are
    visibly in the same ascending-length order the loading screen
    reported timing for, not just a number sitting apart from what's
    on screen. Always available (unlike sort_task, this one is never
    meant to be left unimplemented) -- PlayState only ever calls it
    after run_sort_task's own result confirms the exercise is "on".
    """
    if len(words) <= 1:
        return list(words)

    pivot_length = len(words[len(words) // 2])
    less = [w for w in words if len(w) < pivot_length]
    equal = [w for w in words if len(w) == pivot_length]
    greater = [w for w in words if len(w) > pivot_length]

    return sort_words_by_length(less) + equal + sort_words_by_length(greater)
