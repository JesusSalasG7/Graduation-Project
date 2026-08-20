"""
Pure grid-free model of one falling letter: which character it is, when
it should spawn/reach the hit zone, and what happened to it. Contains no
rendering or pygame code -- src/rendering/note.py turns a letter's own
fall speed into an actual y coordinate once it starts; this class only
ever deals in seconds.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class FallingLetter:
    char: str
    index_in_word: int
    word_length: int

    # Which of the highway's LANE_COUNT lanes this letter falls down --
    # assigned once, at construction, by World's LaneManager (see
    # src/entities/lane_manager.py), not derived from index_in_word.
    lane: Optional[int] = None

    # None until World actually starts this letter falling (see
    # World._activate_letter) -- only one letter per word is ever
    # active/falling at a time (the game is strictly letter-by-letter),
    # so a letter can sit unstarted for a while after the previous one
    # resolves, waiting for its turn.
    spawn_time: Optional[float] = None
    hit_time: Optional[float] = None
    # World's current effective_travel_time at the moment this letter
    # was activated -- this is what src/rendering/note.py reads to set
    # that particular note's fall speed.
    travel_time: Optional[float] = None

    started: bool = False
    resolved: bool = False
    judgement: Optional[str] = None

    @property
    def is_pending(self) -> bool:
        """Whether this is the one letter currently falling and hittable."""
        return self.started and not self.resolved
