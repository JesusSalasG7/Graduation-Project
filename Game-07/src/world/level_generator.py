"""
Procedural level generation via a cellular automaton.

LevelGenerator owns three steps, run in order by generate():

  1. Random noise seed (each cell independently a wall with some
     probability -- see settings.CA_WALL_PROBABILITY's docstring for why
     that has to sit near 50%, not the sparse 5% a cave-style automaton
     would use).
  2. The "Maze" rule (B3/S<survive_min>-<survive_max>): a wall survives
     with survive_min..survive_max wall neighbors, an empty cell is born
     as a wall with exactly birth_limit wall neighbors, applied for a
     fixed number of iterations. Out-of-bounds neighbors count as
     neither wall nor empty (simply skipped) rather than as solid rock --
     counting them as walls was tried first and made every border cell
     spuriously satisfy the birth condition on iteration 1, snowballing
     into a thick wall crust that ate the whole map from the outside in
     and left one big empty cave in the middle instead of corridors.
  3. A flood fill that finds every connected region of empty cells and
     seals every region except the largest one, so the output is
     guaranteed fully navigable from any point reachable within it.

This class only ever produces and returns the raw grid -- picking a
spawn point, retrying an unlucky seed, and everything gameplay-facing
lives in src/world/level.py, which wraps this matrix instead of
subclassing it.
"""
import random
from typing import List, Optional, Set, Tuple

EMPTY = 0
WALL = 1

Grid = List[List[int]]
Cell = Tuple[int, int]  # (row, col)


class LevelGenerator:
    def __init__(
        self,
        columns: int,
        rows: int,
        wall_probability: float,
        iterations: int,
        birth_limit: int,
        survive_min: int,
        survive_max: int,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.columns = columns
        self.rows = rows
        self.wall_probability = wall_probability
        self.iterations = iterations
        self.birth_limit = birth_limit
        self.survive_min = survive_min
        self.survive_max = survive_max
        self._rng = rng or random.Random()

        self.grid: Grid = []
        # Filled in by _enforce_connectivity -- the only region left with
        # EMPTY cells once generate() returns, and therefore the only
        # place a spawn point can legally come from.
        self.largest_region: List[Cell] = []

    def generate(self) -> Grid:
        self._seed_noise()
        for _ in range(self.iterations):
            self._step()
        self._fix_diagonal_pinches()
        self._enforce_connectivity()
        return self.grid

    def pick_spawn_cell(self) -> Cell:
        if not self.largest_region:
            raise RuntimeError("generate() must run (and find an open cell) before picking a spawn cell")
        return self._rng.choice(self.largest_region)

    def _seed_noise(self) -> None:
        self.grid = [
            [WALL if self._rng.random() < self.wall_probability else EMPTY for _ in range(self.columns)]
            for _ in range(self.rows)
        ]

    def _count_wall_neighbors(self, grid: Grid, row: int, col: int) -> int:
        count = 0
        for delta_row in (-1, 0, 1):
            for delta_col in (-1, 0, 1):
                if delta_row == 0 and delta_col == 0:
                    continue
                neighbor_row, neighbor_col = row + delta_row, col + delta_col
                if not self._in_bounds(neighbor_row, neighbor_col):
                    continue  # out-of-bounds counts as neither wall nor empty
                if grid[neighbor_row][neighbor_col] == WALL:
                    count += 1
        return count

    def _step(self) -> None:
        new_grid: Grid = [[EMPTY] * self.columns for _ in range(self.rows)]

        for row in range(self.rows):
            for col in range(self.columns):
                wall_neighbors = self._count_wall_neighbors(self.grid, row, col)

                if self.grid[row][col] == WALL:
                    survives = self.survive_min <= wall_neighbors <= self.survive_max
                    new_grid[row][col] = WALL if survives else EMPTY
                else:
                    new_grid[row][col] = WALL if wall_neighbors == self.birth_limit else EMPTY

        self.grid = new_grid

    def _fix_diagonal_pinches(self) -> None:
        """
        The CA step above counts wall neighbors across the full 8-cell
        Moore neighborhood (that's what makes B3/S<survive_min>-<survive_max>
        the real "Maze" rule), so two EMPTY cells routinely end up
        touching only at a corner, e.g.:

            . #        (. = EMPTY, # = WALL)
            # .

        On screen that reads as one continuous corridor bending through
        the corner, but the player only ever moves along the 4 cardinal
        directions, so a diagonal-only touch is actually a dead end on
        both sides -- left unfixed, the flood fill below would carve the
        maze into dozens of small disconnected pockets instead of one
        large navigable network. Knocking down one of the two blocking
        walls at each such pinch (picked at random, for variety) turns
        the corner into a real orthogonal passage while changing only a
        small fraction of the map's walls.
        """
        for row in range(self.rows - 1):
            for col in range(self.columns - 1):
                self._fix_pinch_at(row, col, corner_a=(row, col + 1), corner_b=(row + 1, col), diagonal=((row, col), (row + 1, col + 1)))
                self._fix_pinch_at(row, col, corner_a=(row, col), corner_b=(row + 1, col + 1), diagonal=((row, col + 1), (row + 1, col)))

    def _fix_pinch_at(self, row: int, col: int, corner_a: Cell, corner_b: Cell, diagonal: Tuple[Cell, Cell]) -> None:
        (diag_a_row, diag_a_col), (diag_b_row, diag_b_col) = diagonal
        if self.grid[diag_a_row][diag_a_col] != EMPTY or self.grid[diag_b_row][diag_b_col] != EMPTY:
            return

        corner_a_row, corner_a_col = corner_a
        corner_b_row, corner_b_col = corner_b
        if self.grid[corner_a_row][corner_a_col] != WALL or self.grid[corner_b_row][corner_b_col] != WALL:
            return

        if self._rng.random() < 0.5:
            self.grid[corner_a_row][corner_a_col] = EMPTY
        else:
            self.grid[corner_b_row][corner_b_col] = EMPTY

    def _enforce_connectivity(self) -> None:
        visited = [[False] * self.columns for _ in range(self.rows)]
        regions: List[List[Cell]] = []

        for row in range(self.rows):
            for col in range(self.columns):
                if self.grid[row][col] == EMPTY and not visited[row][col]:
                    regions.append(self._flood_fill(row, col, visited))

        self.largest_region = max(regions, key=len, default=[])
        largest_set: Set[Cell] = set(self.largest_region)

        for row in range(self.rows):
            for col in range(self.columns):
                if self.grid[row][col] == EMPTY and (row, col) not in largest_set:
                    self.grid[row][col] = WALL

    def _flood_fill(self, start_row: int, start_col: int, visited: List[List[bool]]) -> List[Cell]:
        # 4-directional on purpose -- the player only ever moves along
        # the cardinal directions, so a region only reachable through a
        # diagonal gap wouldn't actually be navigable in-game.
        stack: List[Cell] = [(start_row, start_col)]
        visited[start_row][start_col] = True
        region: List[Cell] = []

        while stack:
            row, col = stack.pop()
            region.append((row, col))

            for delta_row, delta_col in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                neighbor_row, neighbor_col = row + delta_row, col + delta_col
                if (
                    self._in_bounds(neighbor_row, neighbor_col)
                    and not visited[neighbor_row][neighbor_col]
                    and self.grid[neighbor_row][neighbor_col] == EMPTY
                ):
                    visited[neighbor_row][neighbor_col] = True
                    stack.append((neighbor_row, neighbor_col))

        return region

    def _in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.columns
