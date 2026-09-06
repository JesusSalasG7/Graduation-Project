"""Resuelve el desafio de un juego invocando Claude Code en modo headless
(`claude -p`), a partir del prompt que escribio el participante.

Todo ocurre sobre una COPIA TEMPORAL y aislada del juego (nunca sobre el
repositorio real): se copia la carpeta del juego, se reinicia la funcion
del desafio a un estado "sin resolver", se le pide a Claude Code que la
implemente siguiendo el prompt del participante, y al terminar se lee el
resultado y se borra la copia. Asi ningun participante pisa la solucion
de otro en el juego compartido, y no queda ningun archivo temporal dando
vueltas.

La invocacion a `claude` corre con `--restricted` (sin Bash/WebFetch, y
las herramientas de archivo confinadas al directorio de trabajo) y
`--tools Read,Edit,Write`, para que un prompt de participante nunca pueda
ejecutar comandos ni tocar nada fuera de la copia temporal.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from challenges import Challenge
from game_launcher import GameInfo
from quiz import QuizQuestion

CLAUDE_BIN = "claude"
CLAUDE_TIMEOUT_SECONDS = 300
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

SOLUTION_QUIZ_JSON_SCHEMA = {
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

# Donde vive, dentro de cada carpeta de juego, la funcion del desafio A0X
# (ruta relativa al juego + nombre de la funcion), para poder reiniciarla
# a un estado "sin resolver" antes de pedirle a Claude Code que la
# implemente segun el prompt del participante.
STUB_TARGETS: dict[str, dict[str, str]] = {
    "Game-01": {"rel_path": "src/world.py", "function_name": "count_apples_in_range"},
    "Game-02": {"rel_path": "logic2048.py", "function_name": "_compress_and_merge"},
    "Game-03": {"rel_path": "src/algorithm.py", "function_name": "find_3d_pattern"},
    "Game-04": {"rel_path": "src/signal_check.py", "function_name": "is_stable_signal"},
    "Game-05": {"rel_path": "src/algorithm.py", "function_name": "find_repeated"},
    "Game-06": {"rel_path": "src/algorithms/sort_task.py", "function_name": "sort_words_by_length"},
    "Game-07": {"rel_path": "src/board.py", "function_name": "next_generation"},
}

# Orden de "siguiente desafio" del modulo de sesion guiada: los 7 juegos,
# de mas facil a mas dificil (ver difficulty.py).
GUIDED_SESSION_GAME_ORDER = [
    "Game-01", "Game-04", "Game-05", "Game-06", "Game-07", "Game-02", "Game-03",
]

# Como validar la solucion de cada juego usando SU PROPIA suite de pruebas
# real (la misma que ya vive en el repo, no una inventada para este modulo):
# - "pytest": el juego tiene tests con pytest en tests/<archivo>.py.
# - "script_assert": un script en la raiz del juego que usa `assert` y
#   termina con codigo de salida distinto de 0 si algo falla.
# - "script_markers": un script en la raiz del juego que imprime "[OK]"/
#   "[FALLO]" por caso pero SIEMPRE termina con codigo 0 (no usa assert),
#   asi que hay que contar los marcadores en la salida para saber si paso.
# - "unittest_discover": el juego tiene tests con unittest (stdlib, sin
#   pytest instalado) en una carpeta, corridos con `-m unittest discover`.
# Game-02 no tiene ninguna suite de pruebas todavia (ver ChallengeSolveResult
# .tests_passed = None en ese caso: la UI ya lo maneja mostrando un aviso
# neutro en vez de un veredicto).
TEST_RUNNERS: dict[str, dict[str, str]] = {
    "Game-01": {"kind": "pytest", "target": "tests/test_world_count_apples_in_range.py"},
    "Game-04": {"kind": "pytest", "target": "tests/test_signal_check.py"},
    "Game-06": {"kind": "pytest", "target": "tests/test_sort_task.py"},
    "Game-03": {"kind": "script_assert", "target": "test_search_3d_pattern.py"},
    "Game-05": {"kind": "script_markers", "target": "test_find_repeated.py"},
    "Game-07": {"kind": "unittest_discover", "target": "tests"},
}

TEST_TIMEOUT_SECONDS = 60

_IGNORE_COPY = shutil.ignore_patterns(
    ".venv", "__pycache__", ".pytest_cache", ".git", "*.pyc",
)


@dataclass
class ChallengeSolveResult:
    ok: bool
    function_code: str = ""
    summary: str = ""
    error: str = ""
    elapsed_seconds: float = 0.0
    tests_passed: Optional[bool] = None  # None = el juego no tiene suite configurada
    tests_summary: str = ""
    tests_output: str = ""
    comprehension_questions: list[QuizQuestion] = field(default_factory=list)  # Etapa 3
    reasoning_questions: list[QuizQuestion] = field(default_factory=list)  # Etapa 4


def _game_venv_python(game_path: Path) -> Path:
    """Interprete del .venv PROPIO del juego (no el .venv unificado del
    proyecto): es el que tiene instaladas sus dependencias (pytest, pygame,
    etc.). La copia temporal no trae su propio .venv (ver _IGNORE_COPY), asi
    que se ejecuta este interprete con cwd apuntando a la copia.
    """
    candidate = game_path / ".venv" / "bin" / "python"
    return candidate if candidate.exists() else Path(sys.executable)


def run_challenge_tests(game_name: str, game_path: Path, work_dir: Path) -> tuple[Optional[bool], str, str]:
    """Corre la suite de pruebas REAL del desafio (la que ya vive en el
    repo) contra la copia temporal ya resuelta por Claude Code.

    Devuelve (paso, resumen, salida_completa). `paso` es None si el juego
    no tiene una suite configurada en TEST_RUNNERS.
    """
    runner = TEST_RUNNERS.get(game_name)
    if runner is None:
        return None, "", ""

    python = _game_venv_python(game_path)
    target = runner["target"]
    if not (work_dir / target).exists():
        return None, f"No se encontro el archivo de pruebas '{target}'.", ""

    if runner["kind"] == "pytest":
        cmd = [str(python), "-m", "pytest", target, "-q", "--no-header", "--color=no"]
    elif runner["kind"] == "unittest_discover":
        cmd = [str(python), "-m", "unittest", "discover", "-s", target]
    else:
        cmd = [str(python), target]

    try:
        proc = subprocess.run(
            cmd, cwd=str(work_dir), capture_output=True, text=True,
            timeout=TEST_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return False, "Las pruebas no terminaron a tiempo.", ""
    except FileNotFoundError:
        return None, "No se encontro el interprete de pruebas del juego (falta su .venv).", ""

    output = (proc.stdout + "\n" + proc.stderr).strip()

    if runner["kind"] == "pytest":
        passed = proc.returncode == 0
        summary_line = next(
            (
                line.strip() for line in reversed(proc.stdout.splitlines())
                if "passed" in line or "failed" in line or "error" in line
            ),
            f"pytest termino con codigo {proc.returncode}",
        )
        return passed, summary_line.strip("= "), output

    if runner["kind"] == "script_assert":
        passed = proc.returncode == 0
        summary = "Todos los casos de prueba pasaron." if passed else (
            f"Fallo al menos un caso de prueba (codigo de salida {proc.returncode})."
        )
        return passed, summary, output

    if runner["kind"] == "script_markers":
        ok_count = proc.stdout.count("[OK]")
        fail_count = proc.stdout.count("[FALLO]")
        passed = proc.returncode == 0 and fail_count == 0 and ok_count > 0
        return passed, f"{ok_count} caso(s) OK, {fail_count} caso(s) con FALLO.", output

    if runner["kind"] == "unittest_discover":
        # unittest imprime el resumen en stderr, ej. "Ran 10 tests in 0.001s\n\nOK"
        # o "...\nFAILED (failures=1)".
        passed = proc.returncode == 0
        summary_line = next(
            (line.strip() for line in reversed(proc.stderr.splitlines()) if line.strip()),
            f"unittest termino con codigo {proc.returncode}",
        )
        return passed, summary_line, output

    return None, "", output


def _find_function_block(lines: list[str], function_name: str) -> tuple[int, int, str]:
    """Ubica `def {function_name}(...):` (firma posiblemente multilinea) y
    devuelve (indice_fin_firma, indice_fin_cuerpo, indent_de_la_firma).
    """
    def_pattern = re.compile(rf"^(\s*)def {re.escape(function_name)}\(")
    start = None
    indent = ""
    for i, line in enumerate(lines):
        match = def_pattern.match(line)
        if match:
            start = i
            indent = match.group(1)
            break
    if start is None:
        raise ValueError(f"No se encontro la funcion '{function_name}'")

    sig_end = start
    while not lines[sig_end].rstrip().endswith(":"):
        sig_end += 1

    body_end = sig_end + 1
    while body_end < len(lines):
        line = lines[body_end]
        if line.strip() == "":
            body_end += 1
            continue
        current_indent = len(line) - len(line.lstrip(" "))
        if current_indent <= len(indent):
            break
        body_end += 1

    return sig_end, body_end, indent


def reset_function_to_stub(file_path: Path, function_name: str) -> None:
    """Reemplaza el cuerpo de `function_name`, en `file_path`, por un stub
    "sin resolver" (mismo patron que Game-04 antes de implementarse).
    """
    text = file_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    sig_end, body_end, indent = _find_function_block(lines, function_name)

    stub_body = (
        f'{indent}    """Por implementar: ver el enunciado del desafio."""\n'
        f'{indent}    raise NotImplementedError(\n'
        f'{indent}        "Implementa {function_name} siguiendo el prompt del participante."\n'
        f'{indent}    )\n'
    )
    new_lines = lines[:sig_end + 1] + [stub_body] + lines[body_end:]
    file_path.write_text("".join(new_lines), encoding="utf-8")


def extract_function_source(file_path: Path, function_name: str) -> str:
    """Devuelve el codigo fuente completo (firma + cuerpo) de `function_name`
    tal como quedo en `file_path`, para mostrarlo como resultado."""
    text = file_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    def_pattern = re.compile(rf"^(\s*)def {re.escape(function_name)}\(")
    start = None
    for i, line in enumerate(lines):
        if def_pattern.match(line):
            start = i
            break
    if start is None:
        raise ValueError(f"No se encontro la funcion '{function_name}'")
    _, body_end, _ = _find_function_block(lines, function_name)
    return "".join(lines[start:body_end]).rstrip("\n")


def _question_from_payload(payload: dict) -> QuizQuestion:
    options = [str(o) for o in payload["options"]][:4]
    return QuizQuestion(
        text=str(payload["question"]), options=options,
        correct_index=max(0, min(3, int(payload["correct_index"]))),
    )


def generate_solution_quiz(
    challenge: Challenge, function_code: str,
) -> tuple[list[QuizQuestion], list[QuizQuestion]]:
    """Genera, a partir de la solucion concreta que escribio Claude Code para
    ESTE participante, dos bancos de 7 preguntas de opcion multiple: uno
    sobre que hace el codigo (Etapa 3) y otro sobre por que funciona asi
    (Etapa 4, razonamiento). No usa ninguna herramienta (`--tools ""`): es
    generacion de texto pura, restringida a un JSON Schema.

    Devuelve ([], []) si algo falla (la sesion guiada sigue funcionando sin
    preguntas de la solucion antes que romperse).
    """
    prompt = (
        "A partir de la siguiente solucion de un ejercicio de programacion, "
        "genera dos bancos de exactamente 7 preguntas de opcion multiple en "
        "espanol cada uno, con exactamente 4 opciones y una sola correcta "
        "(correct_index de 0 a 3), dificultad moderada, sin ambiguedad ni "
        "opciones absurdas.\n\n"
        f"Enunciado del ejercicio:\n{challenge.statement}\n\n"
        f"Codigo de la solucion:\n```python\n{function_code}\n```\n\n"
        "Banco \"comprehension_questions\" (7 preguntas): sobre QUE HACE este "
        "codigo especifico -- su comportamiento, valores de retorno, casos "
        "borde que maneja tal como esta escrito.\n"
        "Banco \"reasoning_questions\" (7 preguntas): sobre POR QUE funciona "
        "asi -- el razonamiento del algoritmo, su complejidad, decisiones de "
        "diseno, y que pasaria si se cambiara algun aspecto puntual del "
        "enfoque."
    )
    cmd = [
        CLAUDE_BIN, "-p", prompt,
        "--output-format", "json",
        "--json-schema", json.dumps(SOLUTION_QUIZ_JSON_SCHEMA),
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


def _build_claude_prompt(challenge: Challenge, target: dict, participant_prompt: str) -> str:
    return (
        "Estas resolviendo un ejercicio de programacion de un curso. El "
        "siguiente es el enunciado oficial del ejercicio (no lo cambies, es "
        "el criterio de evaluacion):\n\n"
        f"{challenge.statement}\n\n"
        f"Debes implementar EXCLUSIVAMENTE la funcion `{target['function_name']}` "
        f"en el archivo `{target['rel_path']}` de este directorio de trabajo. No "
        "cambies la firma de la funcion, no modifiques ningun otro archivo, y no "
        "agregues dependencias nuevas.\n\n"
        "El siguiente es el prompt que escribio el participante del estudio para "
        "resolver este ejercicio (es la unica instruccion sobre COMO resolverlo; "
        "seguila tal cual, pero sin salirte del alcance de arriba: un unico "
        "archivo, una unica funcion):\n\n"
        f'"""\n{participant_prompt.strip()}\n"""\n\n'
        "Cuando termines, la funcion debe quedar completamente implementada "
        "(sin NotImplementedError ni TODO)."
    )


def solve_challenge_with_claude(
    game: GameInfo, challenge: Challenge, participant_prompt: str,
) -> ChallengeSolveResult:
    import time

    target = STUB_TARGETS.get(game.name)
    if target is None:
        return ChallengeSolveResult(ok=False, error=f"{game.name} no tiene un desafio configurado.")

    temp_root = Path(tempfile.mkdtemp(prefix=f"session_{game.name}_"))
    work_dir = temp_root / game.name
    started = time.monotonic()
    try:
        shutil.copytree(game.path, work_dir, ignore=_IGNORE_COPY)
        target_file = work_dir / target["rel_path"]
        reset_function_to_stub(target_file, target["function_name"])

        prompt = _build_claude_prompt(challenge, target, participant_prompt)
        cmd = [
            CLAUDE_BIN, "-p", prompt,
            "--output-format", "json",
            "--permission-mode", "acceptEdits",
            "--restricted",
            "--tools", "Read,Edit,Write",
            "--model", CLAUDE_MODEL,
        ]

        try:
            proc = subprocess.run(
                cmd, cwd=str(work_dir), capture_output=True, text=True,
                timeout=CLAUDE_TIMEOUT_SECONDS,
            )
        except FileNotFoundError:
            return ChallengeSolveResult(
                ok=False, error="No se encontro el comando 'claude' en el PATH.",
            )
        except subprocess.TimeoutExpired:
            return ChallengeSolveResult(
                ok=False, error=f"Claude Code no respondio en {CLAUDE_TIMEOUT_SECONDS}s.",
            )

        summary = proc.stdout.strip()
        try:
            payload = json.loads(proc.stdout)
            summary = str(payload.get("result", summary))
        except (json.JSONDecodeError, TypeError):
            pass

        if proc.returncode != 0:
            return ChallengeSolveResult(
                ok=False,
                error=f"Claude Code termino con error (codigo {proc.returncode}).",
                summary=summary or proc.stderr.strip(),
                elapsed_seconds=time.monotonic() - started,
            )

        try:
            function_code = extract_function_source(target_file, target["function_name"])
        except ValueError as exc:
            return ChallengeSolveResult(ok=False, error=str(exc), summary=summary)

        if "NotImplementedError" in function_code:
            return ChallengeSolveResult(
                ok=False,
                error="Claude Code no logro implementar la funcion (sigue sin resolver).",
                summary=summary,
                function_code=function_code,
                elapsed_seconds=time.monotonic() - started,
            )

        tests_passed, tests_summary, tests_output = run_challenge_tests(game.name, game.path, work_dir)
        comprehension_questions, reasoning_questions = generate_solution_quiz(challenge, function_code)

        return ChallengeSolveResult(
            ok=True, function_code=function_code, summary=summary,
            elapsed_seconds=time.monotonic() - started,
            tests_passed=tests_passed, tests_summary=tests_summary, tests_output=tests_output,
            comprehension_questions=comprehension_questions, reasoning_questions=reasoning_questions,
        )
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
