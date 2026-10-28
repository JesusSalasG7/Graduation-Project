"""Lanza una copia temporal de un juego para las Etapas 1 y 6 de la sesión
guiada: "ver el juego sin la solucion" y "ver el juego con la solución
hecha" (la función/método del desafío se reemplaza por el código que
generó la IA aislada a partir del prompt del participante, ver
challenge_solver.generate_isolated_response).

La Etapa 1 NO parchea la función/método del desafío: el código fuente real
de cada juego ya deja esa función sin resolver (TODO + `raise
NotImplementedError`, ver CHALLENGES en challenges.py), así que copiarla
tal cual ya alcanza para que el participante vea la falla real -- no una
versión sintética aparte.

Nunca se toca el código fuente real del proyecto: se copia la carpeta del
juego a un directorio temporal (sin .venv ni __pycache__), se parchea ahí
adentro con el módulo `ast` (solo para la Etapa 6), se lanza el proceso
apuntando a esa copia, y la copia se borra sola en cuanto el proceso
termina.
"""

import ast
import re
import shutil
import tempfile
import textwrap
import threading
from pathlib import Path
from typing import Optional

from content.challenges import Challenge
from games.game_launcher import GameInfo, launch_game_process

# Formato de Challenge.location: "archivo.py -> [Clase.]funcion(args)".
_LOCATION_RE = re.compile(
    r"^\s*(?P<file>\S+\.py)\s*->\s*(?:(?P<cls>[A-Za-z_]\w*)\.)?(?P<func>[A-Za-z_]\w*)\s*\("
)


class PatchError(Exception):
    """La función/método del desafío no se pudo ubicar o reemplazar."""


def _parse_location(location: str) -> tuple[str, Optional[str], str]:
    match = _LOCATION_RE.match(location)
    if not match:
        raise PatchError(f"No se pudo interpretar la ubicación del desafío: {location!r}")
    return match.group("file"), match.group("cls"), match.group("func")


def _find_function_slot(tree: ast.Module, class_name: Optional[str], func_name: str):
    """Devuelve (lista_de_statements, índice) donde vive la función/método
    a reemplazar: el body del módulo, o el body de la clase indicada.
    """
    if class_name is None:
        body = tree.body
    else:
        class_node = next(
            (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == class_name),
            None,
        )
        if class_node is None:
            raise PatchError(f"No se encontró la clase {class_name!r} del desafío.")
        body = class_node.body

    for index, node in enumerate(body):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            return body, index
    raise PatchError(f"No se encontró la función/método {func_name!r} del desafío.")


def _solution_function(func_name: str, solution_code: str) -> ast.FunctionDef:
    """Interpreta `solution_code` -- el texto crudo que devolvió la IA
    aislada, se espera una única definición de función/método -- y
    devuelve su nodo FunctionDef, renombrado para calzar con `func_name`.
    """
    try:
        parsed = ast.parse(textwrap.dedent(solution_code))
    except SyntaxError as exc:
        raise PatchError(f"El código generado no es Python válido: {exc}") from exc

    functions = [n for n in parsed.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    # Con el código del juego a la vista, la IA puede devolver también
    # alguna función auxiliar: se prefiere la que se llama como la del
    # desafío y, si ninguna se llama así, la primera.
    func_node = next((n for n in functions if n.name == func_name), functions[0] if functions else None)
    if func_node is None:
        raise PatchError("El código generado no contiene ninguna función/método.")
    func_node.name = func_name
    return func_node


def _defined_name(node: ast.stmt) -> Optional[str]:
    """Nombre que define una función/clase o una asignación simple
    (`X = ...` / `X: T = ...`); None para el resto."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def _solution_parts(
    func_name: str, class_name: Optional[str], solution_code: str,
) -> tuple[ast.FunctionDef, list[ast.stmt], list[ast.stmt]]:
    """Separa el código de la IA en (función del desafío, auxiliares,
    imports). Con el código del juego a la vista, la IA suele devolver,
    además de la función del desafío, funciones auxiliares o constantes
    que esa función usa (p.ej. `_merge_sort`, `_count_live_neighbors`):
    si solo se insertara la función del desafío, el juego fallaría con
    NameError al llamarla. Si la IA envuelve el método en su clase
    (`class World: ...`), se toma lo de adentro de esa clase."""
    try:
        parsed = ast.parse(textwrap.dedent(solution_code))
    except SyntaxError as exc:
        raise PatchError(f"El código generado no es Python válido: {exc}") from exc

    body = parsed.body
    is_function = lambda n: isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))  # noqa: E731
    if class_name is not None and not any(is_function(n) for n in body):
        wrapper = next(
            (n for n in body if isinstance(n, ast.ClassDef) and any(
                is_function(m) and m.name == func_name for m in n.body)),
            None,
        )
        if wrapper is not None:
            body = [n for n in body if n is not wrapper] + wrapper.body

    functions = [n for n in body if is_function(n)]
    # La que se llama como la del desafío y, si ninguna, la primera (igual que _solution_function).
    main = next((n for n in functions if n.name == func_name), functions[0] if functions else None)
    if main is None:
        raise PatchError("El código generado no contiene ninguna función/método.")
    main.name = func_name
    imports = [n for n in body if isinstance(n, (ast.Import, ast.ImportFrom))]
    helpers = [n for n in body if n is not main and _defined_name(n) not in (None, func_name)]
    return main, helpers, imports


def _apply_solution(game_dir: Path, relative_file: str, class_name: Optional[str],
                    func_name: str, solution_code: str) -> None:
    """Reemplaza la función/método del desafío por la de la IA e inserta
    sus auxiliares en el mismo lugar (módulo o clase): si ya existe algo
    con ese nombre, se reemplaza; si no, se agrega justo antes de la
    función del desafío. Los imports de la IA van al principio del
    módulo."""
    source_path = game_dir / relative_file
    if not source_path.exists():
        raise PatchError(f"No se encontró {relative_file} en la copia del juego.")

    main, helpers, imports = _solution_parts(func_name, class_name, solution_code)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    body, index = _find_function_slot(tree, class_name, func_name)
    body[index] = ast.copy_location(main, body[index])

    for helper in helpers:
        name = _defined_name(helper)
        existing = next((i for i, n in enumerate(body) if _defined_name(n) == name), None)
        if existing is not None:
            body[existing] = helper
        else:
            slot = next(i for i, n in enumerate(body) if n is main)
            body.insert(slot, helper)

    if imports:
        # Después del docstring y de los `from __future__`, que deben ir primero.
        position = 0
        while position < len(tree.body) and (
            (position == 0 and isinstance(tree.body[0], ast.Expr)
             and isinstance(getattr(tree.body[0], "value", None), ast.Constant))
            or (isinstance(tree.body[position], ast.ImportFrom) and tree.body[position].module == "__future__")
        ):
            position += 1
        tree.body[position:position] = imports

    ast.fix_missing_locations(tree)
    source_path.write_text(ast.unparse(tree), encoding="utf-8")


def _copy_game_to_tempdir(game: GameInfo) -> Path:
    tmp_root = Path(tempfile.mkdtemp(prefix=f"sesion_guiada_{game.name}_"))
    dest = tmp_root / game.name
    shutil.copytree(
        game.path, dest,
        ignore=shutil.ignore_patterns(".venv", "__pycache__", "*.pyc", ".git"),
    )
    return dest


# Game-01 (Snake) arranca por defecto en el estado "cover" (splash) y de
# ahí pasa al menú, donde el jugador elige a mano Modo Clásico o Modo
# Desafío. El desafío A01 (World.count_apples_in_range) SOLO se ejercita
# en Modo Desafío -- ver `self.mode == "challenge"` en src/world.py --
# así que si la sesión guiada dejara el juego en el splash/menu (o el
# participante terminara en Modo Clásico), nunca se vería el conteo
# "En rango: N/Total" roto que la Etapa 1 necesita mostrar, ni la
# solución aplicada en la Etapa 6. Por eso, solo en esta copia
# temporal, se salta directo a PlayState en Modo Desafío.
_SNAKE_COVER_CALL = 'self.state_machine.change("cover")'
_SNAKE_CHALLENGE_CALL = 'self.state_machine.change("play", mode="challenge")'


def _force_snake_challenge_mode(game_dir: Path) -> None:
    source_path = game_dir / "src" / "snake_game.py"
    if not source_path.exists():
        raise PatchError("No se encontró src/snake_game.py en la copia del juego.")

    source = source_path.read_text(encoding="utf-8")
    if _SNAKE_COVER_CALL not in source:
        raise PatchError(
            "No se encontró el arranque en 'cover' de SnakeGame -- no se pudo forzar el Modo Desafío."
        )
    source_path.write_text(
        source.replace(_SNAKE_COVER_CALL, _SNAKE_CHALLENGE_CALL, 1), encoding="utf-8",
    )


def _launch_and_cleanup(game_dir: Path) -> None:
    process = launch_game_process(game_dir)

    def _cleanup():
        process.wait()
        shutil.rmtree(game_dir.parent, ignore_errors=True)

    threading.Thread(target=_cleanup, daemon=True).start()


def launch_game_without_solution(game: GameInfo) -> None:
    """Etapa 1: copia el juego TAL CUAL (la función/método del desafío ya
    esta sin resolver en el código fuente real, ver challenges.py) y lo
    lanza, para que el participante vea en vivo la falla real -- el
    mismo TODO/raise que hay en el repo -- antes de leer el enunciado.

    Puede lanzar PatchError (Game-01: no se pudo forzar el Modo Desafío)
    o cualquier excepción de IO/subprocess si algo falla -- el llamador
    debe mostrar el error sin tumbar la sesión guiada.
    """
    game_dir = _copy_game_to_tempdir(game)
    try:
        if game.name == "Game-01":
            _force_snake_challenge_mode(game_dir)
    except Exception:
        shutil.rmtree(game_dir.parent, ignore_errors=True)
        raise
    _launch_and_cleanup(game_dir)


def launch_game_with_solution(game: GameInfo, challenge: Challenge, solution_code: str) -> None:
    """Etapa 6: copia el juego, reemplaza la función/método del desafío por
    el código que generó la IA aislada a partir del prompt del participante
    (Etapa 3) y lo lanza, para observar esa solución concreta en acción.

    Puede lanzar PatchError (código generado inválido, o no calza con la
    firma esperada) o cualquier excepción de IO/subprocess -- el llamador
    debe mostrar el error sin tumbar la sesión guiada.
    """
    relative_file, class_name, func_name = _parse_location(challenge.location)
    game_dir = _copy_game_to_tempdir(game)
    try:
        _apply_solution(game_dir, relative_file, class_name, func_name, solution_code)
        if game.name == "Game-01":
            _force_snake_challenge_mode(game_dir)
    except Exception:
        shutil.rmtree(game_dir.parent, ignore_errors=True)
        raise
    _launch_and_cleanup(game_dir)
