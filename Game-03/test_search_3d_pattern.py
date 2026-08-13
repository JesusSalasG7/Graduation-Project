"""
Integration test case for the A03 challenge on the Rubik's Cube.

Defines small 3D patterns and searches for them inside the cube's
3x3x3 matrix using RubikCube.search_3d_pattern (which in turn uses
src.algorithm.find_3d_pattern), printing to the console whether they
were found and at which (x, y, z) coordinates.

Has no dependency on pygame or a window: it can be run directly with:

    python test_search_3d_pattern.py
"""
from src.rubik_cube import RubikCube


def _report(title: str, result) -> None:
    print(f"\n{title}")
    if result is not None:
        x, y, z = result
        print(f"  -> FOUND at (x={x}, y={y}, z={z})")
    else:
        print("  -> NOT found")


def main() -> None:
    cube = RubikCube()

    print("Initial cube state (solved):")
    cube.print_matrix()

    # --- Case 1: a pattern that DOES exist ----------------------------
    # A real 2x2x2 block is extracted from the corner (0, 0, 0) of the
    # solved cube itself, so the pattern is guaranteed to exist and we
    # know beforehand where: exactly at (0, 0, 0).
    corner_pattern = cube.extract_block(0, 0, 0, 2, 2, 2)
    result_1 = cube.search_3d_pattern(corner_pattern)
    _report("Case 1: 2x2x2 block taken from corner (0,0,0) of the solved cube", result_1)
    assert result_1 == (0, 0, 0), "The pattern should have been found exactly where it was extracted from."

    # --- Case 2: the same pattern, after scrambling the cube ----------
    # After applying moves, the pieces change position, so that same
    # block of ids may no longer be at (0,0,0) -- it might not even
    # exist anymore as a contiguous block.
    applied_moves = cube.scramble(15)
    result_2 = cube.search_3d_pattern(corner_pattern)
    _report(
        f"Case 2: same pattern, cube scrambled with {applied_moves}",
        result_2,
    )

    # --- Case 3: an impossible pattern (an id no cubie has) -----------
    # The cube's ids range from 0 (core) to 26 (pieces), so a block
    # full of 99 can never match: this checks the algorithm's "not
    # found" path.
    impossible_pattern = [[[99, 99], [99, 99]], [[99, 99], [99, 99]]]
    result_3 = cube.search_3d_pattern(impossible_pattern)
    _report("Case 3: impossible pattern (2x2x2 block full of id=99)", result_3)
    assert result_3 is None, "A pattern with a nonexistent id should never be found."

    # --- Case 4: a large pattern, taken from a freshly reset cube -----
    # A 3x3x2 block (two full layers in Z) taken from the solved cube
    # should also be found at its original position.
    cube.reset()
    big_pattern = cube.extract_block(0, 0, 0, 3, 3, 2)
    result_4 = cube.search_3d_pattern(big_pattern)
    _report("Case 4: large 3x3x2 block taken from a solved cube", result_4)
    assert result_4 == (0, 0, 0)

    print("\nAll test cases finished successfully.")


if __name__ == "__main__":
    main()
