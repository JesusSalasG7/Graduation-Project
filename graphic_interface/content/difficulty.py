"""Orden de dificultad de los 7 juegos, para la vista "Ver juegos en dificultad"
de la GUI.

El ranking se basa en la complejidad del desafio algoritmico central de cada
juego, no en lo dificil que sea JUGAR cada uno.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DifficultyInfo:
    rank: int  # 1 = mas facil, 7 = mas dificil
    tier: str  # etiqueta corta para la UI
    reason: str  # por que ocupa ese puesto, en una linea


DIFFICULTY: dict[str, DifficultyInfo] = {
    "Game-01": DifficultyInfo(
        1, "Fácil",
        "Recorrer una lista y contar, reutilizando un filtro que ya viene resuelto.",
    ),
    "Game-04": DifficultyInfo(
        2, "Fácil",
        "Invertir un string y compararlo con el original, sin ningun helper previo.",
    ),
    "Game-05": DifficultyInfo(
        3, "Media",
        "Detectar valores repetidos en una matriz usando conjuntos (hash).",
    ),
    "Game-06": DifficultyInfo(
        4, "Media",
        "Implementar un algoritmo de ordenamiento completo (mergesort/quicksort/...).",
    ),
    "Game-07": DifficultyInfo(
        5, "Media-alta",
        "Regla de vecinos (Conway) aplicada a toda la grilla, con celdas bloqueadas.",
    ),
    "Game-02": DifficultyInfo(
        6, "Alta",
        "Motor completo de 2048: fusion con estado, en las 4 direcciones del tablero.",
    ),
    "Game-03": DifficultyInfo(
        7, "Muy alta",
        "Busqueda de un patron por fuerza bruta en 3 ejes (como una sopa de letras en 3D).",
    ),
}


def get_difficulty(game_name: str) -> DifficultyInfo | None:
    return DIFFICULTY.get(game_name)
