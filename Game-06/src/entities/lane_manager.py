"""
Non-sequential lane assignment for TypeBeat's 4-lane highway: instead of
a letter's lane being a flat function of its position in the word,
LaneManager.next_lane() walks a small hand-alternation Markov chain
(see _sample) filtered through two hard constraints (see _is_allowed),
so consecutive notes read as a real 4-key chart -- constantly crossing
between hands -- rather than a mechanical left-to-right sweep.

Pure Python, no pygame -- owned by src/world.py, which stays pygame-free
itself (see its module docstring).
"""
import random
from typing import List, Optional

import settings

_MAX_SAMPLE_ATTEMPTS = 30


def _hand_of(lane: int) -> str:
    return "left" if lane in settings.LEFT_HAND_LANES else "right"


# The only two patterns _is_allowed rejects a full LANE_COUNT-long
# window for: a straight ascending or descending staircase across every
# lane in order.
_STAIRCASE_PATTERNS = (
    tuple(range(settings.LANE_COUNT)),
    tuple(reversed(range(settings.LANE_COUNT))),
)


class LaneManager:
    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)
        self._history: List[int] = []

    def next_lane(self) -> int:
        """
        The next lane a falling letter should use. Samples a candidate
        weighted towards switching hands (see _sample), rejecting one
        that would violate _is_allowed (a 3rd same-lane repeat, or
        completing a straight staircase across every lane) and
        resampling instead. With only LANE_COUNT=4 lanes and two narrow
        rules, a valid candidate is always found well within
        _MAX_SAMPLE_ATTEMPTS.
        """
        for _ in range(_MAX_SAMPLE_ATTEMPTS):
            candidate = self._sample()
            if self._is_allowed(candidate):
                self._history.append(candidate)
                return candidate

        # Unreachable in practice at LANE_COUNT=4 -- a plain scan so
        # next_lane() can never raise even if it somehow were.
        for candidate in range(settings.LANE_COUNT):
            if self._is_allowed(candidate):
                self._history.append(candidate)
                return candidate

        candidate = self._rng.randrange(settings.LANE_COUNT)
        self._history.append(candidate)
        return candidate

    def _sample(self) -> int:
        """
        Uniform for the very first lane of a run (no history to weigh
        against yet); afterwards, a Markov-chain-style draw where every
        lane on the OTHER hand from the current one is weighted
        LANE_SWITCH_HAND_WEIGHT and every lane on the SAME hand
        (including itself) is weighted LANE_SAME_HAND_WEIGHT -- biasing
        constantly towards alternating hands without ever fully
        forbidding a same-hand follow-up.
        """
        if not self._history:
            return self._rng.randrange(settings.LANE_COUNT)

        current_hand = _hand_of(self._history[-1])
        weights = [
            settings.LANE_SWITCH_HAND_WEIGHT
            if _hand_of(lane) != current_hand
            else settings.LANE_SAME_HAND_WEIGHT
            for lane in range(settings.LANE_COUNT)
        ]
        return self._rng.choices(range(settings.LANE_COUNT), weights=weights, k=1)[0]

    def _is_allowed(self, candidate: int) -> bool:
        history = self._history

        streak = history[-settings.LANE_MAX_SAME_LANE_STREAK :]
        if len(streak) == settings.LANE_MAX_SAME_LANE_STREAK and all(lane == candidate for lane in streak):
            return False

        if len(history) >= settings.LANE_COUNT - 1:
            window = tuple(history[-(settings.LANE_COUNT - 1) :]) + (candidate,)
            if window in _STAIRCASE_PATTERNS:
                return False

        return True
