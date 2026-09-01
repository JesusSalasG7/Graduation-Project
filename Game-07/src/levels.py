"""
Level catalog for Conway's Puzzle.

Every level shares the canvas defined by settings.GRID_COLUMNS/GRID_ROWS
and only varies what's drawn inside it: walls, the target zone, enemy
patterns, and the cell budget. Levels are plain data (a Level
dataclass) built with the small rect()/at() helpers below instead of
hand-aligned ASCII art, so there's no risk of a misaligned map silently
shifting a wall or the target zone by one column.

win_type controls how src.board.Board victory is read:
    "target"  -- at least one live cell must reach the target zone.
    "eliminate" -- every enemy-seeded cell must end up dead.
"""
from dataclasses import dataclass, field
from typing import Set, Tuple

import settings

Coord = Tuple[int, int]


def rect(col0: int, row0: int, col1: int, row1: int) -> Set[Coord]:
    """Every (col, row) in the inclusive rectangle [col0, col1] x [row0, row1]."""
    return {
        (col, row)
        for col in range(col0, col1 + 1)
        for row in range(row0, row1 + 1)
    }


def block(col: int, row: int) -> Set[Coord]:
    """The 2x2 still-life block with its top-left corner at (col, row)."""
    return {(col, row), (col + 1, row), (col, row + 1), (col + 1, row + 1)}


_GLIDER_SE = {(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)}


def glider(col: int, row: int, heading: str = "se") -> Set[Coord]:
    """
    The smallest Game of Life spaceship: 5 cells that, left alone under
    B3/S23, translate themselves one cell diagonally every 4
    generations -- forever, until they hit a wall or the board edge.

    (col, row) anchors the top-left corner of its 3x3 bounding box.
    heading picks which diagonal it glides toward: "se" (default),
    "sw", "ne", or "nw", by mirroring the base south-east pattern.
    """
    mirror_col = heading in ("sw", "nw")
    mirror_row = heading in ("ne", "nw")
    return {
        (col + (2 - c if mirror_col else c), row + (2 - r if mirror_row else r))
        for c, r in _GLIDER_SE
    }


@dataclass
class Level:
    name: str
    description: str
    budget: int
    win_type: str
    walls: Set[Coord] = field(default_factory=set)
    target_zone: Set[Coord] = field(default_factory=set)
    enemy_cells: Set[Coord] = field(default_factory=set)


_COLS = settings.GRID_COLUMNS
_ROWS = settings.GRID_ROWS

LEVELS = [
    Level(
        name="Primeros Pasos",
        description="Lleva una celula viva hasta la zona objetivo.",
        budget=20,
        win_type="target",
        target_zone=rect(7, 0, 10, _ROWS - 1),
    ),
    Level(
        name="El Pasillo",
        description="Guia una reaccion a traves del pasillo hasta el objetivo.",
        budget=14,
        win_type="target",
        walls=(rect(0, 0, _COLS - 1, 4) | rect(0, 10, _COLS - 1, _ROWS - 1)),
        target_zone=rect(_COLS - 4, 5, _COLS - 1, 9),
    ),
    Level(
        name="Exterminio",
        description="Elimina el patron enemigo (bloque estable) antes de rendirte.",
        budget=10,
        win_type="eliminate",
        enemy_cells=block(_COLS // 2 - 1, _ROWS // 2 - 1),
    ),
    Level(
        name="El Planeador",
        description=(
            "Con solo 5 celulas no llegas caminando: construye un planeador "
            "para que viaje solo hasta la zona objetivo."
        ),
        budget=5,
        win_type="target",
        target_zone=rect(9, _ROWS - 3, 17, _ROWS - 1),
    ),
]
