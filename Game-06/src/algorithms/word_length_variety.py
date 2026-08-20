"""
A presentation filter, separate from the sorting exercise itself (see
src/algorithms/sort_task.py): sort_words_by_length hands PlayState a
word list sorted strictly ascending by length. Left as-is, that means
however many words share the shortest length all come first, in one
uninterrupted block, before the next length even starts -- with only a
handful of distinct lengths in play (settings.SHORT_WORD_LENGTH_RANGE /
LONG_WORD_LENGTH_RANGE) that block can run into the dozens.

group_in_ascending_blocks reshapes that into fixed-size chunks instead:
settings.WORD_LENGTH_BLOCK_SIZE words of the shortest length, then that
many of the next length up, and so on through every length that exists,
looping back to the shortest length again for whatever's left over --
still strictly ascending within each lap, just broken into a steady
rhythm of same-size blocks rather than one long run per length. Every
word that went in comes back out exactly once, and words sharing a
length keep their original relative order (stable) -- this only ever
reorders BETWEEN lengths, never within one.
"""
from typing import List


def group_in_ascending_blocks(sorted_words: List[str], block_size: int) -> List[str]:
    if not sorted_words:
        return []

    # Length-sorted input means same-length words are already
    # contiguous -- grouping them is just splitting on where the length
    # changes, one pass, no re-sorting needed. Since the input is
    # ascending, `groups` itself is already in ascending-length order.
    groups: List[List[str]] = []
    for word in sorted_words:
        if groups and len(groups[-1][-1]) == len(word):
            groups[-1].append(word)
        else:
            groups.append([word])

    cursors = [0] * len(groups)
    result: List[str] = []
    remaining = len(sorted_words)

    while remaining > 0:
        for index, group in enumerate(groups):
            if cursors[index] >= len(group):
                continue

            chunk = group[cursors[index] : cursors[index] + block_size]
            result.extend(chunk)
            cursors[index] += len(chunk)
            remaining -= len(chunk)

    return result
