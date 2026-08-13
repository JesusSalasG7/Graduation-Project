"""
Module with the internal logic of the Rubik's Cube, modeled as a
three-dimensional matrix of integers (3x3x3).

Each of the 27 cells of `self.matrix` holds a single integer: the id
of the physical piece occupying that position (0 for the central
core, which is not a visible piece). Applying a move carries that id
along with the piece, so the matrix always reflects "which piece is
in each position" -- the state the A03 algorithm (see
`src/algorithm.py`) needs to traverse and compare blocks.

In parallel, `self.colors` models the stickers: for each (position,
outward direction) where a piece has a visible face, it stores its
color. Unlike `self.matrix` (which only matters for the A03
challenge), `self.colors` does rotate both position and orientation
when a layer turns -- just like on a real cube -- so that moves and
scrambling look physically correct when drawing the cube
(`src/view_3d.py`).

This module has no dependency on pygame: it is pure logic, so it can
be tested and used (for instance from test_search_3d_pattern.py)
without needing a window or gale.
"""
import random
from typing import Callable, Dict, List, Optional, Tuple

from src.algorithm import find_3d_pattern

Matrix3D = List[List[List[int]]]
Color = Tuple[int, int, int]
Direction = Tuple[int, int, int]
Position = Tuple[int, int, int]

SIZE = 3
CORE_ID = 0


def _color_from_hex(hex_code: str) -> Color:
    """Converts a '#RRGGBB' color into an (r, g, b) tuple."""
    hex_code = hex_code.lstrip("#")
    return (int(hex_code[0:2], 16), int(hex_code[2:4], 16), int(hex_code[4:6], 16))


# Official colors of a standard Rubik's Cube, one per outward
# direction (+x right, -x left, +y up, -y down, +z front, -z back) --
# the same color each sticker is born with on the solved cube.
WHITE = _color_from_hex("#FFFFFF")
YELLOW = _color_from_hex("#FFD500")
RED = _color_from_hex("#B71234")
ORANGE = _color_from_hex("#FF5800")
BLUE = _color_from_hex("#0046AD")
GREEN = _color_from_hex("#009B48")

_INITIAL_COLOR_BY_DIRECTION: Dict[Direction, Color] = {
    (1, 0, 0): RED,
    (-1, 0, 0): ORANGE,
    (0, 1, 0): WHITE,
    (0, -1, 0): YELLOW,
    (0, 0, 1): GREEN,
    (0, 0, -1): BLUE,
}

_LETTER_BY_COLOR: Dict[Color, str] = {
    WHITE: "W",
    YELLOW: "Y",
    RED: "R",
    ORANGE: "O",
    BLUE: "B",
    GREEN: "G",
}

# Every classic Rubik's Cube move (standard notation) is the turn of a
# single layer: a fixed axis ('x', 'y' or 'z') and the index of that
# layer along that axis (0, 1 or 2). Names with an apostrophe (for
# instance "U'") are the same turn in the counterclockwise direction.
#
# U/D/L/R/F/B are the 6 outer layers; M/E/S are the 3 inner middle
# layers (index 1), following the same clockwise convention (seen from
# the positive side of their axis) as the outer ones: M (Middle,
# between L and R), E (Equator, between D and U) and S (Standing,
# between F and B).
_AXIS_AND_INDEX_BY_MOVE: Dict[str, Tuple[str, int]] = {
    "U": ("y", 2),  # Up: top layer
    "D": ("y", 0),  # Down: bottom layer
    "L": ("x", 0),  # Left: left layer
    "R": ("x", 2),  # Right: right layer
    "F": ("z", 2),  # Front: front layer
    "B": ("z", 0),  # Back: back layer
    "M": ("x", 1),  # Middle: inner vertical layer, between L and R
    "E": ("y", 1),  # Equator: inner horizontal layer, between D and U
    "S": ("z", 1),  # Standing: inner middle layer, between F and B
}

# "Wide" moves (notation "Uw" etc.): turn an outer layer together with
# its adjacent inner layer, as if they were a single layer 2 cells
# thick. Only makes sense for the 6 outer layers (M/E/S are already
# the inner layer).
_WIDE_LAYERS: Dict[str, Tuple[Tuple[str, int], Tuple[str, int]]] = {
    "U": (("y", 2), ("y", 1)),
    "D": (("y", 0), ("y", 1)),
    "L": (("x", 0), ("x", 1)),
    "R": (("x", 2), ("x", 1)),
    "F": (("z", 2), ("z", 1)),
    "B": (("z", 0), ("z", 1)),
}

BASIC_MOVES: Tuple[str, ...] = tuple(_AXIS_AND_INDEX_BY_MOVE.keys())
WIDE_MOVES: Tuple[str, ...] = tuple(name + "w" for name in _WIDE_LAYERS)
ALL_MOVES: Tuple[str, ...] = tuple(
    name + suffix
    for name in BASIC_MOVES + WIDE_MOVES
    for suffix in ("", "'")
)

# Same as _FACES in src/view_3d.py (same axis/index convention for
# each face, see the RubikCube class below), but with no 3D geometry
# at all: just what's needed to walk a face's 3x3 grid and find the
# position and direction of each of its stickers, for `print_colors`.
_FACES_FOR_PRINTING: Dict[str, Tuple[Direction, Callable[[int, int], Position]]] = {
    "Up": ((0, 1, 0), lambda u, v: (u, 2, v)),
    "Down": ((0, -1, 0), lambda u, v: (u, 0, v)),
    "Right": ((1, 0, 0), lambda u, v: (2, u, v)),
    "Left": ((-1, 0, 0), lambda u, v: (0, u, v)),
    "Front": ((0, 0, 1), lambda u, v: (u, v, 2)),
    "Back": ((0, 0, -1), lambda u, v: (u, v, 0)),
}


def _rotate_2d_matrix(matrix2d: List[List[int]], clockwise: bool) -> List[List[int]]:
    """
    Rotates a square 2D matrix 90 degrees (used to turn the 3x3 layer
    extracted from the cube).
    """
    size = len(matrix2d)
    result = [[0] * size for _ in range(size)]

    for i in range(size):
        for j in range(size):
            if clockwise:
                result[j][size - 1 - i] = matrix2d[i][j]
            else:
                result[size - 1 - j][i] = matrix2d[i][j]

    return result


def _rotate_pair(a: int, b: int, clockwise: bool) -> Tuple[int, int]:
    """
    Rotates a pair of coordinates centered on the origin (values -1,
    0 or 1) 90 degrees, with the same orientation `_rotate_2d_matrix`
    uses for a cell (i, j): the pair (a, b) goes to (b, -a) clockwise,
    or to (-b, a) counterclockwise. Used both to translate a
    sticker's position within the turning layer and to rotate where
    its color points to.
    """
    return (b, -a) if clockwise else (-b, a)


def _rotate_sticker(
    axis: str, clockwise: bool, position: Position, direction: Direction
) -> Tuple[Position, Direction]:
    """
    Given a sticker (a `self.matrix` position and the outward
    direction its color points to), returns its new position and
    direction after turning 90 degrees the layer perpendicular to
    `axis` that sticker belongs to.

    Two of the three coordinates (the ones perpendicular to `axis`)
    rotate the same way `_rotate_2d_matrix` rotates that layer's
    sub-matrix; the coordinate along `axis` doesn't change. The same
    applies to the direction: only its two components perpendicular
    to `axis` rotate.
    """
    x, y, z = position
    dx, dy, dz = direction

    if axis == "x":
        ny, nz = _rotate_pair(y - 1, z - 1, clockwise)
        ndy, ndz = _rotate_pair(dy, dz, clockwise)
        return (x, ny + 1, nz + 1), (dx, ndy, ndz)
    if axis == "y":
        nx, nz = _rotate_pair(x - 1, z - 1, clockwise)
        ndx, ndz = _rotate_pair(dx, dz, clockwise)
        return (nx + 1, y, nz + 1), (ndx, dy, ndz)
    # axis == "z"
    nx, ny = _rotate_pair(x - 1, y - 1, clockwise)
    ndx, ndy = _rotate_pair(dx, dy, clockwise)
    return (nx + 1, ny + 1, z), (ndx, ndy, dz)


def layers_for_move(move_name: str) -> Tuple[str, Tuple[int, ...], bool]:
    """
    Breaks down a valid move name (see `RubikCube.apply_move`) into
    `(axis, indices, clockwise)` without applying it -- for instance
    "Uw'" -> ("y", (2, 1), False). Used to know which layer(s) need to
    be animated turning *before* actually applying the move (see
    `src/states/play_state.py`), without duplicating the name parsing
    `apply_move` already does.

    :raises ValueError: if `move_name` is not a recognized move.
    """
    clockwise = not move_name.endswith("'")
    base_name = move_name[:-1] if not clockwise else move_name

    if base_name.endswith("w") and base_name[:-1] in _WIDE_LAYERS:
        pairs = _WIDE_LAYERS[base_name[:-1]]
        axis = pairs[0][0]
        return axis, tuple(index for _axis, index in pairs), clockwise

    if base_name not in _AXIS_AND_INDEX_BY_MOVE:
        raise ValueError(f"Unknown move: {move_name!r}")

    axis, index = _AXIS_AND_INDEX_BY_MOVE[base_name]
    return axis, (index,), clockwise


def inverse_move(move_name: str) -> str:
    """
    Returns the move that undoes `move_name`: every move in
    `ALL_MOVES` comes in a clockwise/counterclockwise pair that only
    differs by a trailing "'" (see `ALL_MOVES`), so undoing one is
    just toggling that apostrophe -- "R" <-> "R'", "Uw" <-> "Uw'".
    Used by the undo/redo buttons (see `src/states/play_state.py`) to
    turn a move already applied back the other way.
    """
    return move_name[:-1] if move_name.endswith("'") else move_name + "'"


class RubikCube:
    """
    Represents the state of a 3x3x3 Rubik's Cube as a three-dimensional
    matrix of integers `self.matrix[x][y][z]`, with:
        - x: axis left(0) -> right(2)
        - y: axis down(0) -> up(2)
        - z: axis back(0) -> front(2)
    """

    def __init__(self) -> None:
        self.matrix: Matrix3D = []
        self.colors: Dict[Tuple[int, int, int, Direction], Color] = {}
        self.reset()

    def reset(self) -> None:
        """Returns the cube to its solved state (every piece in its original position and color)."""
        self.matrix = [
            [[0 for _ in range(SIZE)] for _ in range(SIZE)] for _ in range(SIZE)
        ]
        self.colors = {}

        piece_id = 1
        for x in range(SIZE):
            for y in range(SIZE):
                for z in range(SIZE):
                    if (x, y, z) == (1, 1, 1):
                        self.matrix[x][y][z] = CORE_ID
                    else:
                        self.matrix[x][y][z] = piece_id
                        piece_id += 1

                    # A piece has one sticker for each axis on which it
                    # sits on the cube's boundary (1 for a face center,
                    # 2 for an edge, 3 for a corner).
                    if x == 2:
                        self.colors[(x, y, z, (1, 0, 0))] = _INITIAL_COLOR_BY_DIRECTION[(1, 0, 0)]
                    if x == 0:
                        self.colors[(x, y, z, (-1, 0, 0))] = _INITIAL_COLOR_BY_DIRECTION[(-1, 0, 0)]
                    if y == 2:
                        self.colors[(x, y, z, (0, 1, 0))] = _INITIAL_COLOR_BY_DIRECTION[(0, 1, 0)]
                    if y == 0:
                        self.colors[(x, y, z, (0, -1, 0))] = _INITIAL_COLOR_BY_DIRECTION[(0, -1, 0)]
                    if z == 2:
                        self.colors[(x, y, z, (0, 0, 1))] = _INITIAL_COLOR_BY_DIRECTION[(0, 0, 1)]
                    if z == 0:
                        self.colors[(x, y, z, (0, 0, -1))] = _INITIAL_COLOR_BY_DIRECTION[(0, 0, -1)]

        # Snapshot of the solved state, to compare against it in
        # `is_solved` regardless of how many moves were applied since.
        self._solved_matrix: Matrix3D = [
            [row[:] for row in layer] for layer in self.matrix
        ]

    def rotate_layer(self, axis: str, index: int, clockwise: bool = True) -> None:
        """
        Turns 90 degrees the layer perpendicular to `axis` located at
        `index` (0, 1 or 2).

        :param axis: 'x', 'y' or 'z' -- the axis the layer is perpendicular to.
        :param index: Which layer of that axis is turned (0, 1 or 2).
        :param clockwise: True for clockwise, False for counterclockwise (seen from the positive side of the axis).
        """
        if axis == "x":
            sub = [[self.matrix[index][y][z] for z in range(SIZE)] for y in range(SIZE)]
            rotated_sub = _rotate_2d_matrix(sub, clockwise)
            for y in range(SIZE):
                for z in range(SIZE):
                    self.matrix[index][y][z] = rotated_sub[y][z]
        elif axis == "y":
            sub = [[self.matrix[x][index][z] for z in range(SIZE)] for x in range(SIZE)]
            rotated_sub = _rotate_2d_matrix(sub, clockwise)
            for x in range(SIZE):
                for z in range(SIZE):
                    self.matrix[x][index][z] = rotated_sub[x][z]
        elif axis == "z":
            sub = [[self.matrix[x][y][index] for y in range(SIZE)] for x in range(SIZE)]
            rotated_sub = _rotate_2d_matrix(sub, clockwise)
            for x in range(SIZE):
                for y in range(SIZE):
                    self.matrix[x][y][index] = rotated_sub[x][y]
        else:
            raise ValueError(f"Invalid axis: {axis!r} (must be 'x', 'y' or 'z')")

        self._rotate_layer_colors(axis, index, clockwise)

    def _rotate_layer_colors(self, axis: str, index: int, clockwise: bool) -> None:
        """
        Counterpart of `rotate_layer` for `self.colors`: moves every
        sticker in the layer (`axis`, `index`) to its new position and
        direction, so the colors travel with the pieces -- both
        position and orientation -- just like on a real cube.
        """
        axis_index = {"x": 0, "y": 1, "z": 2}[axis]
        layer_stickers = [
            key for key in self.colors if key[axis_index] == index
        ]

        new_stickers: Dict[Tuple[int, int, int, Direction], Color] = {}
        for x, y, z, direction in layer_stickers:
            color = self.colors.pop((x, y, z, direction))
            new_position, new_direction = _rotate_sticker(
                axis, clockwise, (x, y, z), direction
            )
            new_stickers[new_position + (new_direction,)] = color

        self.colors.update(new_stickers)

    def apply_move(self, move_name: str) -> None:
        """
        Applies a move in standard Rubik's Cube notation:
            - Outer layers: "U", "D", "L", "R", "F", "B".
            - Inner layers: "M", "E", "S".
            - Wide layer (outer + its adjacent inner layer): the name
              of an outer layer followed by "w", for instance "Uw".
        Any of the names above followed by an apostrophe (for instance
        "U'" or "Uw'") applies the same turn counterclockwise instead
        of clockwise.
        """
        axis, indices, clockwise = layers_for_move(move_name)
        for index in indices:
            self.rotate_layer(axis, index, clockwise)

    def scramble(self, move_count: int = 20) -> List[str]:
        """Applies a random sequence of moves and returns it (useful for displaying it on screen)."""
        applied_moves = [
            random.choice(ALL_MOVES) for _ in range(move_count)
        ]
        for move in applied_moves:
            self.apply_move(move)
        return applied_moves

    def is_solved(self) -> bool:
        return self.matrix == self._solved_matrix

    def extract_block(
        self, origin_x: int, origin_y: int, origin_z: int, depth: int, rows: int, columns: int
    ) -> Matrix3D:
        """
        Returns a copy of the 3D block of `self.matrix` that starts at
        (origin_x, origin_y, origin_z) with the given dimensions.
        Useful for building, from the cube itself, a test pattern
        known to exist (see test_search_3d_pattern.py).
        """
        return [
            [
                [self.matrix[origin_x + i][origin_y + j][origin_z + k] for k in range(columns)]
                for j in range(rows)
            ]
            for i in range(depth)
        ]

    def search_3d_pattern(
        self, target_submatrix: Matrix3D
    ) -> Optional[Tuple[int, int, int]]:
        """
        A03 challenge applied to the cube: searches for
        `target_submatrix` (a smaller 3D block, for instance 2x2x2)
        inside the cube's current state (`self.matrix`, the larger
        3x3x3 matrix), sliding it across every valid position and
        comparing, at each one, the whole block element by element
        (brute force -- see the exact, commented implementation in
        `src/algorithm.py::find_3d_pattern`).

        :param target_submatrix: The 3D block of piece ids to be located inside the cube.
        :returns: The (x, y, z) position where the match starts inside the cube, or None if it was not found.
        """
        result = find_3d_pattern(self.matrix, target_submatrix)
        return result["position"] if result["found"] else None

    def print_matrix(self) -> None:
        """Prints the cube to the console, one layer (y value) at a time, from bottom to top."""
        for y in range(SIZE):
            print(f"-- Layer y={y} --")
            for x in range(SIZE):
                row = [self.matrix[x][y][z] for z in range(SIZE)]
                print("  " + " ".join(f"{value:2d}" for value in row))

    def print_colors(self) -> None:
        """
        Prints to the console the 3x3 grid of each of the 6 faces
        (`self.colors`), as color letters: W=White, Y=Yellow, R=Red,
        O=Orange, B=Blue, G=Green.
        """
        for name, (direction, index_fn) in _FACES_FOR_PRINTING.items():
            print(f"-- {name} --")
            for v in reversed(range(SIZE)):
                row = []
                for u in range(SIZE):
                    x, y, z = index_fn(u, v)
                    row.append(_LETTER_BY_COLOR[self.colors[(x, y, z, direction)]])
                print("  " + " ".join(row))
