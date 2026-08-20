"""
Persists the TypeBeat leaderboard (name, score, and -- only for runs
where src/algorithms/sort_task.py's sort_task was actually implemented
-- the sort exercise's elapsed time) to a JSON file next to the
project, so it survives between runs.

Same shape as Game-01/src/records.py -- copied deliberately rather than
reinvented, since the leaderboard rules (top MAX_ENTRIES, strictly-beats
to qualify, case-insensitive overwrite) are project-wide conventions,
not something specific to Snake -- plus the sort_time field this game
adds on top.
"""
import json
from typing import List, Optional, TypedDict

import settings

_RECORDS_PATH = settings.BASE_DIR / "records.json"

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


def best_score() -> int:
    entries = load_all()
    return entries[0]["score"] if entries else 0


def qualifies(score: int) -> bool:
    """Whether `score` earns a spot on the leaderboard: strictly beats the current best."""
    return score > best_score()


def name_exists(name: str) -> bool:
    """Whether `name` already has an entry on the leaderboard (case/space-insensitive)."""
    normalized = name.strip().upper()
    return any(entry["name"].strip().upper() == normalized for entry in load_all())


def _save(entries: List[RecordEntry]) -> None:
    entries.sort(key=lambda entry: entry["score"], reverse=True)
    entries = entries[:MAX_ENTRIES]

    with open(_RECORDS_PATH, "w", encoding="utf-8") as file:
        json.dump(entries, file)


def add(name: str, score: int, sort_time: Optional[float] = None) -> None:
    """Inserts (name, score, sort_time), keeping only the top MAX_ENTRIES afterward."""
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
