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
    """
    Exact implementation of the A03 challenge: searches for
    `pattern_matrix` inside `big_matrix` by brute force.

    Step by step:
        1. Compute the dimensions of both matrices.
        2. If the pattern does not fit inside the big matrix along any
           axis, there is nothing to search for: return "not found".
        3. Walk through EVERY starting position (origin_x, origin_y,
           origin_z) where the pattern, placed there, still lands
           completely inside the big matrix -- this is "sliding the
           smaller matrix across all valid positions of the larger
           one".
        4. At each candidate position, do a "full element-by-element
           comparison" (see `_block_matches`) to check for an exact
           match of the whole three-dimensional block.
        5. As soon as a candidate position matches completely, that
           match is declared found and the search stops.
        6. If every candidate position is exhausted with no complete
           match, declare "not found".

    :param big_matrix: The large 3D matrix (for instance, the 3x3x3 state of the Rubik's Cube).
    :param pattern_matrix: The smaller 3D block being searched for inside `big_matrix` (for instance, a 2x2x2 block).
    :returns: A dictionary with:
        - 'found': True if some position was found where the pattern matches completely.
        - 'position': the (x, y, z) tuple of that position, or None if it was not found.
    """
    # Step 1: dimensions of both matrices.
    big_depth = len(big_matrix)
    big_rows = len(big_matrix[0]) if big_depth else 0
    big_columns = len(big_matrix[0][0]) if big_rows else 0

    pattern_depth = len(pattern_matrix)
    pattern_rows = len(pattern_matrix[0]) if pattern_depth else 0
    pattern_columns = len(pattern_matrix[0][0]) if pattern_rows else 0

    # Step 2: if the pattern doesn't fit, there's nothing to search for.
    if (
        pattern_depth > big_depth
        or pattern_rows > big_rows
        or pattern_columns > big_columns
    ):
        return {"found": False, "position": None}

    # Step 3: walk through every valid candidate position.
    for origin_x in range(big_depth - pattern_depth + 1):
        for origin_y in range(big_rows - pattern_rows + 1):
            for origin_z in range(big_columns - pattern_columns + 1):
                # Step 4: full element-by-element comparison.
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
                    # Step 5: exact match of the whole block.
                    return {
                        "found": True,
                        "position": (origin_x, origin_y, origin_z),
                    }
                # If _block_matches returned False, this candidate was
                # already abandoned (at the first mismatched element)
                # and the loop simply continues with the next position.

    # Step 6: every candidate position was tried, none matched.
    return {"found": False, "position": None}


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
