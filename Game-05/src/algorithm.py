"""
Desafío A05 -- detectar los elementos que se repiten en una línea del
tablero.

Enunciado (adaptado a Transmutación Arcana; el algoritmo y el Key
concept originales de la rúbrica no cambian, solo el material sobre el
que se filtra y que se hace con los duplicados detectados):
    "Detecta los valores repetidos de una línea del tablero (fila o
    columna), comparando cada ficha con las que le siguen. La línea se
    rellena inicialmente con los elementos que fue dejando el jugador
    con sus jugadas (sus swaps)."
    Key concept: conjuntos, iteración.
    Enfoque en la comprension: filtrado de datos.

Lógica pura -- este archivo no importa pygame ni gale, para poder
leerse, probarse y calificarse de forma aislada de la parte grafica
del juego (mismo criterio que src/algorithm.py en Game-03). Cada
elemento del tablero (Fuego, Agua, Tierra...) se identifica con el
entero TileKind.value, así que "linea del tablero" y "matriz de
enteros de una fila" son la misma cosa vistas desde dos lados: el
tema del juego eligiendo qué dato filtrar, y el tipo de dato que
`find_repeated` sabe filtrar.

Conectado al juego real en src/board/board.py (Board.resolve_runs):
cuando una Catálisis (match-4+, Módulo A) limpia una fila o columna
entera del tablero, esa línea de fichas es exactamente una matriz de
enteros -- cada casilla es el valor de un TileKind (0..7) -- rellenada
por las jugadas del jugador (sus swaps son los "valores introducidos
por el usuario" del enunciado, reordenando el tablero swap a swap).
find_repeated() sobre esa línea dice cuántos elementos aparecieron
DOS O MÁS VECES, y esa cantidad paga el bonus de "Resonancia
Elemental" (ver settings.RESONANCE_BONUS_PER_KIND): una Catálisis
totalmente mixta (cada elemento aparece una sola vez) no suma nada
extra; una donde algún elemento se repite dentro de la línea, si --
premia la idea temática de que ese elemento "resuena" al aparecer más
de una vez en la misma transmutación, no solo el tamaño del match.
"""

from typing import List


def find_repeated(matrix: List[List[int]]) -> List[int]:
    # TODO: recorrer la matriz fila por fila, valor por valor, y
    # devolver los valores que aparecen 2 o más veces (uno solo por
    # valor, en el orden de su segunda aparición), usando conjuntos en
    # una sola pasada.
    raise NotImplementedError("Implementar la detección de valores repetidos (A05)")
