"""
Pure grid-logic model of the snake: its segments, its direction, and
how it grows. Contains no rendering or pygame code so it can be tested
and reasoned about independently of how it is drawn.
"""
from typing import List, Tuple

from src.direction import Direction

Cell = Tuple[int, int]


class Snake:
    def __init__(
        self, start_cell: Cell, direction: Direction, initial_length: int = 3
    ) -> None:
        self.direction = direction
        self.pending_direction = direction
        self.grow_pending = 0

        head_x, head_y = start_cell
        self.segments: List[Cell] = [
            (head_x - i * direction.dx, head_y - i * direction.dy)
            for i in range(initial_length)
        ]

    @property
    def head(self) -> Cell:
        return self.segments[0]

    @property
    def tail(self) -> Cell:
        return self.segments[-1]

    def set_direction(self, new_direction: Direction) -> None:
        """
        Queue a direction change, ignoring it if it would reverse the
        snake onto itself. Validated against the last *committed*
        direction (not the queued one) so two direction changes queued
        within the same tick can't combine into an illegal reversal.
        """
        if new_direction is self.direction.opposite:
            return

        self.pending_direction = new_direction

    def grow(self, amount: int = 1) -> None:
        self.grow_pending += amount

    @property
    def next_head(self) -> Cell:
        """The cell `move()` would land the head on, without committing to it."""
        head_x, head_y = self.head
        direction = self.pending_direction
        return (head_x + direction.dx, head_y + direction.dy)

    def would_collide_with_self(self, next_cell: Cell) -> bool:
        """
        Whether landing on next_cell would hit the snake's own body.
        Mirrors collides_with_self's post-move check (the tail cell
        doesn't count when the snake isn't growing, since it will have
        vacated that cell by the time the head arrives).
        """
        body = self.segments if self.grow_pending > 0 else self.segments[:-1]
        return next_cell in body

    def move(self) -> None:
        self.direction = self.pending_direction
        head_x, head_y = self.head
        new_head = (head_x + self.direction.dx, head_y + self.direction.dy)
        self.segments.insert(0, new_head)

        if self.grow_pending > 0:
            self.grow_pending -= 1
        else:
            self.segments.pop()
