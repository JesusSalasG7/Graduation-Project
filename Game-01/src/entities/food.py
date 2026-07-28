"""
Pure grid-logic model of the food: where the apple sits on the grid and
how it picks a new free cell. Contains no rendering or pygame code.
"""
import random
from typing import Iterable, List, Optional, Sequence, Tuple

Cell = Tuple[int, int]


class Apple:
    def __init__(self, position: Cell, value: int = 1) -> None:
        self.position = position
        # Nutritional/growth value. Always 1 in classic mode (matching the
        # historical grow(1)/score+=1 behavior); randomized from
        # settings.CHALLENGE_APPLE_VALUES in challenge mode -- see
        # FoodField.spawn_one's value_choices parameter.
        self.value = value
        # Countdown in seconds until this apple auto-expires, or None to
        # sit there until eaten. Only set (by World, after spawning) for
        # apples that land outside the active filter range in challenge
        # mode -- see World._spawn_apple/_update_apple_timers.
        self.expires_in: Optional[float] = None


class FoodField:
    def __init__(self, grid_cols: int, grid_rows: int) -> None:
        self.grid_cols = grid_cols
        self.grid_rows = grid_rows
        self.apples: List[Apple] = []

    def _free_cells(self, occupied_cells: Iterable[Cell]) -> List[Cell]:
        occupied = set(occupied_cells)
        return [
            (x, y)
            for x in range(self.grid_cols)
            for y in range(self.grid_rows)
            if (x, y) not in occupied
        ]

    def spawn_one(
        self, occupied_cells: Iterable[Cell], value_choices: Optional[Sequence[int]] = None
    ) -> Optional[Apple]:
        """
        `value_choices`, when given (challenge mode), picks the new apple's
        value at random from it; omitted (classic mode), the apple keeps
        Apple's default value of 1. Returns the spawned Apple (or None if
        the grid is full) so callers can attach extra state to it -- e.g.
        World arming an expiry timer on an out-of-range apple.
        """
        free_cells = self._free_cells(occupied_cells)

        if not free_cells:
            return None

        cell = random.choice(free_cells)
        value = random.choice(value_choices) if value_choices else 1
        apple = Apple(cell, value=value)
        self.apples.append(apple)
        return apple

    def apple_at(self, cell: Cell) -> Optional[Apple]:
        return next((apple for apple in self.apples if apple.position == cell), None)

    def remove(self, apple: Apple) -> None:
        self.apples.remove(apple)
