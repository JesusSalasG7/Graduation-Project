"""
logic2048.py

Lógica pura del juego 2048 (sin ninguna dependencia de Pygame ni de Gale),
para que sea trivial de probar de forma aislada. La clase Board
mantiene la matriz 4x4, la puntuación y las banderas de victoria/derrota.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

GRID_SIZE = 4
PROBABILITY_TILE_2 = 0.9  # 90% de probabilidad de '2', 10% de '4'.
WIN_VALUE = 2048

VALID_DIRECTIONS = ("LEFT", "RIGHT", "UP", "DOWN")


@dataclass
class _LineShift:
    """
    Desplazamiento de UNA ficha dentro de una única línea (fila o columna
    ya orientada), en coordenadas relativas a esa línea (0..GRID_SIZE-1).
    Es un detalle interno de `_compress_and_merge`; `_process_rows`/
    `_process_columns` lo traducen a coordenadas (fila, columna) reales
    del tablero para construir un `TileMovement` público.
    """

    source_index: int
    target_index: int
    source_value: int
    merged: bool  # True si esta ficha terminó fusionándose con otra en destino


@dataclass
class TileMovement:
    """
    Describe, para la capa de presentación, el viaje de UNA ficha que ya
    existía en el tablero antes del movimiento: desde dónde partió y a
    dónde llegó (en coordenadas (fila, columna) reales), con qué valor
    viajaba y si su destino es el resultado de una fusión (dos fichas
    del mismo valor convergiendo en la misma celda). Con esta lista la
    interfaz puede animar el deslizamiento sin tener que adivinar nada.
    """

    source: Tuple[int, int]
    target: Tuple[int, int]
    source_value: int
    merged: bool


@dataclass
class MoveResult:
    """Resultado completo de un `Board.move(...)`, listo para animar."""

    changed: bool
    movements: List[TileMovement] = field(default_factory=list)
    new_tile_position: Optional[Tuple[int, int]] = None
    new_tile_value: Optional[int] = None


class Board:
    """Estado completo de una partida de 2048."""

    def __init__(self) -> None:
        self.cells: List[List[int]] = [[0] * GRID_SIZE for _ in range(GRID_SIZE)]
        self.score: int = 0
        self.won: bool = False
        self.lost: bool = False
        # Toda partida arranca con dos fichas.
        self.add_random_tile()
        self.add_random_tile()

    # ------------------------------------------------------------------
    # Generación de fichas
    # ------------------------------------------------------------------
    def empty_cells(self) -> List[Tuple[int, int]]:
        return [
            (row, col)
            for row in range(GRID_SIZE)
            for col in range(GRID_SIZE)
            if self.cells[row][col] == 0
        ]

    def add_random_tile(self) -> Optional[Tuple[int, int, int]]:
        """
        Coloca un '2' (90%) o un '4' (10%) en una celda vacía al azar.
        Devuelve (fila, col, valor) de la ficha creada, o None si el
        tablero ya estaba lleno; la interfaz usa esa posición para
        animar la aparición de la ficha nueva.
        """
        empty = self.empty_cells()
        if not empty:
            return None
        row, col = random.choice(empty)
        value = 2 if random.random() < PROBABILITY_TILE_2 else 4
        self.cells[row][col] = value
        return row, col, value

    # ------------------------------------------------------------------
    # Núcleo del deslizamiento y la fusión
    # ------------------------------------------------------------------
    @staticmethod
    def _compress_and_merge(
        line: List[int],
    ) -> Tuple[List[int], int, bool, List["_LineShift"]]:
        # TODO: comprimir los huecos, fusionar cada par de fichas iguales
        # una sola vez por turno (ej: [2,2,2,2] -> [4,4], nunca [8,0] ni
        # [4,2,2]), y volver a rellenar con ceros hasta el tamano
        # original. Devolver (linea_resultante, puntos_obtenidos,
        # hubo_cambio, desplazamientos).
        raise NotImplementedError("Implementar compresion y fusion de una linea de 2048 (A02)")

    @classmethod
    def _compress_and_merge_or_default(
        cls, line: List[int],
    ) -> Tuple[List[int], int, bool, List["_LineShift"]]:
        """Envoltorio de `_compress_and_merge` que cubre el desafio A02
        sin implementar -- ya sea que lance NotImplementedError (el TODO
        real) o devuelva None -- tratandolo como si la linea no hubiera
        cambiado (sin puntos ni fichas movidas) en vez de romper el
        movimiento entero.
        """
        try:
            outcome = cls._compress_and_merge(line)
        except Exception:
            outcome = None
        if outcome is None:
            return list(line), 0, False, []
        return outcome

    @staticmethod
    def _real_index(line_index: int, reverse: bool) -> int:
        """Traduce un índice dentro de una línea (posiblemente invertida) a su índice real en el tablero."""
        return line_index if not reverse else GRID_SIZE - 1 - line_index

    def _process_rows(self, reverse: bool) -> Tuple[bool, List[TileMovement]]:
        """Aplica el deslizamiento horizontal (LEFT/RIGHT) fila a fila."""
        changed_overall = False
        movements: List[TileMovement] = []

        for row in range(GRID_SIZE):
            line = self.cells[row][:]
            if reverse:
                line = line[::-1]

            result, points, changed, shifts = self._compress_and_merge_or_default(line)

            if not changed:
                continue

            changed_overall = True
            self.score += points
            for shift in shifts:
                source_col = self._real_index(shift.source_index, reverse)
                target_col = self._real_index(shift.target_index, reverse)
                movements.append(
                    TileMovement((row, source_col), (row, target_col), shift.source_value, shift.merged)
                )

            if reverse:
                result = result[::-1]
            self.cells[row] = result

        return changed_overall, movements

    def _process_columns(self, reverse: bool) -> Tuple[bool, List[TileMovement]]:
        """Aplica el deslizamiento vertical (UP/DOWN) columna a columna."""
        changed_overall = False
        movements: List[TileMovement] = []

        for col in range(GRID_SIZE):
            line = [self.cells[row][col] for row in range(GRID_SIZE)]
            if reverse:
                line = line[::-1]

            result, points, changed, shifts = self._compress_and_merge_or_default(line)

            if not changed:
                continue

            changed_overall = True
            self.score += points
            for shift in shifts:
                source_row = self._real_index(shift.source_index, reverse)
                target_row = self._real_index(shift.target_index, reverse)
                movements.append(
                    TileMovement((source_row, col), (target_row, col), shift.source_value, shift.merged)
                )

            if reverse:
                result = result[::-1]
            for row in range(GRID_SIZE):
                self.cells[row][col] = result[row]

        return changed_overall, movements

    # ------------------------------------------------------------------
    # API pública de movimiento
    # ------------------------------------------------------------------
    def move(self, direction: str) -> MoveResult:
        """
        Ejecuta un movimiento completo: desliza+fusiona el tablero en
        `direction`, y si hubo cambio, agrega una ficha nueva y
        recalcula las banderas de victoria/derrota.

        Devuelve un MoveResult: si `changed` es False, el
        tablero no se tocó (no se gasta turno ni se genera ficha nueva).
        Si es True, trae además la lista de TileMovement (para animar
        el deslizamiento) y la posición/valor de la ficha nueva
        (para animar su aparición DESPUÉS del deslizamiento).
        """
        if direction not in VALID_DIRECTIONS:
            raise ValueError(f"dirección inválida: {direction!r}")

        if self.lost or self.won:
            return MoveResult(changed=False)

        if direction == "LEFT":
            changed, movements = self._process_rows(reverse=False)
        elif direction == "RIGHT":
            changed, movements = self._process_rows(reverse=True)
        elif direction == "UP":
            changed, movements = self._process_columns(reverse=False)
        else:  # "DOWN"
            changed, movements = self._process_columns(reverse=True)

        if not changed:
            return MoveResult(changed=False)

        if any(value >= WIN_VALUE for row in self.cells for value in row):
            self.won = True

        new_tile = self.add_random_tile()

        if not self._has_possible_moves():
            self.lost = True

        new_tile_position = (new_tile[0], new_tile[1]) if new_tile else None
        new_tile_value = new_tile[2] if new_tile else None
        return MoveResult(
            changed=True,
            movements=movements,
            new_tile_position=new_tile_position,
            new_tile_value=new_tile_value,
        )

    def _has_possible_moves(self) -> bool:
        """Game Over sólo si el tablero está lleno Y no hay fusiones posibles."""
        if self.empty_cells():
            return True
        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                value = self.cells[row][col]
                if col + 1 < GRID_SIZE and self.cells[row][col + 1] == value:
                    return True
                if row + 1 < GRID_SIZE and self.cells[row + 1][col] == value:
                    return True
        return False
