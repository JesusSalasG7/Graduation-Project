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
        """
        Corazón del algoritmo de 2048.

        Recibe una "línea" de 4 valores (una fila o una columna del
        tablero) YA ORIENTADA en la dirección del movimiento: el primer
        elemento de la lista es el más cercano al borde hacia el que se
        desliza. Devuelve una tupla:

            (linea_resultante, puntos_obtenidos, hubo_cambio, desplazamientos)

        El proceso tiene tres fases, porque fusionar dos fichas deja un
        hueco que hay que volver a compactar. Además, para poder animar
        el movimiento en la interfaz, cada ficha original que no era
        cero se rastrea desde su índice de partida hasta su índice de
        llegada (eso es lo que guarda `shifts`).

        1) COMPRIMIR: se identifican los valores distintos de cero junto
           con su índice original, manteniendo su orden relativo, como
           si la "gravedad" del movimiento las empujara todas hacia el
           borde. Ej: [0,2,0,2] -> [(1,2), (3,2)].

        2) FUSIONAR: se recorre esa lista de izquierda a derecha. Si un
           valor es igual al siguiente, se combinan en una única ficha
           del doble de valor -registrando AMBOS índices de origen como
           desplazamientos hacia el mismo índice de destino, marcados
           con merged=True- y el recorrido avanza DOS posiciones
           (i += 2), de modo que la ficha resultante de la fusión nunca
           vuelve a evaluarse en este mismo recorrido. Esto es lo que
           garantiza la regla "una ficha sólo puede fusionarse una vez
           por turno": en una línea [2,2,2,2] el resultado es [4,4] (dos
           fusiones independientes) y no [4,2,2] ni [8,0] -- una ficha
           ya fusionada jamás vuelve a sumarse con su vecina en el mismo
           movimiento.

        3) RECOMPACTAR: la fusión acorta la lista (dos fichas pasan a
           ser una), así que se rellena con ceros hasta volver a tener
           GRID_SIZE elementos, dejando los huecos al final (lejos del
           borde hacia el que se deslizó).
        """
        # Guardamos la línea tal cual llegó (antes de tocar nada) para al
        # final poder comparar y saber si el movimiento tuvo algún efecto.
        # Ejemplo guía que seguimos en cada paso: line = [2, 2, 2, 4]
        original = list(line)

        # -------------------------------------------------------------
        # PASO 1 — COMPRIMIR (quitar los huecos, sin perder de dónde
        # venía cada ficha).
        #
        # `enumerate(line)` recorre la línea dando (índice, valor) para
        # cada posición: (0,2) (1,2) (2,2) (3,4). Filtramos los ceros
        # porque una celda vacía no es una "ficha": no debe ocupar
        # espacio ni participar en la fusión.
        #
        # El resultado es una lista de PARES (índice_original, valor)
        # -no solo los valores- porque más adelante necesitamos poder
        # decir "la ficha que estaba en la posición X terminó en la
        # posición Y", y para eso hay que conservar el índice original.
        #
        # Con line = [2, 2, 2, 4] (sin ceros que filtrar en este caso):
        #   non_zero = [(0, 2), (1, 2), (2, 2), (3, 4)]
        # -------------------------------------------------------------
        non_zero = [(index, value) for index, value in enumerate(line) if value != 0]

        # -------------------------------------------------------------
        # PASO 2 — FUSIONAR, recorriendo `non_zero` de izquierda a
        # derecha con un índice manual `i` (no un for) porque necesitamos
        # poder "saltar de a dos" cuando ocurre una fusión.
        #
        #   merged_line -> los valores ya resueltos, en el orden final.
        #   shifts      -> un registro por CADA ficha original: de
        #                  qué índice partió, a qué índice llegó, con
        #                  qué valor viajaba, y si se fusionó.
        #   points_earned -> suma de los valores nuevos creados por
        #                    cada fusión (regla oficial de 2048: la
        #                    puntuación sube en el valor resultante).
        # -------------------------------------------------------------
        merged_line: List[int] = []
        shifts: List[_LineShift] = []
        points_earned = 0
        i = 0
        while i < len(non_zero):
            source_index, current = non_zero[i]

            # ¿La siguiente ficha en la lista (si existe) tiene el MISMO
            # valor que la actual? Si es así, ambas se fusionan.
            next_exists = i + 1 < len(non_zero)
            is_merge = next_exists and non_zero[i + 1][1] == current

            if is_merge:
                # --- Caso A: fusión de dos fichas iguales ---
                next_source_index, _ = non_zero[i + 1]
                merged_value = current * 2

                # `target_index` es simplemente "la próxima posición
                # libre en el resultado", es decir cuántos elementos ya
                # llevamos escritos en `merged_line` hasta ahora.
                target_index = len(merged_line)

                # Escribimos UNA sola ficha en el resultado (el doble de
                # valor), pero registramos DOS desplazamientos -uno por
                # cada ficha original que participó- apuntando ambos al
                # mismo índice de destino. Así, más adelante, la interfaz
                # puede animar cómo las dos fichas viajan y "chocan" en
                # la misma celda. Ambos quedan marcados merged=True.
                merged_line.append(merged_value)
                points_earned += merged_value
                shifts.append(
                    _LineShift(source_index, target_index, current, True)
                )
                shifts.append(
                    _LineShift(next_source_index, target_index, current, True)
                )

                # Avanzamos DOS posiciones (no una): la ficha resultante
                # de la fusión ya quedó escrita y NO vuelve a evaluarse
                # en este mismo recorrido. Esto es lo que impide que una
                # ficha se fusione dos veces en el mismo movimiento.
                i += 2
            else:
                # --- Caso B: la ficha actual queda tal cual, sin fusión ---
                target_index = len(merged_line)
                merged_line.append(current)
                shifts.append(
                    _LineShift(source_index, target_index, current, False)
                )
                i += 1  # Solo avanzamos una posición: no se consumió ninguna otra ficha.

        # Trazando el ejemplo line = [2, 2, 2, 4] con el bucle de arriba:
        #   i=0: non_zero[1] también vale 2 -> FUSIÓN. merged_line=[4].
        #        shifts: (0->0, val=2, merged=True)
        #                (1->0, val=2, merged=True)
        #        i pasa a 2.
        #   i=2: non_zero[3] vale 4 (distinto de 2) -> SIN fusión.
        #        merged_line=[4, 2]. shifts += (2->1, val=2, merged=False)
        #        i pasa a 3.
        #   i=3: es la ficha de valor 4, no hay i+1 -> SIN fusión.
        #        merged_line=[4, 2, 4]. shifts += (3->2, val=4, merged=False)
        #        i pasa a 4, el bucle termina (4 == len(non_zero)).

        # -------------------------------------------------------------
        # PASO 3 — RECOMPACTAR al tamaño original de la línea.
        #
        # `merged_line` puede haber quedado más corta que `line` (cada
        # fusión reduce el conteo en uno), así que rellenamos con ceros
        # al final -lejos del borde hacia el que se deslizó- hasta
        # recuperar la longitud original.
        #
        # Siguiendo el ejemplo: merged_line=[4,2,4] con len(line)=4
        #   -> result = [4, 2, 4] + [0]*(4-3) = [4, 2, 4, 0]
        # -------------------------------------------------------------
        result = merged_line + [0] * (len(line) - len(merged_line))

        # Si el resultado es idéntico a la línea de entrada, el
        # movimiento no tuvo ningún efecto en esta fila/columna (por
        # ejemplo, deslizar hacia la izquierda una línea que ya está
        # pegada a la izquierda y sin fusiones posibles).
        changed = result != original
        return result, points_earned, changed, shifts

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

            result, points, changed, shifts = self._compress_and_merge(line)

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

            result, points, changed, shifts = self._compress_and_merge(line)

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
