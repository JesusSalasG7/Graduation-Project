"""
Board: the puzzle's logic grid.

A 2D matrix of booleans, completely independent of screen coordinates
(the renderer is the only thing that knows about pixels) that applies
Conway's Game of Life rule B3/S23 through a double buffer -- step()
computes the next generation into a fresh matrix and swaps it in, so a
cell's neighbor count is never read while it is being written.

Walls block a cell from ever holding life (they are skipped on both
placement and birth). The target zone and enemy cells are plain
coordinate sets layered on top of the same logic grid: they don't
change how the automaton runs, only how victory is evaluated.
"""
from typing import List, Set, Tuple

Coord = Tuple[int, int]  # (col, row)

_NEIGHBOR_OFFSETS: Tuple[Coord, ...] = (
    (-1, -1), (0, -1), (1, -1),
    (-1, 0),            (1, 0),
    (-1, 1),  (0, 1),   (1, 1),
)


def _empty_matrix(columns: int, rows: int) -> List[List[bool]]:
    return [[False] * columns for _ in range(rows)]


def next_generation(
    matrix: List[List[bool]], blocked: Set[Coord] = frozenset()
) -> List[List[bool]]:
    """
    Pure implementation of Conway's Game of Life, rule B3/S23.

    Given the current generation as a rows x columns matrix of alive
    flags, returns the *next* generation as a brand-new matrix -- the
    input is never mutated, so this can be called on any matrix (not
    just a live Board) to inspect or test how a pattern evolves.

    A cell survives with 2 or 3 live neighbors, and a dead cell is born
    with exactly 3. `blocked` names coordinates (walls) that can never
    hold life, whichever the rule would otherwise say -- passing none
    turns this into the unmodified, classic Game of Life.
    """
    rows = len(matrix)
    columns = len(matrix[0]) if rows else 0
    result = _empty_matrix(columns, rows)

    for row in range(rows):
        for col in range(columns):
            if (col, row) in blocked:
                continue

            neighbors = 0
            for dc, dr in _NEIGHBOR_OFFSETS:
                nc, nr = col + dc, row + dr
                if 0 <= nc < columns and 0 <= nr < rows and matrix[nr][nc]:
                    neighbors += 1

            result[row][col] = neighbors == 3 or (matrix[row][col] and neighbors == 2)

    return result


class Board:
    def __init__(
        self,
        columns: int,
        rows: int,
        walls: Set[Coord],
        target_zone: Set[Coord],
        enemy_cells: Set[Coord],
        budget: int,
    ) -> None:
        self.columns = columns
        self.rows = rows
        self.walls: Set[Coord] = set(walls)
        self.target_zone: Set[Coord] = set(target_zone)

        self._front: List[List[bool]] = _empty_matrix(columns, rows)
        self._back: List[List[bool]] = _empty_matrix(columns, rows)

        self.enemy_cells: Set[Coord] = set(enemy_cells)
        self.player_cells: Set[Coord] = set()

        self.budget_total = budget
        self.budget_remaining = budget
        self.generation = 0

        for col, row in self.enemy_cells:
            self._front[row][col] = True

    def in_bounds(self, col: int, row: int) -> bool:
        return 0 <= col < self.columns and 0 <= row < self.rows

    def is_wall(self, col: int, row: int) -> bool:
        return (col, row) in self.walls

    def is_alive(self, col: int, row: int) -> bool:
        return self._front[row][col]

    def alive_cells(self):
        for row in range(self.rows):
            for col in range(self.columns):
                if self._front[row][col]:
                    yield (col, row)

    def toggle_cell(self, col: int, row: int) -> bool:
        """
        Place or remove a player-owned cell at (col, row). Only cells the
        player placed can be removed this way -- enemy cells and walls
        are untouched -- and only while the budget allows it.

        :returns: True if the grid actually changed.
        """
        if not self.in_bounds(col, row) or self.is_wall(col, row):
            return False

        if (col, row) in self.player_cells:
            self.player_cells.discard((col, row))
            self._front[row][col] = False
            self.budget_remaining += 1
            return True

        if self._front[row][col] or self.budget_remaining <= 0:
            return False

        self.player_cells.add((col, row))
        self._front[row][col] = True
        self.budget_remaining -= 1
        return True

    def clear_player_cells(self) -> None:
        """Remove every player-placed cell and refund the budget."""
        for col, row in self.player_cells:
            self._front[row][col] = False
        self.player_cells.clear()
        self.budget_remaining = self.budget_total

    def step(self) -> int:
        """
        Advance one generation by delegating to next_generation().

        :returns: number of cells born this generation (used by the
        achievements system to detect a chain reaction).
        """
        self._back = next_generation(self._front, self.walls)

        births = sum(
            1
            for row in range(self.rows)
            for col in range(self.columns)
            if self._back[row][col] and not self._front[row][col]
        )

        self._front, self._back = self._back, self._front
        self.generation += 1
        return births

    def reached_target(self) -> bool:
        return any(self._front[row][col] for col, row in self.target_zone)

    def enemies_eliminated(self) -> bool:
        return self.generation > 0 and not any(
            self._front[row][col] for col, row in self.enemy_cells
        )
