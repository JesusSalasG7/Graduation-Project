"""Genera la respuesta de la Etapa 2/3 de la sesión guiada a partir del
prompt que escribe el participante.

La llamada a la IA en si (aislada, sin contexto del ejercicio ni del juego,
system prompt restrictivo -- ver ahí mismo por qué NO tiene temperature
baja) vive en isolated_prompt.py. Este archivo solo orquesta: le pasa el
prompt del participante a esa llamada aislada y, con la respuesta que
vuelva, genera los dos bancos de preguntas de opción multiple (comprension
para la Etapa 3, razonamiento para la Etapa 4) y el texto de explicación
de razonamiento de la Etapa 4 -- todo esto sí puede usar el enunciado del
ejercicio como contexto, porque es herramienta de evaluación armada por el
investigador, no la respuesta que ve la IA del participante.
"""

import time
from dataclasses import dataclass, field

from ai import ai_backend
from content.challenges import Challenge
from ai.isolated_prompt import ask_isolated_prompt
from content.quiz import QuizQuestion

# 14 preguntas de opción multiple + una explicación de razonamiento de 2-4
# parrafos, generadas en una sola llamada JSON-schema al backend de IA
# configurado (ver ai_backend.py): en la practica esto puede superar 90s
# (visto en sesiones reales, ver generate_isolated_response), lo que hacia
# fallar en silencio Etapas 4 Y 5 a la vez (ambas salen de esta misma
# llamada) sin ningún mensaje útil.
QUIZ_TIMEOUT_SECONDS = 180
CLAUDE_MODEL = "sonnet"  # solo aplica cuando ai_backend.active_provider() == "claude"

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
        "reasoning_explanation": {"type": "string"},
    },
    "required": ["comprehension_questions", "reasoning_questions", "reasoning_explanation"],
}

# Orden de "siguiente desafio" del módulo de sesión guiada: los 7 juegos,
# de más fácil a más difícil (ver difficulty.py).
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
    reasoning_explanation: str = ""  # Etapa 4 -- por qué la IA aislada llegó a esa respuesta
    quiz_generation_error: str = ""  # por qué comprehension/reasoning quedaron vacíos (si aplica)


def _question_from_payload(payload: dict) -> QuizQuestion:
    options = [str(o) for o in payload["options"]][:4]
    return QuizQuestion(
        text=str(payload["question"]), options=options,
        correct_index=max(0, min(3, int(payload["correct_index"]))),
    )


def generate_response_quiz(
    challenge: Challenge, response_text: str,
) -> tuple[list[QuizQuestion], list[QuizQuestion], str, str]:
    """Genera, a partir del código que devolvió la IA AISLADA al prompt del
    participante, dos bancos de 7 preguntas de opción multiple -- uno sobre
    que hace esa implementación (Etapa 3) y otro sobre si el razonamiento y
    la implementación son correctos y alcanzan para resolver el desafío
    (Etapa 4, razonamiento) -- más un texto (también Etapa 4) que evalua esa
    solución contra el enunciado.

    A diferencia de la llamada aislada, esta SI usa el enunciado del
    ejercicio como contexto -- es una herramienta de evaluación armada por
    el investigador, no la respuesta que recibe el participante. No usa
    ninguna herramienta (`--tools ""`): es generación de texto pura,
    restringida a un JSON Schema.

    Devuelve ([], [], "", <razón>) si algo falla (la sesión guiada sigue
    funcionando sin preguntas ni explicación antes que romperse) -- la razón
    queda en ChallengeSolveResult.quiz_generation_error para que la interfaz
    (ver session_wizard._build_quiz) pueda mostrarla en vez de un
    "no se generaron preguntas" sin ninguna pista de por qué.
    """
    prompt = (
        "Un participante de un estudio escribió un prompt para pedirle a una "
        "IA que resuelva el siguiente ejercicio de programación. Tu tarea es "
        "evaluar si el código que devolvió esa IA es correcto y suficiente "
        "para resolver el ejercicio tal como lo pide el enunciado.\n\n"
        f"Enunciado del ejercicio:\n{challenge.statement}\n\n"
        f"Respuesta de la IA al prompt del participante:\n\"\"\"\n{response_text}\n\"\"\"\n\n"
        "Genera lo siguiente, en español:\n\n"
        "1. Un texto \"reasoning_explanation\" de 2 a 4 párrafos, en lenguaje "
        "claro para un participante (no un experto), que evalúe ESA "
        "respuesta concreta contra el enunciado: el paso a paso y la lógica "
        "que sigue el código (en qué orden hace las cosas, qué estructuras "
        "de datos o control usa y para qué), si ese razonamiento es "
        "correcto, si la implementación cumple cada requisito del enunciado "
        "(firma, tipo de retorno, casos borde, restricciones), y una "
        "conclusión clara de si alcanza o no para resolver el desafío -- y, "
        "si no alcanza, qué requisito concreto no cumple o en qué caso "
        "falla. No inventes métricas hipotéticas (tiempos, rendimiento), "
        "comportamientos no verificados, ni ventajas que no estén soportadas "
        "por el código de la respuesta -- evalúa únicamente lo que el código "
        "realmente hace.\n\n"
        "2. Dos bancos de exactamente 7 preguntas de opción múltiple cada "
        "uno, con exactamente 4 opciones y una sola correcta (correct_index "
        "de 0 a 3), dificultad moderada, sin ambigüedad ni opciones "
        "absurdas.\n\n"
        "Banco \"comprehension_questions\" (7 preguntas): sobre QUÉ HACE esa "
        "implementación concreta -- qué devuelve para entradas específicas, "
        "cómo maneja los casos borde, qué estructuras usa y cómo se "
        "comporta paso a paso.\n"
        "Banco \"reasoning_questions\" (7 preguntas): sobre la evaluación "
        "descrita en \"reasoning_explanation\" -- si el razonamiento y la "
        "implementación son correctos, qué requisitos del enunciado cumple "
        "o no cumple, en qué casos daría un resultado correcto o incorrecto, "
        "y si en conjunto resuelve el desafío."
    )
    result = ai_backend.run_json_schema_prompt(
        prompt, RESPONSE_QUIZ_JSON_SCHEMA, CLAUDE_MODEL, QUIZ_TIMEOUT_SECONDS,
    )
    if not result.ok:
        return [], [], "", result.error

    try:
        structured = result.payload
        comprehension = [_question_from_payload(q) for q in structured["comprehension_questions"]][:7]
        reasoning = [_question_from_payload(q) for q in structured["reasoning_questions"]][:7]
        explanation = str(structured["reasoning_explanation"]).strip()
        return comprehension, reasoning, explanation, ""
    except Exception as exc:
        return [], [], "", f"Respuesta inesperada del backend de IA al generar las preguntas: {exc}"


def generate_isolated_response(challenge: Challenge, participant_prompt: str) -> ChallengeSolveResult:
    """Envía el prompt del participante a la llamada 100% aislada (ver
    isolated_prompt.ask_isolated_prompt) y, si responde, arma los bancos de
    preguntas y la explicación de razonamiento de las Etapas 3 y 4 a partir
    de esa respuesta.
    """
    started = time.monotonic()
    result = ask_isolated_prompt(participant_prompt)
    elapsed = time.monotonic() - started

    if not result.ok:
        return ChallengeSolveResult(ok=False, error=result.error, elapsed_seconds=elapsed)

    comprehension_questions, reasoning_questions, reasoning_explanation, quiz_error = generate_response_quiz(
        challenge, result.text,
    )
    return ChallengeSolveResult(
        ok=True, response_text=result.text, elapsed_seconds=elapsed,
        comprehension_questions=comprehension_questions, reasoning_questions=reasoning_questions,
        reasoning_explanation=reasoning_explanation, quiz_generation_error=quiz_error,
    )
