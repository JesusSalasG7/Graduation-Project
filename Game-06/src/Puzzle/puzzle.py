"""
Standalone launcher for the sorting-puzzle prototype (src/Puzzle/src/Board.py
and src/Puzzle/src/Tile.py). This is a throwaway dev harness kept only to try
the board mechanic in isolation; the real, integrated puzzle the game
actually plays is src/Puzzle/SortingPuzzle.py, driven by
src/states/game_states/PuzzleState.py.

It shares the single project-wide settings.py and assets/ folder, so it must
be run from the project root, e.g.:
    python -m src.Puzzle.puzzle
"""

import sys
from pathlib import Path

# Allow running this file directly (python src/Puzzle/puzzle.py) too, by
# making sure the project root is on sys.path before importing the shared
# settings module and package-qualified sources below.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import settings
from src.Puzzle.src.Board import Board

if __name__ == "__main__":
    board = Board(
        "Puzzle",
        settings.WINDOW_WIDTH,
        settings.WINDOW_HEIGHT,
        settings.VIRTUAL_WIDTH,
        settings.VIRTUAL_HEIGHT,
    )
    board.exec()
