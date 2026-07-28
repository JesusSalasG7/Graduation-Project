"""
Grid direction used by the snake's movement logic and by the renderer
to pick/rotate the correct sprite for each segment.
"""
from enum import Enum


class Direction(Enum):
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)

    @property
    def dx(self) -> int:
        return self.value[0]

    @property
    def dy(self) -> int:
        return self.value[1]

    @property
    def opposite(self) -> "Direction":
        return _OPPOSITES[self]

    @staticmethod
    def from_vector(dx: int, dy: int) -> "Direction":
        return _BY_VECTOR[(dx, dy)]


_OPPOSITES = {
    Direction.UP: Direction.DOWN,
    Direction.DOWN: Direction.UP,
    Direction.LEFT: Direction.RIGHT,
    Direction.RIGHT: Direction.LEFT,
}

_BY_VECTOR = {direction.value: direction for direction in Direction}
