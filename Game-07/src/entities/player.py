"""
Player: a "Tomb of the Mask" style grid slider. A direction launches it
at a constant speed; it keeps moving on its own, ignoring every other
directional input, until the next cell along that direction is a wall --
then it stops dead, exactly cell-aligned.

Deliberately has no idea a Level exists: update() takes a plain
is_wall(row, col) callable (and an optional on_enter_cell callback) so
this class can be tested -- or reused against any other grid source --
without constructing one.
"""
from typing import Callable, Optional, Tuple

Direction = Tuple[int, int]

UP: Direction = (0, -1)
DOWN: Direction = (0, 1)
LEFT: Direction = (-1, 0)
RIGHT: Direction = (1, 0)
_NONE: Direction = (0, 0)

IsWall = Callable[[int, int], bool]
# Called with the (row, col) of a cell the moment the player fully
# enters it (goal/obstacle checks, say). Returning True cuts the slide
# short right there, exactly like hitting a wall would.
OnEnterCell = Callable[[int, int], bool]


class Player:
    def __init__(self, col: int, row: int, speed_cells_per_second: float) -> None:
        # The last cell the player fully occupied -- always an exact,
        # non-wall grid cell, never a rounded approximation of a
        # fractional position (that was the bug: rounding a continuously
        # moving float flips to the next cell half a tile early, so the
        # look-ahead wall check fired too soon and the slide stopped
        # mid-tile instead of cell-aligned).
        self.col = col
        self.row = row
        # How far (0.0-1.0) the player has slid past (col, row) towards
        # the next cell in `direction`. Always 0.0 while at rest.
        self._progress: float = 0.0
        self.speed = speed_cells_per_second
        self.direction: Direction = _NONE

    @property
    def x(self) -> float:
        delta_col, _ = self.direction
        return self.col + delta_col * self._progress

    @property
    def y(self) -> float:
        _, delta_row = self.direction
        return self.row + delta_row * self._progress

    @property
    def is_moving(self) -> bool:
        return self.direction != _NONE

    def try_move(self, direction: Direction) -> None:
        """
        Launches a slide in `direction`. A no-op while already moving --
        this is the one place that rule is enforced, so PlayState can
        forward every direction press unconditionally.
        """
        if self.is_moving:
            return
        self.direction = direction

    def warp_to(self, col: int, row: int) -> None:
        """
        Instantly relocates the player (e.g. respawning after hitting an
        obstacle), cancelling any slide in progress.
        """
        self.col = col
        self.row = row
        self._progress = 0.0
        self.direction = _NONE

    def update(self, dt: float, is_wall: IsWall, on_enter_cell: Optional[OnEnterCell] = None) -> None:
        if not self.is_moving:
            return

        delta_col, delta_row = self.direction
        remaining = self.speed * dt

        while remaining > 0 and self.is_moving:
            next_col = self.col + delta_col
            next_row = self.row + delta_row

            if is_wall(next_row, next_col):
                self.direction = _NONE
                self._progress = 0.0
                break

            distance_to_next_cell = 1.0 - self._progress

            if remaining >= distance_to_next_cell:
                self.col, self.row = next_col, next_row
                self._progress = 0.0
                remaining -= distance_to_next_cell

                if on_enter_cell is not None and on_enter_cell(self.row, self.col):
                    self.direction = _NONE
                    break
            else:
                self._progress += remaining
                remaining = 0.0
