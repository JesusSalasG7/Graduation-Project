"""
Tests de src/logic2048.py: la lógica pura del 2048, sin pygame ni ventana.

- TestCompressAndMerge y TestBoardMove prueban el Desafío A02
  (Board._compress_and_merge). Mientras esa función siga sin implementar
  (TODO + NotImplementedError) estos tests FALLAN: es lo esperado.
- TestBoardWithoutChallenge prueba el resto del tablero, que no depende
  del desafío, así que pasa siempre.

Correr con (desde Game-02/):
    python -m unittest discover -s tests
    python -m pytest
"""
import unittest
from unittest import mock

from src.logic2048 import GRID_SIZE, WIN_VALUE, Board, MoveResult


def _board(cells):
    """Tablero con exactamente `cells` (Board() arranca con dos fichas al azar)."""
    board = Board()
    board.cells = [row[:] for row in cells]
    board.score = 0
    return board


def _shifts(shifts):
    """Desplazamientos como conjunto de tuplas, para comparar sin depender del orden."""
    return {(s.source_index, s.target_index, s.source_value, s.merged) for s in shifts}


def _movements(movements):
    return {(m.source, m.target, m.source_value, m.merged) for m in movements}


def _without_new_tile():
    """Anula la ficha al azar que agrega cada movimiento, para comparar tableros exactos."""
    return mock.patch.object(Board, "add_random_tile", return_value=None)


class TestCompressAndMerge(unittest.TestCase):
    """Desafío A02: comprimir y fusionar UNA línea ya orientada hacia el borde."""

    def _run(self, line):
        return Board._compress_and_merge(list(line))

    def _assert_line(self, line, expected_line, expected_points, expected_changed):
        result, points, changed, _ = self._run(line)
        self.assertEqual(result, expected_line)
        self.assertEqual(points, expected_points)
        self.assertIs(changed, expected_changed)

    # --- ejemplos del enunciado ---
    def test_statement_example_merge_first_pair_only(self):
        self._assert_line([2, 2, 2, 4], [4, 2, 4, 0], 4, True)

    def test_statement_example_four_equal_tiles_make_two_pairs(self):
        # Nunca [8, 0, 0, 0] ni [4, 2, 2, 0]: cada ficha se fusiona una sola vez.
        self._assert_line([2, 2, 2, 2], [4, 4, 0, 0], 8, True)

    def test_statement_example_compress_without_merge(self):
        self._assert_line([4, 0, 0, 2], [4, 2, 0, 0], 0, True)

    def test_statement_example_already_compact_line_does_not_change(self):
        self._assert_line([8, 4, 2, 0], [8, 4, 2, 0], 0, False)

    # --- compresión ---
    def test_empty_line_does_not_change(self):
        self._assert_line([0, 0, 0, 0], [0, 0, 0, 0], 0, False)

    def test_single_tile_slides_to_the_edge(self):
        self._assert_line([0, 0, 0, 2], [2, 0, 0, 0], 0, True)

    def test_single_tile_already_at_the_edge_does_not_change(self):
        self._assert_line([2, 0, 0, 0], [2, 0, 0, 0], 0, False)

    def test_compress_keeps_relative_order(self):
        self._assert_line([0, 2, 0, 4], [2, 4, 0, 0], 0, True)

    def test_full_line_without_equal_neighbors_does_not_change(self):
        self._assert_line([2, 4, 2, 4], [2, 4, 2, 4], 0, False)

    # --- fusión ---
    def test_equal_tiles_separated_by_a_gap_merge(self):
        self._assert_line([2, 0, 2, 0], [4, 0, 0, 0], 4, True)

    def test_equal_tiles_at_both_ends_merge(self):
        self._assert_line([2, 0, 0, 2], [4, 0, 0, 0], 4, True)

    def test_two_different_pairs_merge_independently(self):
        self._assert_line([2, 2, 4, 4], [4, 8, 0, 0], 12, True)

    def test_merge_result_does_not_merge_again_in_the_same_move(self):
        # 4+4 = 8 queda junto al 8 original, pero no se vuelve a fusionar.
        self._assert_line([4, 4, 8, 0], [8, 8, 0, 0], 8, True)
        self._assert_line([2, 2, 4, 0], [4, 4, 0, 0], 4, True)

    def test_three_equal_tiles_merge_the_pair_closest_to_the_edge(self):
        self._assert_line([4, 4, 4, 0], [8, 4, 0, 0], 8, True)
        self._assert_line([0, 2, 2, 2], [4, 2, 0, 0], 4, True)

    def test_different_tile_between_equal_ones_blocks_the_merge(self):
        self._assert_line([2, 4, 2, 0], [2, 4, 2, 0], 0, False)

    def test_points_are_the_sum_of_the_new_values(self):
        self._assert_line([1024, 1024, 16, 16], [2048, 32, 0, 0], 2080, True)

    # --- forma del resultado ---
    def test_returns_a_tuple_of_four_elements(self):
        outcome = self._run([2, 2, 0, 0])
        self.assertEqual(len(outcome), 4)
        result, points, changed, shifts = outcome
        self.assertIsInstance(result, list)
        self.assertIsInstance(points, int)
        self.assertIsInstance(changed, bool)
        self.assertEqual(len(shifts), 2)

    def test_does_not_mutate_the_input_line(self):
        for line in ([2, 2, 2, 4], [4, 0, 0, 2], [0, 0, 0, 0]):
            original = list(line)
            Board._compress_and_merge(line)
            self.assertEqual(line, original)

    def test_result_is_a_new_list(self):
        line = [8, 4, 2, 0]
        result, _, _, _ = Board._compress_and_merge(line)
        self.assertIsNot(result, line)

    def test_result_keeps_the_original_length(self):
        for line in ([2, 2, 2, 2], [0, 0, 0, 2], [2, 0, 2, 2, 0], [2, 2]):
            result, _, _, _ = self._run(line)
            self.assertEqual(len(result), len(line))

    def test_line_of_another_size(self):
        self._assert_line([2, 0, 2, 2, 0], [4, 2, 0, 0, 0], 4, True)

    # --- desplazamientos (para animar el movimiento) ---
    def test_shifts_of_an_empty_line_are_empty(self):
        _, _, _, shifts = self._run([0, 0, 0, 0])
        self.assertEqual(list(shifts), [])

    def test_one_shift_per_original_tile(self):
        for line, tiles in (([2, 2, 2, 4], 4), ([4, 0, 0, 2], 2), ([0, 0, 0, 2], 1), ([2, 2, 2, 2], 4)):
            _, _, _, shifts = self._run(line)
            self.assertEqual(len(shifts), tiles, f"línea {line}")

    def test_shifts_without_merge_record_source_and_target(self):
        _, _, _, shifts = self._run([4, 0, 0, 2])
        self.assertEqual(_shifts(shifts), {(0, 0, 4, False), (3, 1, 2, False)})

    def test_shifts_mark_both_tiles_of_a_merge(self):
        # Las dos fichas que se fusionan llegan a la misma celda; el valor
        # que se registra es el que traía cada una, no el fusionado.
        _, _, _, shifts = self._run([2, 2, 2, 4])
        self.assertEqual(
            _shifts(shifts),
            {(0, 0, 2, True), (1, 0, 2, True), (2, 1, 2, False), (3, 2, 4, False)},
        )

    def test_shifts_of_two_independent_merges(self):
        _, _, _, shifts = self._run([2, 2, 2, 2])
        self.assertEqual(
            _shifts(shifts),
            {(0, 0, 2, True), (1, 0, 2, True), (2, 1, 2, True), (3, 1, 2, True)},
        )

    def test_shifts_of_a_merge_across_a_gap(self):
        _, _, _, shifts = self._run([0, 2, 0, 2])
        self.assertEqual(_shifts(shifts), {(1, 0, 2, True), (3, 0, 2, True)})


class TestBoardMove(unittest.TestCase):
    """Board.move() en las 4 direcciones; depende del Desafío A02."""

    CELLS = [
        [2, 2, 0, 0],
        [0, 4, 0, 4],
        [2, 0, 0, 0],
        [0, 0, 0, 8],
    ]

    def _move(self, direction, cells=None):
        board = _board(cells or self.CELLS)
        with _without_new_tile():
            result = board.move(direction)
        return board, result

    def test_move_left(self):
        board, result = self._move("LEFT")
        self.assertTrue(result.changed)
        self.assertEqual(board.cells, [
            [4, 0, 0, 0],
            [8, 0, 0, 0],
            [2, 0, 0, 0],
            [8, 0, 0, 0],
        ])
        self.assertEqual(board.score, 12)

    def test_move_right(self):
        board, result = self._move("RIGHT")
        self.assertTrue(result.changed)
        self.assertEqual(board.cells, [
            [0, 0, 0, 4],
            [0, 0, 0, 8],
            [0, 0, 0, 2],
            [0, 0, 0, 8],
        ])
        self.assertEqual(board.score, 12)

    def test_move_up(self):
        board, result = self._move("UP")
        self.assertTrue(result.changed)
        self.assertEqual(board.cells, [
            [4, 2, 0, 4],
            [0, 4, 0, 8],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
        ])
        self.assertEqual(board.score, 4)

    def test_move_down(self):
        board, result = self._move("DOWN")
        self.assertTrue(result.changed)
        self.assertEqual(board.cells, [
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 2, 0, 4],
            [4, 4, 0, 8],
        ])
        self.assertEqual(board.score, 4)

    def test_merge_goes_towards_the_edge_of_the_move(self):
        # Con tres iguales, se fusiona el par más cercano al borde de destino.
        row = [[2, 2, 2, 0]] + [[0] * GRID_SIZE for _ in range(GRID_SIZE - 1)]
        left, _ = self._move("LEFT", row)
        right, _ = self._move("RIGHT", row)
        self.assertEqual(left.cells[0], [4, 2, 0, 0])
        self.assertEqual(right.cells[0], [0, 0, 2, 4])

    def test_movements_use_real_board_coordinates(self):
        cells = [[0] * GRID_SIZE for _ in range(GRID_SIZE)]
        cells[1] = [2, 2, 0, 4]
        _, result = self._move("RIGHT", cells)
        self.assertEqual(
            _movements(result.movements),
            {((1, 3), (1, 3), 4, False), ((1, 1), (1, 2), 2, True), ((1, 0), (1, 2), 2, True)},
        )

    def test_movements_of_a_vertical_move(self):
        cells = [[0] * GRID_SIZE for _ in range(GRID_SIZE)]
        cells[0][2] = 2
        cells[3][2] = 2
        _, result = self._move("DOWN", cells)
        self.assertEqual(
            _movements(result.movements),
            {((3, 2), (3, 2), 2, True), ((0, 2), (3, 2), 2, True)},
        )

    def test_move_that_changes_nothing_spends_no_turn(self):
        cells = [
            [2, 0, 0, 0],
            [4, 0, 0, 0],
            [2, 0, 0, 0],
            [4, 0, 0, 0],
        ]
        board = _board(cells)
        result = board.move("LEFT")
        self.assertFalse(result.changed)
        self.assertFalse(result.bumped)
        self.assertEqual(board.cells, cells)
        self.assertEqual(board.score, 0)
        self.assertIsNone(result.new_tile_position)

    def test_move_that_changes_adds_one_new_tile(self):
        board = _board(self.CELLS)
        tiles_before = sum(1 for row in self.CELLS for value in row if value)
        result = board.move("UP")
        # UP fusiona un par (2 + 2): una ficha menos, más la nueva.
        tiles_after = sum(1 for row in board.cells for value in row if value)
        self.assertEqual(tiles_after, tiles_before - 1 + 1)
        row, col = result.new_tile_position
        self.assertIn(result.new_tile_value, (2, 4))
        self.assertEqual(board.cells[row][col], result.new_tile_value)

    def test_reaching_the_win_value_sets_won(self):
        cells = [[0] * GRID_SIZE for _ in range(GRID_SIZE)]
        cells[0] = [WIN_VALUE // 2, WIN_VALUE // 2, 0, 0]
        board, _ = self._move("LEFT", cells)
        self.assertTrue(board.won)
        self.assertEqual(board.cells[0][0], WIN_VALUE)
        self.assertEqual(board.score, WIN_VALUE)

    def test_score_accumulates_across_moves(self):
        cells = [[0] * GRID_SIZE for _ in range(GRID_SIZE)]
        cells[0] = [2, 2, 4, 4]
        board = _board(cells)
        with _without_new_tile():
            board.move("LEFT")   # [4, 8, 0, 0] -> 12 puntos
            board.cells[0] = [4, 4, 8, 8]
            board.move("LEFT")   # [8, 16, 0, 0] -> 24 puntos
        self.assertEqual(board.score, 36)

    def test_last_possible_move_sets_lost(self):
        # Tras deslizar la fila de arriba, la ficha nueva solo puede caer en
        # la única celda libre (0, 3); con un 4 ahí no queda ninguna jugada.
        cells = [
            [0, 2, 8, 2],
            [4, 16, 4, 16],
            [2, 4, 16, 2],
            [4, 2, 4, 8],
        ]
        board = _board(cells)
        with mock.patch("src.logic2048.random.random", return_value=0.99):
            result = board.move("LEFT")
        self.assertTrue(result.changed)
        self.assertEqual(board.cells[0], [2, 8, 2, 4])
        self.assertTrue(board.lost)


class TestBoardWithoutChallenge(unittest.TestCase):
    """Lo que no depende del Desafío A02: pasa aunque siga sin implementar."""

    def test_new_board_starts_with_two_tiles(self):
        board = Board()
        tiles = [value for row in board.cells for value in row if value]
        self.assertEqual(len(tiles), 2)
        self.assertTrue(all(value in (2, 4) for value in tiles))
        self.assertEqual(len(board.cells), GRID_SIZE)
        self.assertTrue(all(len(row) == GRID_SIZE for row in board.cells))
        self.assertEqual(board.score, 0)
        self.assertFalse(board.won)
        self.assertFalse(board.lost)

    def test_empty_cells_lists_only_zeros(self):
        cells = [[2] * GRID_SIZE for _ in range(GRID_SIZE)]
        cells[1][2] = 0
        cells[3][0] = 0
        board = _board(cells)
        self.assertEqual(board.empty_cells(), [(1, 2), (3, 0)])

    def test_add_random_tile_fills_an_empty_cell(self):
        cells = [[2] * GRID_SIZE for _ in range(GRID_SIZE)]
        cells[2][1] = 0
        board = _board(cells)
        self.assertEqual(board.add_random_tile()[:2], (2, 1))
        self.assertIn(board.cells[2][1], (2, 4))

    def test_add_random_tile_value_follows_the_probability(self):
        board = _board([[0] * GRID_SIZE for _ in range(GRID_SIZE)])
        with mock.patch("src.logic2048.random.random", return_value=0.5):
            self.assertEqual(board.add_random_tile()[2], 2)
        with mock.patch("src.logic2048.random.random", return_value=0.95):
            self.assertEqual(board.add_random_tile()[2], 4)

    def test_add_random_tile_on_a_full_board_returns_none(self):
        cells = [[2] * GRID_SIZE for _ in range(GRID_SIZE)]
        board = _board(cells)
        self.assertIsNone(board.add_random_tile())
        self.assertEqual(board.cells, cells)

    def test_invalid_direction_raises(self):
        board = Board()
        for direction in ("left", "DIAGONAL", "", None):
            with self.assertRaises(ValueError):
                board.move(direction)

    def test_no_moves_after_winning_or_losing(self):
        for flag in ("won", "lost"):
            cells = [[0] * GRID_SIZE for _ in range(GRID_SIZE)]
            cells[0] = [2, 2, 0, 0]
            board = _board(cells)
            setattr(board, flag, True)
            result = board.move("LEFT")
            self.assertFalse(result.changed)
            self.assertEqual(board.cells, cells)

    def test_has_possible_moves_with_an_empty_cell(self):
        cells = [
            [2, 4, 2, 4],
            [4, 2, 4, 2],
            [2, 4, 2, 4],
            [4, 2, 4, 0],
        ]
        self.assertTrue(_board(cells)._has_possible_moves())

    def test_has_possible_moves_with_a_horizontal_pair(self):
        cells = [
            [2, 4, 2, 4],
            [4, 2, 4, 2],
            [2, 4, 2, 4],
            [4, 2, 8, 8],
        ]
        self.assertTrue(_board(cells)._has_possible_moves())

    def test_has_possible_moves_with_a_vertical_pair(self):
        cells = [
            [2, 4, 2, 4],
            [4, 2, 4, 2],
            [2, 4, 2, 8],
            [4, 2, 4, 8],
        ]
        self.assertTrue(_board(cells)._has_possible_moves())

    def test_no_possible_moves_on_a_full_board_without_pairs(self):
        cells = [
            [2, 4, 2, 4],
            [4, 2, 4, 2],
            [2, 4, 2, 4],
            [4, 2, 4, 2],
        ]
        self.assertFalse(_board(cells)._has_possible_moves())

    # --- comportamiento mientras el desafío no está implementado ---
    def _missing_challenge(self):
        def not_implemented(line):
            raise NotImplementedError

        return mock.patch.object(Board, "_compress_and_merge", staticmethod(not_implemented))

    def test_missing_challenge_bumps_instead_of_sliding(self):
        cells = [[0] * GRID_SIZE for _ in range(GRID_SIZE)]
        cells[0] = [0, 2, 0, 2]
        board = _board(cells)
        with self._missing_challenge():
            result = board.move("LEFT")
        self.assertIsInstance(result, MoveResult)
        self.assertTrue(result.changed)
        self.assertTrue(result.bumped)
        self.assertTrue(board.challenge_missing)
        # Ninguna ficha se movió ni se fusionó...
        self.assertEqual((board.cells[0][1], board.cells[0][3]), (2, 2))
        self.assertEqual(_movements(result.movements), {((0, 1), (0, 1), 2, False), ((0, 3), (0, 3), 2, False)})
        self.assertEqual(board.score, 0)
        # ...pero el turno se gastó: apareció una ficha nueva.
        self.assertEqual(sum(1 for row in board.cells for value in row if value), 3)

    def test_missing_challenge_also_covers_a_function_that_returns_none(self):
        board = _board([[2, 2, 0, 0]] + [[0] * GRID_SIZE for _ in range(GRID_SIZE - 1)])
        with mock.patch.object(Board, "_compress_and_merge", staticmethod(lambda line: None)):
            result = board.move("LEFT")
        self.assertTrue(result.bumped)
        self.assertTrue(board.challenge_missing)

    def test_missing_challenge_loses_when_the_board_fills_up(self):
        cells = [[2] * GRID_SIZE for _ in range(GRID_SIZE)]
        cells[3][3] = 0
        board = _board(cells)
        with self._missing_challenge():
            result = board.move("UP")
        self.assertTrue(result.bumped)
        self.assertEqual(result.new_tile_position, (3, 3))
        self.assertTrue(board.lost)


if __name__ == "__main__":
    unittest.main()
