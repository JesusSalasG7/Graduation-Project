"""
Caso de prueba integrado del Desafío A05 (ver README.md y
src/algorithm.py). No necesita pygame ni una ventana -- src/algorithm.py
no lo importa -- pero si prueba la conexión real con el tablero
(src/board/board.py, Board.resolve_runs), así que se inicializa pygame
sin display para poder construir Tile/Board.

Correr con:
    .venv/bin/python tests/test_find_repeated.py
"""

import sys
from pathlib import Path

# Permite correrlo directo (python tests/<archivo>.py): agrega la raíz del juego al path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402

pygame.init()

from src.algorithm import find_repeated
from src.board.board import Board, MatchRun
from src.board.tile import Tile, TileKind


def _check(label: str, got, expected) -> None:
    status = "OK" if got == expected else "FALLO"
    print(f"[{status}] {label}: obtuve {got!r}, esperaba {expected!r}")


def test_algorithm() -> None:
    print("-- find_repeated (lógica pura) --")
    _check(
        "matriz 2x3/1x3 con repetidos entre filas",
        find_repeated([[1, 2, 2, 3], [3, 1, 4]]),
        [2, 3, 1],
    )
    _check(
        "una fila totalmente repetida (se reporta una sola vez)",
        find_repeated([[5, 5, 5, 5]]),
        [5],
    )
    _check("matriz vacía", find_repeated([]), [])
    _check(
        "sin ningún repetido",
        find_repeated([[9, 1, 4], [2, 7]]),
        [],
    )


def _catalysis_row_board(row_kinds) -> Board:
    # Un tablero 6x6 relleno de Agua, con la fila 0 forzada a los
    # kinds que le pasemos -- aislado de lo que pase en el resto del
    # tablero (le damos a resolve_runs solo el MatchRun de la fila 0).
    board = Board.__new__(Board)
    board.x, board.y = 0, 0
    board.tiles = [
        [Tile(i, j, TileKind.WATER) for j in range(6)] for i in range(6)
    ]
    for j, kind in enumerate(row_kinds):
        board.tiles[0][j].kind = kind
    return board


def test_board_integration() -> None:
    print("\n-- Board.resolve_runs (Desafío A05 conectado a una Catálisis) --")

    # Fila con Match-4 de Fuego + dos elementos distintos más, cada uno
    # una sola vez -> ningún elemento se repite (resonancia = 0).
    board = _catalysis_row_board(
        [TileKind.FIRE, TileKind.FIRE, TileKind.FIRE, TileKind.FIRE, TileKind.EARTH, TileKind.ICE]
    )
    run = MatchRun(TileKind.FIRE, [board.tiles[0][j] for j in range(4)], "h", 0)
    _, catalysis, cleared, resonance = board.resolve_runs([run])
    _check("Catálisis mixta -> se dispara", catalysis, True)
    _check("Catálisis mixta -> fichas limpiadas (fila completa)", cleared, 6)
    _check("Catálisis mixta (Fuego repite, Tierra/Hielo no) -> resonancia", resonance, 1)

    # Fila con dos pares que se repiten (Fuego x4, Agua x2) -> 2
    # elementos que resuenan en la misma línea.
    board = _catalysis_row_board(
        [TileKind.FIRE, TileKind.FIRE, TileKind.FIRE, TileKind.FIRE, TileKind.WATER, TileKind.WATER]
    )
    run = MatchRun(TileKind.FIRE, [board.tiles[0][j] for j in range(4)], "h", 0)
    _, catalysis, cleared, resonance = board.resolve_runs([run])
    _check("Catálisis con dos pares -> resonancia", resonance, 2)

    # Fila homogénea (Match-4 de Agua, resto también Agua) -> un solo
    # elemento, y se repite -> resonancia 1.
    board = _catalysis_row_board([TileKind.WATER] * 6)
    run = MatchRun(TileKind.WATER, [board.tiles[0][j] for j in range(4)], "h", 0)
    _, catalysis, cleared, resonance = board.resolve_runs([run])
    _check("Catálisis homogénea -> resonancia", resonance, 1)

    # Match-3 común (sin Catálisis) -> no hay bonus de resonancia.
    board = _catalysis_row_board([TileKind.WATER] * 6)
    run = MatchRun(TileKind.WATER, [board.tiles[0][j] for j in range(3)], "h", 0)
    _, catalysis, cleared, resonance = board.resolve_runs([run])
    _check("Match-3 sin Catálisis -> no dispara", catalysis, False)
    _check("Match-3 sin Catálisis -> resonancia en 0", resonance, 0)


if __name__ == "__main__":
    test_algorithm()
    test_board_integration()
