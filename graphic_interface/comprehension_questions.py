"""Catalogo de preguntas de comprension por juego (tests de seleccion multiple).

Cada juego (Game-01, Game-03, ...) puede tener una tanda de preguntas de
seleccion multiple para verificar que el participante comprendio el
desafio que resolvio (o el prompt de IA que uso para resolverlo, ver
`challenges.py`). Por ahora el catalogo esta vacio: la estructura ya
queda lista para que se agreguen las preguntas reales de cada juego mas
adelante, sin tener que tocar la interfaz grafica.

Para agregar preguntas a un juego, se completa su entrada en QUESTIONS,
por ejemplo:

    "Game-01": [
        Question(
            text="¿Que metodo ya existente reutiliza count_apples_in_range()"
                 " para decidir si una manzana individual pasa el filtro?",
            options=[
                "World._apple_passes_filter",
                "World._spawn_apple",
                "FoodField.remove",
                "Snake.grow",
            ],
            correct_index=0,
        ),
    ],
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Question:
    text: str  # enunciado de la pregunta
    options: list[str]  # alternativas de respuesta (tipicamente 3-5)
    correct_index: int  # indice (0-based) de la opcion correcta en `options`


# Un juego sin entrada, o con lista vacia, se muestra en la GUI como
# "sin preguntas registradas todavia".
QUESTIONS: dict[str, list[Question]] = {
    "Game-01": [],
    "Game-03": [],
    "Game-04": [],
    "Game-05": [],
    "Game-06": [],
}


def get_questions(game_name: str) -> list[Question]:
    return QUESTIONS.get(game_name, [])
