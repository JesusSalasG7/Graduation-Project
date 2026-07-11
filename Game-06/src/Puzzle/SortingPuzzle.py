"""
Lógica pura del minijuego "¿Dónde está la llave?".

El tablero es un arreglo de fragmentos de imagen (Tile, ver
src/Puzzle/Tile.py). Cada Tile sabe permanentemente cuál fragmento de la
imagen debe mostrar (su `id`); lo único que cambia al "ordenar" el
arreglo es EN QUÉ POSICIÓN del tablero queda cada Tile y cuántas veces
se rota. La solución no es "cada fragmento en su casilla de origen": es
la disposición fija de SOLUTION, que revela una silueta oculta distinta
del recorte original de la imagen. Cuando cada Tile llega a su
`target_i`/`target_j`/`target_rotation`, la silueta queda completa.

Esta clase no dibuja nada ni conoce el bucle del juego, el input o la
cámara: solo reordena una lista de Tile. Así el algoritmo de
ordenamiento se puede leer, escribir y probar sin tener que entender el
resto del motor del juego.
"""

from typing import List

import settings
from src.Puzzle.Tile import Tile

# Disposición (casilla + rotación) que resuelve la silueta oculta,
# indexada por la posición de ORIGEN (fila, columna) de cada fragmento,
# es decir, el cuadrante de la imagen original del que se recortó:
#   origen (0,0) -> destino (fila 0, columna 1, rotación 0)
#   origen (0,1) -> destino (fila 1, columna 0, rotación 0)
#   origen (1,0) -> destino (fila 0, columna 0, rotación 2)
#   origen (1,1) -> destino (fila 1, columna 1, rotación 2)
SOLUTION = {
    (0, 0): (0, 1, 0),
    (0, 1): (1, 0, 0),
    (1, 0): (0, 0, 2),
    (1, 1): (1, 1, 2),
}


class SortingPuzzle:
    def __init__(self, tiles: List[Tile]) -> None:
        self.tiles = list(tiles)

    def is_sorted(self) -> bool:
        """True si cada Tile llegó a su casilla y rotación de destino."""
        return all(tile.is_correct_position() for tile in self.tiles)

    def sort(self) -> None:
        pass
    
    @classmethod
    def new_tiles(cls) -> List[Tile]:
        """
        Crea las fichas del tablero: una por casilla, cada una con el
        fragmento de imagen que le corresponde por su posición de origen
        (frame == id) y la casilla + rotación de destino que resuelve la
        silueta oculta, según SOLUTION.
        """
        tile_count = settings.BOARD_WIDTH * settings.BOARD_HEIGHT
        tiles = []
        for value in range(tile_count):
            origin_i, origin_j = divmod(value, settings.BOARD_WIDTH)
            target_i, target_j, target_rotation = SOLUTION[(origin_i, origin_j)]
            tiles.append(
                Tile(
                    x=0,
                    y=0,
                    frame=value,
                    id=value,
                    target_i=target_i,
                    target_j=target_j,
                    target_rotation=target_rotation,
                )
            )
        return tiles
