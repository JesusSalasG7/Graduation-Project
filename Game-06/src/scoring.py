"""
Precision judgement: turns "how far off in time was this key press from
the letter's ideal hit_time" into one of four categories, plus the
points/combo-multiplier math built on top of it.

Pure functions/constants only, no pygame -- src/world.py is the only
caller, and it stays pygame-free itself (see its module docstring), so
this has to as well.
"""
from typing import Optional

import settings

PERFECT = "perfect"
GOOD = "good"
OK = "ok"
MISS = "miss"

# Ordered widest-relevant-window last: classify_judgement checks them in
# this order and returns the first (tightest) one the distance fits in.
_WINDOWS = (
    (settings.PERFECT_WINDOW_SECONDS, PERFECT),
    (settings.GOOD_WINDOW_SECONDS, GOOD),
    (settings.OK_WINDOW_SECONDS, OK),
)


def classify_judgement(distance_seconds: float) -> Optional[str]:
    """
    Maps a time distance (always >= 0; how far the key press landed from
    the letter's hit_time) to a judgement category, or None if it falls
    outside every window -- meaning the press doesn't concern this
    letter at all and should be ignored rather than scored (see
    World.handle_key). MISS is never returned here: it is only ever
    assigned by World.update() when a letter's window closes with no
    press landing in it.
    """
    for window, judgement in _WINDOWS:
        if distance_seconds <= window:
            return judgement

    return None


def points_for(judgement: str) -> int:
    return settings.JUDGEMENT_POINTS[judgement]


def combo_multiplier(combo: int) -> float:
    """
    1.0x with no streak, rising by COMBO_MULTIPLIER_STEP for every
    COMBO_MULTIPLIER_STEP_SIZE consecutive non-miss hits, capped at
    COMBO_MULTIPLIER_MAX -- the longer the streak survives, the more
    each further hit is worth.
    """
    tiers = combo // settings.COMBO_MULTIPLIER_STEP_SIZE
    return min(
        settings.COMBO_MULTIPLIER_MAX, 1.0 + tiers * settings.COMBO_MULTIPLIER_STEP
    )


def score_for_hit(judgement: str, combo_before_hit: int) -> int:
    """
    Points a single non-miss hit is worth, combo multiplier included.
    `combo_before_hit` is the streak length *before* this hit is added
    to it (i.e. World should call this before incrementing combo), so a
    hit that starts tier N+1 is still scored at tier N's multiplier --
    the bump takes effect on the *next* hit, same as a real streak
    counter reading "9 in a row" the instant before the 10th lands.
    """
    return round(points_for(judgement) * combo_multiplier(combo_before_hit))
