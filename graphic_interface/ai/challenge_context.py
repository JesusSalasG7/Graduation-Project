"""Código del juego que recibe la IA aislada en la Etapa 3 de la sesión
guiada (ver isolated_prompt.ask_isolated_prompt).

La IA no ve el enunciado, pero sí todo el código Python del juego del
desafío actual, para que trabaje con los nombres, clases y métodos reales
siguiendo solo las instrucciones del participante. Para que un prompt vago
no alcance a resolver el desafío, ese código llega sin pistas:

  - Solo los .py de la carpeta del juego: sin tests/ (repiten los
    ejemplos del enunciado), sin los .md (guías y README) y sin nada que
    no sea .py.
  - Sin ningún comentario ni docstring, en ningún archivo (muchos explican
    el desafío o cómo resolverlo).
  - La función/método del desafío queda solo con su firma y un
    `raise NotImplementedError` sin mensaje.
  - Sin las funciones que ya resuelven el desafío casi igual (ver
    HIDDEN_FUNCTIONS).

Los textos que muestra el juego en pantalla (instrucciones, guías) se
dejan tal cual: son parte del juego que el participante ya vio.

Nunca se modifica el código real del proyecto: todo se arma en memoria.
"""

import ast
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from content.challenges import Challenge
from games.game_patch import PatchError, _find_function_slot, _parse_location
from paths import PROJECT_ROOT

# Carpetas que nunca se le pasan a la IA (en cualquier nivel).
EXCLUDED_DIRS = {"tests", "__pycache__", ".venv", ".git", "docs"}

# Funciones que se sacan del código que ve la IA porque resuelven el
# desafío casi igual -- copiarlas bastaría con un prompt vago. Por juego:
# {archivo relativo: [nombres de función de nivel módulo]}. Solo deben
# figurar funciones que el resto del juego no usa.
HIDDEN_FUNCTIONS: dict[str, dict[str, list[str]]] = {
    # Misma búsqueda por fuerza bruta que find_3d_pattern, sin cortar en
    # la primera coincidencia.
    "Game-03": {"src/algorithm.py": ["find_all_matches"]},
}


@dataclass
class CodeContext:
    text: str  # el bloque de código tal como se le envía a la IA
    files: list[str] = field(default_factory=list)  # rutas relativas incluidas, en orden
    sha256: str = ""  # huella de `text`, para el registro de la sesión


def game_dir(challenge: Challenge) -> Path:
    return PROJECT_ROOT / challenge.game


def _python_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if any(part in EXCLUDED_DIRS for part in relative.parts[:-1]):
            continue
        files.append(path)
    # main.py y settings.py primero (dan el panorama), después el resto.
    priority = {"main.py": 0, "settings.py": 1}
    return sorted(files, key=lambda p: (priority.get(str(p.relative_to(root)), 2), str(p.relative_to(root))))


def _is_docstring(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _remove_docstrings(tree: ast.Module) -> None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.body and _is_docstring(node.body[0]):
                node.body = node.body[1:] or [ast.Pass()]


def sanitize_source(
    source: str, challenge: Optional[tuple[Optional[str], str]] = None,
    hidden_functions: tuple[str, ...] = (),
) -> str:
    """Devuelve `source` sin comentarios ni docstrings (se regenera con
    ast.unparse, que no conserva comentarios). Si `challenge` = (clase,
    función), deja esa función/método solo con `raise
    NotImplementedError`; las funciones de `hidden_functions` (nivel
    módulo) se quitan."""
    tree = ast.parse(source)
    _remove_docstrings(tree)

    if challenge is not None:
        class_name, func_name = challenge
        body, index = _find_function_slot(tree, class_name, func_name)
        body[index].body = [ast.Raise(exc=ast.Name(id="NotImplementedError", ctx=ast.Load()), cause=None)]

    if hidden_functions:
        tree.body = [
            node for node in tree.body
            if not (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in hidden_functions)
        ]

    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def build_code_context(challenge: Challenge, root: Optional[Path] = None) -> CodeContext:
    """Arma el bloque con el código del juego de `challenge`. Lanza
    PatchError si no encuentra la función del desafío y OSError si no
    puede leer la carpeta del juego."""
    root = root or game_dir(challenge)
    if not root.is_dir():
        raise OSError(f"No se encontró la carpeta del juego {challenge.game}.")
    relative_file, class_name, func_name = _parse_location(challenge.location)
    hidden = HIDDEN_FUNCTIONS.get(challenge.game, {})

    sections = []
    files = []
    found_challenge_file = False
    for path in _python_files(root):
        relative = path.relative_to(root).as_posix()
        is_challenge_file = relative == relative_file
        found_challenge_file = found_challenge_file or is_challenge_file
        source = sanitize_source(
            path.read_text(encoding="utf-8"),
            challenge=(class_name, func_name) if is_challenge_file else None,
            hidden_functions=tuple(hidden.get(relative, ())),
        )
        files.append(relative)
        sections.append(f"### Archivo: {relative}\n```python\n{source.rstrip()}\n```")

    if not found_challenge_file:
        raise PatchError(f"No se encontró {relative_file} en {challenge.game}.")

    text = "\n\n".join(sections)
    return CodeContext(text=text, files=files, sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())
