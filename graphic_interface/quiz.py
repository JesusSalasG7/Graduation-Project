"""Estructura compartida para preguntas de seleccion multiple (opcion unica).

La usan tanto el banco estatico de preguntas sobre el enunciado
(statement_quiz.py) como las preguntas generadas dinamicamente sobre la
solucion concreta de cada participante (challenge_solver.py).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class QuizQuestion:
    text: str
    options: list[str]  # exactamente 4
    correct_index: int  # 0..3
