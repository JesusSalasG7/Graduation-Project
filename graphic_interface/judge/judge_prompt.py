"""Construcción del prompt del juez y validación de su respuesta.

`build_judge_prompt` recibe únicamente el desafío y el texto del prompt del
estudiante: no existe forma de pasarle el nivel pretendido, el generador, el
número de palabras ni el id, así que el juez no puede verlos.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Optional

from judge.judge_inputs import JudgeInputError, RubricParts, load_challenge_specs, load_rubric_parts

DIMENSIONS = ["especificacion", "comportamiento", "restricciones", "casos_borde", "contexto_verificacion"]
GLOBAL_LEVEL = "nivel_global"
SCORE_KEYS = [*DIMENSIONS, GLOBAL_LEVEL]
MIN_SCORE, MAX_SCORE = 1, 4

PLACEHOLDERS = ["ficha", "rubrica", "reglas", "prompt", "formato"]
_PLACEHOLDER_RE = re.compile(r"\{(" + "|".join(PLACEHOLDERS) + r")\}")


@dataclass(frozen=True)
class JudgeContext:
    """Todo lo que es fijo durante una corrida: fichas y partes de la rúbrica."""
    specs: dict[str, str]
    rubric: RubricParts


def load_judge_context() -> JudgeContext:
    rubric = load_rubric_parts()
    missing = [name for name in PLACEHOLDERS if "{" + name + "}" not in rubric.plantilla]
    if missing:
        raise JudgeInputError("A la plantilla del juez le faltan los marcadores: " + ", ".join(missing))
    return JudgeContext(specs=load_challenge_specs(), rubric=rubric)


def build_judge_prompt(context: JudgeContext, desafio: str, prompt_text: str) -> str:
    """Reemplaza {ficha}, {rubrica}, {reglas}, {prompt} y {formato} en la
    plantilla. Se hace en una sola pasada para que un texto insertado que
    contenga, por ejemplo, "{ficha}" no vuelva a reemplazarse."""
    values = {
        "ficha": context.specs[desafio],
        "rubrica": context.rubric.rubrica,
        "reglas": context.rubric.reglas,
        "prompt": prompt_text,
        "formato": context.rubric.formato,
    }
    return _PLACEHOLDER_RE.sub(lambda match: values[match.group(1)], context.rubric.plantilla)


def context_hash(context: JudgeContext, desafio: str) -> str:
    """Huella de todo lo que recibe el juez salvo el prompt del estudiante.
    Si cambia la plantilla, la rúbrica, las reglas o la ficha sin subir
    JUDGE_TEMPLATE_VERSION, las evaluaciones viejas no se dan por hechas."""
    fixed_text = build_judge_prompt(context, desafio, "")
    return hashlib.sha256(fixed_text.encode("utf-8")).hexdigest()[:12]


def _extract_json(text: str) -> Optional[dict]:
    """El juez debe responder solo con JSON, pero a veces lo envuelve en un
    bloque ```json o agrega una frase: se toma desde la primera llave hasta
    la última."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _valid_score(value) -> bool:
    # bool es subclase de int en Python: True no cuenta como puntaje 1.
    return isinstance(value, int) and not isinstance(value, bool) and MIN_SCORE <= value <= MAX_SCORE


def validate_judge_response(text: str) -> tuple[Optional[dict], str]:
    """Devuelve (puntajes, "") si la respuesta trae las 5 dimensiones y el
    nivel global como enteros del 1 al 4, o (None, motivo) si no."""
    data = _extract_json(text)
    if data is None:
        return None, "La respuesta no es un JSON válido"

    dimensions = data.get("dimensiones")
    if not isinstance(dimensions, dict):
        return None, 'Falta el objeto "dimensiones"'

    scores = {}
    for name in DIMENSIONS:
        entry = dimensions.get(name)
        score = entry.get("puntaje") if isinstance(entry, dict) else None
        if not _valid_score(score):
            return None, f'Puntaje ausente o fuera de 1-4 en "{name}"'
        scores[name] = score

    entry = data.get(GLOBAL_LEVEL)
    score = entry.get("puntaje") if isinstance(entry, dict) else None
    if not _valid_score(score):
        return None, f'Puntaje ausente o fuera de 1-4 en "{GLOBAL_LEVEL}"'
    scores[GLOBAL_LEVEL] = score
    return scores, ""


def parse_reasoning(text: str) -> dict:
    """La respuesta completa ya parseada (evidencia y razonamientos), para
    mostrarla en --prueba. Diccionario vacío si no se pudo leer."""
    return _extract_json(text) or {}
