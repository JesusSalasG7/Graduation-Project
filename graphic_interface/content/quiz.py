"""Estructura compartida para preguntas de selección multiple (opción única).

La usan tanto el banco estático de preguntas sobre el enunciado
(statement_quiz.py) como las preguntas generadas dinámicamente sobre la
solución concreta de cada participante (challenge_solver.py).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class QuizQuestion:
    text: str
    options: list[str]  # exactamente 4
    correct_index: int  # 0..3
