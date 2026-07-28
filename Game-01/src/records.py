"""
Persists the Snake leaderboard (name plus score for each qualifying run)
to a JSON file next to the project, so it survives between runs.
"""
import json
from typing import List, TypedDict

import settings

_RECORDS_PATH = settings.BASE_DIR / "records.json"

# How many entries the leaderboard keeps. Chosen to fit comfortably in the
# menu screen's leaderboard panel (see MenuState._render_leaderboard).
MAX_ENTRIES = 5


class RecordEntry(TypedDict):
    name: str
    score: int


def load_all() -> List[RecordEntry]:
    """Every saved record, best score first. Empty if none have been set yet."""
    if not _RECORDS_PATH.exists():
        return []

    try:
        with open(_RECORDS_PATH, "r", encoding="utf-8") as file:
            data = json.load(file)
        entries = [{"name": str(entry["name"]), "score": int(entry["score"])} for entry in data]
    except (json.JSONDecodeError, KeyError, ValueError, OSError, TypeError):
        return []

    entries.sort(key=lambda entry: entry["score"], reverse=True)
    return entries


def best_score() -> int:
    entries = load_all()
    return entries[0]["score"] if entries else 0


def qualifies(score: int) -> bool:
    """
    Whether `score` earns a spot on the leaderboard: strictly beats the
    current best (or there is no record at all yet). Ties don't count --
    matching the "el mejor record" wording, only an outright new best
    gets a name attached and saved.
    """
    return score > best_score()


def add(name: str, score: int) -> None:
    """
    Inserts (name, score), keeping only the top MAX_ENTRIES afterward.
    Since add() is only ever called after qualifies() confirms a new
    best (see PlayState), this doubles as a capped history of the runs
    that broke the record over time.
    """
    entries = load_all()
    entries.append({"name": name, "score": score})
    entries.sort(key=lambda entry: entry["score"], reverse=True)
    entries = entries[:MAX_ENTRIES]

    with open(_RECORDS_PATH, "w", encoding="utf-8") as file:
        json.dump(entries, file)
