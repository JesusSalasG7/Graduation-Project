"""Genera la respuesta de la Etapa 2/3 de la sesion guiada a partir del
prompt que escribe el participante.

La llamada a la IA en si (aislada, sin contexto del ejercicio ni del juego,
system prompt restrictivo -- ver ahi mismo por que NO tiene temperature
baja) vive en isolated_prompt.py. Este archivo solo orquesta: le pasa el
prompt del participante a esa llamada aislada y, con la respuesta que
vuelva, genera los dos bancos de preguntas de opcion multiple (comprension
para la Etapa 3, razonamiento para la Etapa 4) que sí pueden usar el
enunciado del ejercicio como contexto -- son herramienta de evaluacion del
investigador, no la respuesta que ve la IA del participante.
"""

import json
import subprocess
import time
from dataclasses import dataclass, field

from challenges import Challenge
from isolated_prompt import ask_isolated_prompt
from quiz import QuizQuestion

CLAUDE_BIN = "claude"
QUIZ_TIMEOUT_SECONDS = 90
CLAUDE_MODEL = "sonnet"

_QUESTION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "options": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 4},
        "correct_index": {"type": "integer", "minimum": 0, "maximum": 3},
    },
    "required": ["question", "options", "correct_index"],
}

RESPONSE_QUIZ_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "comprehension_questions": {
            "type": "array", "minItems": 7, "maxItems": 7, "items": _QUESTION_JSON_SCHEMA,
        },
        "reasoning_questions": {
            "type": "array", "minItems": 7, "maxItems": 7, "items": _QUESTION_JSON_SCHEMA,
        },
    },
    "required": ["comprehension_questions", "reasoning_questions"],
}

# Orden de "siguiente desafio" del modulo de sesion guiada: los 7 juegos,
# de mas facil a mas dificil (ver difficulty.py).
GUIDED_SESSION_GAME_ORDER = [
    "Game-01", "Game-04", "Game-05", "Game-06", "Game-07", "Game-02", "Game-03",
]


@dataclass
class ChallengeSolveResult:
    ok: bool
    response_text: str = ""
    error: str = ""
    elapsed_seconds: float = 0.0
    comprehension_questions: list[QuizQuestion] = field(default_factory=list)  # Etapa 3
    reasoning_questions: list[QuizQuestion] = field(default_factory=list)  # Etapa 4


def _question_from_payload(payload: dict) -> QuizQuestion:
    options = [str(o) for o in payload["options"]][:4]
    return QuizQuestion(
        text=str(payload["question"]), options=options,
        correct_index=max(0, min(3, int(payload["correct_index"]))),
    )


def generate_response_quiz(
    challenge: Challenge, response_text: str,
) -> tuple[list[QuizQuestion], list[QuizQuestion]]:
    """Genera, a partir de la respuesta AISLADA que le llego al participante
    (puede ser codigo, texto explicativo, o la IA diciendo que le falta
    contexto), dos bancos de 7 preguntas de opcion multiple: uno sobre que
    dice/hace esa respuesta (Etapa 3) y otro sobre por que es (o no es) una
    respuesta valida al enunciado (Etapa 4, razonamiento).

    A diferencia de la llamada aislada, esta SI usa el enunciado del
    ejercicio como contexto -- es una herramienta de evaluacion armada por
    el investigador, no la respuesta que recibe el participante. No usa
    ninguna herramienta (`--tools ""`): es generacion de texto pura,
    restringida a un JSON Schema.

    Devuelve ([], []) si algo falla (la sesion guiada sigue funcionando sin
    preguntas antes que romperse).
    """
    prompt = (
        "Un participante de un estudio escribio un prompt para pedirle a una "
        "IA que resuelva el siguiente ejercicio de programacion. Esa IA "
        "respondio SIN conocer el enunciado (aislada, solo vio el prompt del "
        "participante), asi que su respuesta puede ser una solucion correcta, "
        "una solucion incompleta, texto que no es codigo, o directamente la "
        "IA diciendo que le falta contexto.\n\n"
        f"Enunciado del ejercicio (para tu referencia, la IA que respondio NO "
        f"lo vio):\n{challenge.statement}\n\n"
        f"Respuesta de la IA al prompt del participante:\n\"\"\"\n{response_text}\n\"\"\"\n\n"
        "Genera dos bancos de exactamente 7 preguntas de opcion multiple en "
        "espanol cada uno, con exactamente 4 opciones y una sola correcta "
        "(correct_index de 0 a 3), dificultad moderada, sin ambiguedad ni "
        "opciones absurdas.\n\n"
        "Banco \"comprehension_questions\" (7 preguntas): sobre QUE DICE o "
        "QUE HACE esa respuesta concreta -- si resuelve el ejercicio o no, "
        "que le falto, que asumio, como se comporta si es codigo.\n"
        "Banco \"reasoning_questions\" (7 preguntas): sobre POR QUE la "
        "respuesta es (o no es) valida frente al enunciado -- que contexto "
        "le hubiera hecho falta al prompt del participante para que la IA "
        "pudiera responder mejor, y que decisiones tomo la IA al quedarse "
        "sin ese contexto."
    )
    cmd = [
        CLAUDE_BIN, "-p", prompt,
        "--output-format", "json",
        "--json-schema", json.dumps(RESPONSE_QUIZ_JSON_SCHEMA),
        "--tools", "",
        "--model", CLAUDE_MODEL,
    ]

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=QUIZ_TIMEOUT_SECONDS,
        )
        payload = json.loads(proc.stdout)
        structured = payload.get("structured_output")
        if structured is None:
            structured = json.loads(payload["result"])
        comprehension = [_question_from_payload(q) for q in structured["comprehension_questions"]][:7]
        reasoning = [_question_from_payload(q) for q in structured["reasoning_questions"]][:7]
        return comprehension, reasoning
    except Exception:
        return [], []


def generate_isolated_response(challenge: Challenge, participant_prompt: str) -> ChallengeSolveResult:
    """Envia el prompt del participante a la llamada 100% aislada (ver
    isolated_prompt.ask_isolated_prompt) y, si responde, arma los bancos de
    preguntas de las Etapas 3 y 4 a partir de esa respuesta.
    """
    started = time.monotonic()
    result = ask_isolated_prompt(participant_prompt)
    elapsed = time.monotonic() - started

    if not result.ok:
        return ChallengeSolveResult(ok=False, error=result.error, elapsed_seconds=elapsed)

    comprehension_questions, reasoning_questions = generate_response_quiz(challenge, result.text)
    return ChallengeSolveResult(
        ok=True, response_text=result.text, elapsed_seconds=elapsed,
        comprehension_questions=comprehension_questions, reasoning_questions=reasoning_questions,
    )
