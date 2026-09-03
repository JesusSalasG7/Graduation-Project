"""
Tests for next_generation(): Conway's Game of Life (rule B3/S23) as a
pure function, independent of Board and pygame.

Run with: python -m unittest discover -s tests
"""
import unittest

from src.board import next_generation


def _matrix(rows):
    """Turn ["#..", ".#.", ...] into a bool matrix ('#' = alive)."""
    return [[ch == "#" for ch in row] for row in rows]


def _cells_to_matrix(cells, columns, rows):
    matrix = [[False] * columns for _ in range(rows)]
    for col, row in cells:
        matrix[row][col] = True
    return matrix


def _matrix_to_cells(matrix):
    return {
        (col, row)
        for row, line in enumerate(matrix)
        for col, alive in enumerate(line)
        if alive
    }


class TestNextGeneration(unittest.TestCase):
    def test_lone_cell_dies_of_underpopulation(self):
        matrix = _matrix(["...", ".#.", "..."])
        result = next_generation(matrix)
        self.assertEqual(result, _matrix(["...", "...", "..."]))

    def test_overcrowded_cell_dies(self):
        # Center is alive with 4 diagonal neighbors alive -> overpopulation.
        matrix = _matrix(["#.#", ".#.", "#.#"])
        result = next_generation(matrix)
        self.assertFalse(result[1][1])

    def test_dead_cell_is_born_with_three_neighbors(self):
        matrix = _matrix(["###", "...", "..."])
        result = next_generation(matrix)
        self.assertTrue(result[1][1])

    def test_dead_cell_stays_dead_with_two_neighbors(self):
        matrix = _matrix(["##.", "...", "..."])
        result = next_generation(matrix)
        self.assertFalse(result[1][1])

    def test_block_still_life_is_stable(self):
        matrix = _matrix([
            "....",
            ".##.",
            ".##.",
            "....",
        ])
        result = next_generation(matrix)
        self.assertEqual(result, matrix)

    def test_blinker_oscillates_with_period_two(self):
        vertical = _matrix([
            ".....",
            "..#..",
            "..#..",
            "..#..",
            ".....",
        ])
        horizontal = _matrix([
            ".....",
            ".....",
            ".###.",
            ".....",
            ".....",
        ])
        after_one = next_generation(vertical)
        self.assertEqual(after_one, horizontal)

        after_two = next_generation(after_one)
        self.assertEqual(after_two, vertical)

    def test_no_wraparound_across_the_border(self):
        # Row 1, col 0 has exactly 2 real neighbors alive (above and below
        # it). A cell at (2, 1) is alive too, but it is two columns away --
        # a correct, non-toroidal board must NOT treat it as adjacent to
        # (0, 1) by wrapping column -1 back to the last column.
        matrix = _matrix([
            "#..",
            "..#",
            "#..",
        ])
        result = next_generation(matrix)
        self.assertFalse(result[1][0])

    def test_blocked_cells_never_come_alive(self):
        matrix = _matrix(["###", "...", "..."])
        result = next_generation(matrix, blocked={(1, 1)})
        self.assertFalse(result[1][1])

    def test_input_matrix_is_not_mutated(self):
        matrix = _matrix(["###", "...", "..."])
        snapshot = [row[:] for row in matrix]
        next_generation(matrix)
        self.assertEqual(matrix, snapshot)

    def test_glider_translates_diagonally_after_one_period(self):
        # The smallest Game of Life spaceship: after 4 generations it is
        # back to its original shape, shifted by (+1, +1).
        columns, rows = 10, 10
        start = {(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)}
        matrix = _cells_to_matrix(start, columns, rows)

        for _ in range(4):
            matrix = next_generation(matrix)

        shifted = {(col + 1, row + 1) for col, row in start}
        self.assertEqual(_matrix_to_cells(matrix), shifted)


if __name__ == "__main__":
    unittest.main()
