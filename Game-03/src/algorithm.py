"""
Algorithm A03 — Search for a pattern inside a 3D matrix.

Problem statement (as originally given):
    "Search for a three-dimensional matrix of integers inside a larger
    three-dimensional matrix, sliding the smaller matrix across all
    valid positions of the larger one. At each candidate position,
    perform a full element-by-element comparison to check for an exact
    match of the whole three-dimensional block, moving on to the next
    candidate position as soon as a mismatched element is found."

    Key Concept: Traversal of a 3D matrix.
    Comprehension focus: Pattern recognition.

This module is intentionally independent of pygame and gale: it is
pure logic over nested lists of integers, so it can be read, tested
and graded in isolation from the graphics side
(src/rubik_cube.py uses it to implement
RubikCube.search_3d_pattern, and src/states/play_state.py uses it to
animate the search over the cube).
"""
from typing import Dict, List, Optional, Tuple

Matrix3D = List[List[List[int]]]


def _block_matches(
    big_matrix: Matrix3D,
    pattern_matrix: Matrix3D,
    origin_x: int,
    origin_y: int,
    origin_z: int,
    pattern_depth: int,
    pattern_rows: int,
    pattern_columns: int,
) -> bool:
    """
    Compares, element by element, the block of `big_matrix` that
    starts at (origin_x, origin_y, origin_z) against the whole
    `pattern_matrix`.

    As soon as a mismatched element shows up, the comparison stops and
    False is returned right away -- this is exactly the "moving on to
    the next candidate position as soon as a mismatched element is
    found" from the problem statement: there is no point comparing the
    rest of the block once this position is already known to be
    invalid.

    :param big_matrix: The large 3D matrix being searched.
    :param pattern_matrix: The 3D block being searched for.
    :param origin_x, origin_y, origin_z: Coordinates where the candidate block starts inside `big_matrix`.
    :param pattern_depth, pattern_rows, pattern_columns: Dimensions of `pattern_matrix`.
    :returns: True if all `pattern_depth * pattern_rows * pattern_columns` cells match exactly; False as soon as the first mismatch is found.
    """
    for i in range(pattern_depth):
        for j in range(pattern_rows):
            for k in range(pattern_columns):
                big_value = big_matrix[origin_x + i][origin_y + j][origin_z + k]
                pattern_value = pattern_matrix[i][j][k]

                if big_value != pattern_value:
                    # A mismatched element: this candidate position is
                    # abandoned without comparing the rest of the block.
                    return False

    # Every cell of the block was compared and none of them differed.
    return True


def find_3d_pattern(
    big_matrix: Matrix3D, pattern_matrix: Matrix3D
) -> Dict[str, object]:
    # TODO: slide pattern_matrix across every valid position of
    # big_matrix (see _block_matches for the element-by-element check),
    # stopping at the first full match. Return
    # {"found": bool, "position": (x, y, z) | None}.
    raise NotImplementedError("Implement the 3D pattern search (A03)")


def find_all_matches(
    big_matrix: Matrix3D, pattern_matrix: Matrix3D
) -> List[Tuple[int, int, int]]:
    """
    Variant of `find_3d_pattern` that does not stop at the first
    match: it still walks through every candidate position and
    returns the full list of positions where the block matches
    completely (possibly an empty list). Offered as an extra utility;
    the A03 challenge itself only asks for declaring a single match,
    which is what `find_3d_pattern` does.
    """
    big_depth = len(big_matrix)
    big_rows = len(big_matrix[0]) if big_depth else 0
    big_columns = len(big_matrix[0][0]) if big_rows else 0

    pattern_depth = len(pattern_matrix)
    pattern_rows = len(pattern_matrix[0]) if pattern_depth else 0
    pattern_columns = len(pattern_matrix[0][0]) if pattern_rows else 0

    matches: List[Tuple[int, int, int]] = []

    if (
        pattern_depth > big_depth
        or pattern_rows > big_rows
        or pattern_columns > big_columns
    ):
        return matches

    for origin_x in range(big_depth - pattern_depth + 1):
        for origin_y in range(big_rows - pattern_rows + 1):
            for origin_z in range(big_columns - pattern_columns + 1):
                if _block_matches(
                    big_matrix,
                    pattern_matrix,
                    origin_x,
                    origin_y,
                    origin_z,
                    pattern_depth,
                    pattern_rows,
                    pattern_columns,
                ):
                    matches.append((origin_x, origin_y, origin_z))

    return matches
