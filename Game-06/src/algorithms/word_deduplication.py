"""
Another presentation filter, separate from the sorting exercise and from
word_length_variety.py's run-breaking (see that module's docstring) --
Faker's providers only have so many distinct values to draw from (twelve
month names, a finite city/name list...), so a batch of
settings.SORT_TASK_WORD_COUNT generated words routinely comes back with
the same word appearing dozens of times ("MAYO" showed up 34 times out
of 500 in one real run). Fine for sort_task's own numbers-only exercise,
but repetitive -- and a little strange -- to actually type the same word
over and over during play.
"""
from typing import List


def deduplicate_words(words: List[str]) -> List[str]:
    """
    `words` with every repeat after the first occurrence dropped,
    otherwise preserving order -- not a re-sort, just a filter, so
    callers that sort or group afterward (see sort_words_by_length) see
    the same relative ordering they would have without this.
    """
    seen = set()
    unique_words = []

    for word in words:
        if word not in seen:
            seen.add(word)
            unique_words.append(word)

    return unique_words
