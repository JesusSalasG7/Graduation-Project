"""Entradas del juez: las fichas de referencia de los desafíos, las
secciones de la rúbrica y los prompts a evaluar.

Todo prompt, venga de donde venga, se convierte en un `PromptRecord`. El
juez solo usa `desafio` y `prompt`; el resto de los datos (generador, nivel
pretendido, palabras...) viaja en `extra` y solo se usa al escribir los
resultados y en el análisis.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from content.challenges import CHALLENGES
from paths import JUDGE_DATASET_FILE, JUDGE_RUBRIC_FILE, JUDGE_SPECS_FILE

# Campos del dataset sintético que NO puede ver el juez.
DATASET_EXTRA_FIELDS = ["generador", "nivel_pretendido", "palabras"]

_SPEC_HEADING_RE = re.compile(r"^## (Game-\d{2})\b.*$", re.MULTILINE)
_SECTION_HEADING_RE = re.compile(r"^## (.+)$", re.MULTILINE)
_NUMBERED_ITEM_RE = re.compile(r"^\d+\.", re.MULTILINE)

RUBRIC_SECTION_DIMENSIONS = "Dimensiones"
RUBRIC_SECTION_GLOBAL_LEVEL = "Nivel global"
RUBRIC_SECTION_RULES = "Reglas del juez"
RUBRIC_SECTION_TEMPLATE = "Plantilla del prompt del juez"
RUBRIC_SECTION_OUTPUT_FORMAT = "Formato de salida"


class JudgeInputError(ValueError):
    """Un archivo de entrada falta o no tiene la estructura esperada."""


@dataclass(frozen=True)
class PromptRecord:
    id: str
    desafio: str  # "Game-01" ... "Game-07"
    prompt: str
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RubricParts:
    rubrica: str  # secciones Dimensiones + Nivel global
    reglas: str
    plantilla: str
    formato: str


def _read(path: Path) -> str:
    if not path.exists():
        raise JudgeInputError(f"No se encontró {path}")
    return path.read_text(encoding="utf-8")


def load_challenge_specs(path: Path = JUDGE_SPECS_FILE) -> dict[str, str]:
    """Separa especificaciones.md por los encabezados "## Game-0X" y devuelve
    {"Game-01": ficha, ...}. Cada ficha va desde su encabezado hasta el
    siguiente "## " (así quedan fuera las secciones que no son fichas).
    Valida que estén las de todos los desafíos de content/challenges.py."""
    text = _read(path)
    specs: dict[str, str] = {}
    for match in _SPEC_HEADING_RE.finditer(text):
        following = _SECTION_HEADING_RE.search(text, match.end())
        end = following.start() if following else len(text)
        game = match.group(1)
        if game in specs:
            raise JudgeInputError(f"La ficha de {game} está repetida en {path.name}")
        specs[game] = text[match.start():end].strip()

    missing = sorted(set(CHALLENGES) - set(specs))
    if missing:
        raise JudgeInputError(f"Faltan fichas en {path.name}: {', '.join(missing)}")
    return specs


def _sections(text: str) -> dict[str, str]:
    """{título de la sección "## ...": cuerpo, sin el encabezado}."""
    matches = list(_SECTION_HEADING_RE.finditer(text))
    sections = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1).strip()] = text[match.end():end].strip()
    return sections


def _fenced_block(body: str, language: str, section: str) -> str:
    match = re.search(rf"```{language}\n(.*?)\n```", body, re.DOTALL)
    if not match:
        raise JudgeInputError(f'La sección "{section}" de la rúbrica no tiene un bloque ```{language}')
    return match.group(1)


def load_rubric_parts(path: Path = JUDGE_RUBRIC_FILE) -> RubricParts:
    """Extrae de rubrica.md lo que se inserta en el prompt del juez. Las
    demás secciones (configuración, decisiones pendientes) no se envían."""
    sections = _sections(_read(path))
    required = [
        RUBRIC_SECTION_DIMENSIONS, RUBRIC_SECTION_GLOBAL_LEVEL, RUBRIC_SECTION_RULES,
        RUBRIC_SECTION_TEMPLATE, RUBRIC_SECTION_OUTPUT_FORMAT,
    ]
    missing = [name for name in required if name not in sections]
    if missing:
        raise JudgeInputError(f"Faltan secciones en {path.name}: {', '.join(missing)}")

    rubrica = "\n\n".join(
        f"## {name}\n\n{sections[name]}" for name in (RUBRIC_SECTION_DIMENSIONS, RUBRIC_SECTION_GLOBAL_LEVEL)
    )
    # De las reglas solo va la lista numerada: el párrafo previo habla del
    # estudio ("apuntan a los sesgos que se van a medir"), no al juez.
    rules_body = sections[RUBRIC_SECTION_RULES]
    first_rule = _NUMBERED_ITEM_RE.search(rules_body)
    if not first_rule:
        raise JudgeInputError(f'La sección "{RUBRIC_SECTION_RULES}" no tiene reglas numeradas')
    return RubricParts(
        rubrica=rubrica,
        reglas=rules_body[first_rule.start():].strip(),
        plantilla=_fenced_block(sections[RUBRIC_SECTION_TEMPLATE], "text", RUBRIC_SECTION_TEMPLATE),
        formato=_fenced_block(sections[RUBRIC_SECTION_OUTPUT_FORMAT], "json", RUBRIC_SECTION_OUTPUT_FORMAT),
    )


def load_dataset_prompts(path: Path = JUDGE_DATASET_FILE) -> list[PromptRecord]:
    """Dataset sintético: lista de objetos con id, generador, desafio,
    nivel_pretendido, prompt y palabras."""
    try:
        items = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        raise JudgeInputError(f"{path.name} no es JSON válido: {exc}") from exc
    if not isinstance(items, list):
        raise JudgeInputError(f"{path.name} debe ser una lista de prompts")

    records, seen = [], set()
    for position, item in enumerate(items, start=1):
        missing = [key for key in ["id", "desafio", "prompt", *DATASET_EXTRA_FIELDS] if key not in item]
        if missing:
            raise JudgeInputError(f"Al prompt {position} de {path.name} le falta: {', '.join(missing)}")
        if item["id"] in seen:
            raise JudgeInputError(f"El id {item['id']} está repetido en {path.name}")
        if item["desafio"] not in CHALLENGES:
            raise JudgeInputError(f"El prompt {item['id']} tiene un desafío desconocido: {item['desafio']}")
        seen.add(item["id"])
        records.append(PromptRecord(
            id=str(item["id"]), desafio=item["desafio"], prompt=str(item["prompt"]),
            extra={key: item[key] for key in DATASET_EXTRA_FIELDS},
        ))
    return records


def load_session_prompts() -> list[PromptRecord]:
    """PENDIENTE (entrada preparada, sin implementar): prompts reales de las
    sesiones guiadas.

    Va a recorrer ~/Escritorio/Sesiones_participantes/Participante_N/
    Desafio_k/Etapa_3/intento_M/escrito_etapa3.txt (ver
    storage/stage_capture.write_stage3_files) y devolver un PromptRecord por
    intento, con id "P{N}_D{k}_I{M}", el desafío de esa carpeta y, en
    `extra`, participante, desafío e intento. El resto del juez
    (run_judge, write_results) ya funciona con cualquier lista de
    PromptRecord: solo hay que pasarle judge_config.results_dir(
    SOURCE_SESSIONS) como carpeta de resultados.
    """
    raise NotImplementedError("La evaluación de los prompts reales de las sesiones todavía no está implementada.")
