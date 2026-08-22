"""
Desafio A05 -- eliminar los valores duplicados de una matriz de enteros.

Enunciado (rubrica):
    "Elimina los valores duplicados de una matriz de enteros. El
    algoritmo recorre la matriz, comparando cada elemento con los
    valores siguientes y eliminando los duplicados. La matriz se
    rellena inicialmente con los valores introducidos por el usuario."
    Key concept: conjuntos, iteracion.
    Enfoque en la comprension: filtrado de datos.

Logica pura -- este archivo no importa pygame ni gale, para poder
leerse, probarse y calificarse de forma aislada de la parte grafica
del juego (mismo criterio que src/algorithm.py en Game-03).

Conectado al juego real en src/board/board.py (Board.resolve_runs):
cuando una Catalisis (match-4+, Modulo A) limpia una fila o columna
entera del tablero, esa linea de fichas es exactamente una matriz de
enteros -- cada casilla es el valor de un TileKind (0..7) -- rellenada
por las jugadas del jugador (sus swaps son los "valores introducidos
por el usuario" del enunciado, reordenando el tablero swap a swap).
remove_duplicates() sobre esa linea dice cuantos elementos realmente
DISTINTOS se combinaron, y esa cantidad paga el bonus de "Diversidad
Elemental" (ver settings.DIVERSITY_BONUS_PER_KIND): una Catalisis de
un solo elemento repetido no suma nada extra; una que mezcla varios
elementos distintos, si -- premia la idea tematica de "transmutar"
elementos distintos juntos, no solo limpiar una linea larga.
"""

from typing import List


def remove_duplicates(matrix: List[List[int]]) -> List[int]:
    """
    Recorre la matriz fila por fila, valor por valor, y se queda solo
    con la primera aparicion de cada uno.

    La forma de "comparar cada elemento con los valores siguientes"
    del enunciado se hace mirandolo al reves, que es lo mismo pero en
    un solo recorrido: en vez de, al llegar a un valor, mirar hacia
    adelante para ver si se repite mas tarde, se guarda cada valor
    nuevo en el conjunto `seen` apenas aparece. Asi, cuando el
    recorrido llega a una aparicion posterior de ese mismo valor, esa
    aparicion posterior *es* "uno de los valores siguientes" de la
    primera, y el chequeo `value in seen` la detecta y descarta en
    tiempo O(1) -- sin tener que comparar manualmente contra cada
    valor restante de la matriz.

    :param matrix: lista de filas, cada una una lista de enteros. No
        se asume ninguna forma particular: no hace falta que sea
        cuadrada ni que todas las filas midan lo mismo (incluso sirve
        para una matriz de una sola fila, como la linea que limpia una
        Catalisis en el tablero).
    :returns: los valores unicos de la matriz, en el orden en que
        aparecieron por primera vez.
    """
    seen = set()
    unique: List[int] = []

    for row in matrix:
        for value in row:
            if value in seen:
                continue
            seen.add(value)
            unique.append(value)

    return unique
