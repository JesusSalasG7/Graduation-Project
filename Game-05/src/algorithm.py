"""
Desafio A05 -- detectar los elementos que se repiten en una linea del
tablero.

Enunciado (adaptado a Transmutacion Arcana; el algoritmo y el Key
concept originales de la rubrica no cambian, solo el material sobre el
que se filtra y que se hace con los duplicados detectados):
    "Detecta los valores repetidos de una linea del tablero (fila o
    columna), comparando cada ficha con las que le siguen. La linea se
    rellena inicialmente con los elementos que fue dejando el jugador
    con sus jugadas (sus swaps)."
    Key concept: conjuntos, iteracion.
    Enfoque en la comprension: filtrado de datos.

Logica pura -- este archivo no importa pygame ni gale, para poder
leerse, probarse y calificarse de forma aislada de la parte grafica
del juego (mismo criterio que src/algorithm.py en Game-03). Cada
elemento del tablero (Fuego, Agua, Tierra...) se identifica con el
entero TileKind.value, asi que "linea del tablero" y "matriz de
enteros de una fila" son la misma cosa vistas desde dos lados: el
tema del juego eligiendo que dato filtrar, y el tipo de dato que
`find_repeated` sabe filtrar.

Conectado al juego real en src/board/board.py (Board.resolve_runs):
cuando una Catalisis (match-4+, Modulo A) limpia una fila o columna
entera del tablero, esa linea de fichas es exactamente una matriz de
enteros -- cada casilla es el valor de un TileKind (0..7) -- rellenada
por las jugadas del jugador (sus swaps son los "valores introducidos
por el usuario" del enunciado, reordenando el tablero swap a swap).
find_repeated() sobre esa linea dice cuantos elementos aparecieron
DOS O MAS VECES, y esa cantidad paga el bonus de "Resonancia
Elemental" (ver settings.RESONANCE_BONUS_PER_KIND): una Catalisis
totalmente mixta (cada elemento aparece una sola vez) no suma nada
extra; una donde algun elemento se repite dentro de la linea, si --
premia la idea tematica de que ese elemento "resuena" al aparecer mas
de una vez en la misma transmutacion, no solo el tamano del match.
"""

from typing import List


def find_repeated(matrix: List[List[int]]) -> List[int]:
    """
    Recorre la matriz fila por fila, valor por valor, y reporta los
    valores que aparecen dos o mas veces -- uno solo por valor, sin
    importar cuantas veces se repita.

    La forma de "comparar cada elemento con los valores siguientes"
    del enunciado se hace mirandolo al reves, que es lo mismo pero en
    un solo recorrido: en vez de, al llegar a un valor, mirar hacia
    adelante para ver si se repite mas tarde, se guarda cada valor
    nuevo en el conjunto `seen` apenas aparece. Asi, cuando el
    recorrido llega a una aparicion posterior de ese mismo valor, esa
    aparicion posterior *es* "uno de los valores siguientes" de la
    primera, y el chequeo `value in seen` la detecta en tiempo O(1) --
    sin tener que comparar manualmente contra cada valor restante de
    la matriz. Un segundo conjunto, `reported`, evita que un valor que
    se repite 3 o mas veces (p. ej. `[5, 5, 5]`) aparezca mas de una
    vez en el resultado.

    :param matrix: lista de filas, cada una una lista de enteros. No
        se asume ninguna forma particular: no hace falta que sea
        cuadrada ni que todas las filas midan lo mismo (incluso sirve
        para una matriz de una sola fila, como la linea que limpia una
        Catalisis en el tablero).
    :returns: los valores que aparecen 2 o mas veces en la matriz, en
        el orden en que se detecto la repeticion (su segunda
        aparicion), cada uno una sola vez.
    """
    seen = set()
    reported = set()
    repeated: List[int] = []

    for row in matrix:
        for value in row:
            if value in seen:
                if value not in reported:
                    reported.add(value)
                    repeated.append(value)
            else:
                seen.add(value)

    return repeated
