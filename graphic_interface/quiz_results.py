"""Guarda las respuestas de los cuestionarios de la sesion guiada, por
participante anonimo, en graphic_interface/data/quiz_results/PARTICIPANTE_N.json.

No se usa para bloquear el avance de la sesion guiada (eso sigue siendo
libre) -- es solo el registro de lo que respondio cada participante, para
poder analizarlo despues.
"""

import json
from pathlib import Path

from quiz import QuizQuestion

QUIZ_RESULTS_DIR = Path(__file__).resolve().parent / "data" / "quiz_results"


def save_quiz_answers(
    participant_number: int, game_name: str, stage: str,
    questions: list[QuizQuestion], answers: dict[int, int],
) -> None:
    """Agrega un registro con las respuestas de un cuestionario.

    `stage` identifica de cual de los 3 cuestionarios se trata (ej.
    "etapa1_enunciado", "etapa3_comprension", "etapa4_razonamiento").
    `answers` mapea indice de pregunta -> indice de opcion elegida (-1 si no
    se respondio).
    """
    if not questions:
        return

    QUIZ_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = QUIZ_RESULTS_DIR / f"PARTICIPANTE_{participant_number}.json"

    data = {"participant_number": participant_number, "records": []}
    if file_path.exists():
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
        data.setdefault("records", [])

    record = {
        "game": game_name,
        "stage": stage,
        "questions": [
            {
                "text": q.text,
                "options": q.options,
                "correct_index": q.correct_index,
                "selected_index": answers.get(i, -1),
                "is_correct": answers.get(i, -1) == q.correct_index,
            }
            for i, q in enumerate(questions)
        ],
    }
    data["records"].append(record)
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
