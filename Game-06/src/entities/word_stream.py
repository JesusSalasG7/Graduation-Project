"""
Endless supply of target words, built on `faker` instead of a fixed word
list so the game never runs out or repeats a noticeably small pool.

Pulls from several unrelated Faker providers (first names, cities,
lorem words, jobs...) each call, split evenly between the es_ES and
en_US locales (see _providers -- each provider method appears once per
locale, so a plain random.choice over the combined list lands on either
language with equal odds every single word) so the game reads as
genuinely bilingual rather than "mostly Spanish with the occasional
English word slipping in", and alternates between a short-length and a
long-length target every call so the fall mechanics constantly have to
cope with both instead of drifting towards whatever length Faker
happens to favor.

Pure Python, no pygame -- consumed by src/world.py, which itself stays
pygame-free (see its module docstring).
"""
import random
import re
import unicodedata
from typing import Callable, List, Optional, Sequence, Tuple

from faker import Faker

import settings

# Several providers (job, color_name, country, company, street_name...)
# return a multi-word phrase, not a single word -- "Ingeniero
# electricista", "Amarillo dorado oscuro". Concatenating every word in
# the phrase produced unreadable mashups, so this instead splits the
# phrase into letter-only tokens and _pick_word_token below chooses one
# real word out of it.
_WORD_TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
_MIN_TOKEN_LENGTH = 2


def _strip_accents(text: str) -> str:
    """
    "producción" -> "produccion", "Tanzanía" -> "Tanzania", "Ibañez" ->
    "Ibanez". The game only binds plain a-z keys (see settings.py), so
    Spanish diacritics/eñes are transliterated down to their closest
    plain-ASCII letter via Unicode's own decomposition rather than
    simply deleted -- deleting outright (a naive [^A-Za-z] filter) would
    corrupt the word instead ("producción" -> "produccin").
    """
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _pick_word_token(phrase: str) -> Optional[str]:
    """The longest letters-only token in `phrase` -- see _WORD_TOKEN_RE."""
    tokens = [t for t in _WORD_TOKEN_RE.findall(phrase) if len(t) >= _MIN_TOKEN_LENGTH]
    return max(tokens, key=len) if tokens else None


class WordStream:
    def __init__(self, seed: Optional[int] = None, preset_words: Optional[Sequence[str]] = None) -> None:
        """
        `preset_words`, if given, is drained in order (one per
        next_word() call) before this ever generates anything of its
        own -- see src/algorithms/sort_task.py's sort_words_by_length,
        the one real caller: PlayState feeds a length-sorted batch in
        here so the words a run actually falls in the ascending order
        its own loading screen just claimed to have sorted, rather than
        that sort only ever being visible as a number on that one
        screen. Once exhausted (or if it was never given at all), this
        falls back to the normal endless Faker-backed generation below,
        exactly as every WordStream behaved before preset_words existed.
        """
        self._faker_es = Faker("es_ES")
        self._faker_en = Faker("en_US")

        if seed is not None:
            self._faker_es.seed_instance(seed)
            self._faker_en.seed_instance(seed)
            random.seed(seed)

        # Deliberately unrelated providers -- names, places, lorem
        # words, job titles, calendar words -- so consecutive target
        # words don't all read like the same category, one set per
        # locale so a target is equally likely to land in either
        # language (see the module docstring).
        self._providers: List[Callable[[], str]] = [
            self._faker_es.word,
            self._faker_es.first_name,
            self._faker_es.last_name,
            self._faker_es.city,
            self._faker_es.country,
            self._faker_es.color_name,
            self._faker_es.job,
            self._faker_es.company,
            self._faker_es.street_name,
            self._faker_es.month_name,
            self._faker_es.day_of_week,
            self._faker_en.word,
            self._faker_en.first_name,
            self._faker_en.last_name,
            self._faker_en.city,
            self._faker_en.country,
            self._faker_en.color_name,
            self._faker_en.job,
            self._faker_en.company,
            self._faker_en.street_name,
            self._faker_en.month_name,
            self._faker_en.day_of_week,
        ]

        self._next_is_short = random.random() < 0.5

        self._preset_words: List[str] = list(preset_words) if preset_words else []
        self._preset_index = 0

    def next_word(self) -> str:
        """
        The next preset word if any are left (see __init__), otherwise
        the next generated one, alternating short/long each call (see
        settings.SHORT_WORD_LENGTH_RANGE / LONG_WORD_LENGTH_RANGE) --
        that alternation is untouched by preset words being drained
        first, so it picks up exactly where a fresh WordStream would
        once the preset runs out. Always returns a non-empty, upper-case,
        letters-only string.
        """
        if self._preset_index < len(self._preset_words):
            word = self._preset_words[self._preset_index]
            self._preset_index += 1
            return word

        length_range = (
            settings.SHORT_WORD_LENGTH_RANGE
            if self._next_is_short
            else settings.LONG_WORD_LENGTH_RANGE
        )
        self._next_is_short = not self._next_is_short

        return self._generate_in_range(length_range)

    def _generate_in_range(self, length_range: Tuple[int, int]) -> str:
        low, high = length_range
        target_mid = (low + high) / 2
        best_candidate: Optional[str] = None

        for _ in range(settings.MAX_WORD_GENERATION_ATTEMPTS):
            provider = random.choice(self._providers)
            token = _pick_word_token(provider())

            if token is None:
                continue

            candidate = _strip_accents(token).upper()

            if low <= len(candidate) <= high:
                return candidate

            # Every provider call this pass landed outside the range --
            # keep whichever came closest so next_word() can still
            # return *something* playable instead of ever raising.
            if best_candidate is None or abs(len(candidate) - target_mid) < abs(
                len(best_candidate) - target_mid
            ):
                best_candidate = candidate

        return _fit_to_range(best_candidate or "PALABRA", length_range)


def _fit_to_range(word: str, length_range: Tuple[int, int]) -> str:
    low, high = length_range

    if len(word) > high:
        return word[:high]

    if len(word) < low:
        # Only reachable if every attempt across every provider came up
        # short of `low` letters -- pad by repeating the word's own
        # letters rather than inventing filler the player never
        # actually generated.
        repeats = (low // max(1, len(word))) + 1
        return (word * repeats)[:low]

    return word
