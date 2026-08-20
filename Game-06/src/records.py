"""
Persists every participant's run (name, score, and -- only for runs
where src/algorithms/sort_task.py's sort_task was actually implemented
-- the sort exercise's elapsed time) to a JSON file next to the
project, so it survives between runs.

Unlike Game-01/src/records.py (a straight top-scorers leaderboard this
was originally copied from), storage here is NOT capped at
MAX_ENTRIES and NOT gated behind beating the previous best -- every run
gets a saved entry regardless of score, since the sort_time each one
carries is data this project needs to collect from every participant,
not just whoever currently has the top score (see PlayState._handle_game_over,
which always attempts a save now). MAX_ENTRIES instead only bounds
leaderboard(), the top-N view CoverState renders -- load_all() itself
always returns the full history.
"""
import json
from typing import List, Optional, TypedDict

import settings

_RECORDS_PATH = settings.BASE_DIR / "records.json"

# Display-only cap for leaderboard() (e.g. CoverState's top scorers list)
# -- load_all()/_save() never trim to this, so no participant's run is
# ever discarded just because someone else scored higher.
MAX_ENTRIES = 5


class RecordEntry(TypedDict):
    name: str
    score: int
    # None whenever the run's sort_task wasn't implemented (see
    # PlayState._save_record) -- there's no elapsed time to report, and
    # storing 0.0 there would misleadingly read as "instant".
    sort_time: Optional[float]


def load_all() -> List[RecordEntry]:
    """Every saved record, best score first. Empty if none have been set yet."""
    if not _RECORDS_PATH.exists():
        return []

    try:
        with open(_RECORDS_PATH, "r", encoding="utf-8") as file:
            data = json.load(file)
        entries = [
            {
                "name": str(entry["name"]),
                "score": int(entry["score"]),
                # .get, not [...] -- entries saved before this field
                # existed have no "sort_time" key at all.
                "sort_time": float(entry["sort_time"]) if entry.get("sort_time") is not None else None,
            }
            for entry in data
        ]
    except (json.JSONDecodeError, KeyError, ValueError, OSError, TypeError):
        return []

    entries.sort(key=lambda entry: entry["score"], reverse=True)
    return entries


def leaderboard(limit: int = MAX_ENTRIES) -> List[RecordEntry]:
    """
    The top `limit` entries by score -- what CoverState actually renders.
    Unlike load_all(), this is a display view, not the full participant
    history: it's fine for this to leave weaker runs off screen since
    nothing about storage depends on it.
    """
    return load_all()[:limit]


def best_score() -> int:
    entries = load_all()
    return entries[0]["score"] if entries else 0


def qualifies(score: int) -> bool:
    """Whether `score` would earn a spot on the displayed leaderboard: strictly beats the current best."""
    return score > best_score()


def name_exists(name: str) -> bool:
    """Whether `name` already has an entry on the leaderboard (case/space-insensitive)."""
    normalized = name.strip().upper()
    return any(entry["name"].strip().upper() == normalized for entry in load_all())


def _save(entries: List[RecordEntry]) -> None:
    # No MAX_ENTRIES trim here -- every participant's run is kept, not
    # just the top scorers (see the module docstring / leaderboard()).
    entries.sort(key=lambda entry: entry["score"], reverse=True)

    with open(_RECORDS_PATH, "w", encoding="utf-8") as file:
        json.dump(entries, file)


def add(name: str, score: int, sort_time: Optional[float] = None) -> None:
    """Inserts (name, score, sort_time) -- every run is kept, see the module docstring."""
    entries = load_all()
    entries.append({"name": name, "score": score, "sort_time": sort_time})
    _save(entries)


def overwrite(name: str, score: int, sort_time: Optional[float] = None) -> None:
    """Like add(), but first drops any existing entry with the same name."""
    normalized = name.strip().upper()
    entries = [entry for entry in load_all() if entry["name"].strip().upper() != normalized]
    entries.append({"name": name, "score": score, "sort_time": sort_time})
    _save(entries)


def clear() -> None:
    """Wipes the leaderboard -- used by the main menu's "Borrar Records" option."""
    _save([])
