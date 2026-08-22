"""
Caso de prueba integrado del Desafio A05 (ver GUIA_A05_remove_duplicates.md
y src/algorithm.py). No necesita pygame ni una ventana -- src/algorithm.py
no lo importa -- pero si prueba la conexion real con el tablero
(src/board/board.py, Board.resolve_runs), asi que se inicializa pygame
sin display para poder construir Tile/Board.

Correr con:
    .venv/bin/python test_remove_duplicates.py
"""

import pygame

pygame.init()

from src.algorithm import remove_duplicates
from src.board.board import Board, MatchRun
from src.board.tile import Tile, TileKind


def _check(label: str, got, expected) -> None:
    status = "OK" if got == expected else "FALLO"
    print(f"[{status}] {label}: obtuve {got!r}, esperaba {expected!r}")


def test_algorithm() -> None:
    print("-- remove_duplicates (logica pura) --")
    _check(
        "matriz 2x3/1x3 con repetidos entre filas",
        remove_duplicates([[1, 2, 2, 3], [3, 1, 4]]),
        [1, 2, 3, 4],
    )
    _check(
        "una fila totalmente repetida",
        remove_duplicates([[5, 5, 5, 5]]),
        [5],
    )
    _check("matriz vacia", remove_duplicates([]), [])
    _check(
        "sin ningun duplicado (se conserva el orden)",
        remove_duplicates([[9, 1, 4], [2, 7]]),
        [9, 1, 4, 2, 7],
    )


def _catalysis_row_board(row_kinds) -> Board:
    # Un tablero 6x6 relleno de Agua, con la fila 0 forzada a los
    # kinds que le pasemos -- aislado de lo que pase en el resto del
    # tablero (le damos a resolve_runs solo el MatchRun de la fila 0).
    board = Board.__new__(Board)
    board.x, board.y = 0, 0
    board.tiles = [
        [Tile(i, j, TileKind.AGUA) for j in range(6)] for i in range(6)
    ]
    for j, kind in enumerate(row_kinds):
        board.tiles[0][j].kind = kind
    return board


def test_board_integration() -> None:
    print("\n-- Board.resolve_runs (Desafio A05 conectado a una Catalisis) --")

    # Fila con Match-4 de Fuego + dos elementos distintos mas -> 3
    # elementos unicos en la linea completa.
    board = _catalysis_row_board(
        [TileKind.FUEGO, TileKind.FUEGO, TileKind.FUEGO, TileKind.FUEGO, TileKind.TIERRA, TileKind.HIELO]
    )
    run = MatchRun(TileKind.FUEGO, [board.tiles[0][j] for j in range(4)], "h", 0)
    _, catalysis, cleared, diversity = board.resolve_runs([run])
    _check("Catalisis mixta -> se dispara", catalysis, True)
    _check("Catalisis mixta -> fichas limpiadas (fila completa)", cleared, 6)
    _check("Catalisis mixta -> elementos distintos", diversity, 3)

    # Fila homogenea (Match-4 de Agua, resto tambien Agua) -> un solo
    # elemento distinto en toda la linea.
    board = _catalysis_row_board([TileKind.AGUA] * 6)
    run = MatchRun(TileKind.AGUA, [board.tiles[0][j] for j in range(4)], "h", 0)
    _, catalysis, cleared, diversity = board.resolve_runs([run])
    _check("Catalisis homogenea -> elementos distintos", diversity, 1)

    # Match-3 comun (sin Catalisis) -> no hay bonus de diversidad.
    board = _catalysis_row_board([TileKind.AGUA] * 6)
    run = MatchRun(TileKind.AGUA, [board.tiles[0][j] for j in range(3)], "h", 0)
    _, catalysis, cleared, diversity = board.resolve_runs([run])
    _check("Match-3 sin Catalisis -> no dispara", catalysis, False)
    _check("Match-3 sin Catalisis -> diversidad en 0", diversity, 0)


if __name__ == "__main__":
    test_algorithm()
    test_board_integration()
