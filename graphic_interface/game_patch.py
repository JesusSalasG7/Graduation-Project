"""Lanza una copia temporal de un juego para las Etapas 1 y 6 de la sesion
guiada: "ver el juego sin la solucion" y "ver el juego con la solucion
hecha" (la funcion/metodo del desafio se reemplaza por el codigo que
genero la IA aislada a partir del prompt del participante, ver
challenge_solver.generate_isolated_response).

La Etapa 1 NO parchea la funcion/metodo del desafio: el codigo fuente real
de cada juego ya deja esa funcion sin resolver (TODO + `raise
NotImplementedError`, ver CHALLENGES en challenges.py), asi que copiarla
tal cual ya alcanza para que el participante vea la falla real -- no una
version sintetica aparte.

Nunca se toca el codigo fuente real del proyecto: se copia la carpeta del
juego a un directorio temporal (sin .venv ni __pycache__), se parchea ahi
adentro con el modulo `ast` (solo para la Etapa 6), se lanza el proceso
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

from challenges import Challenge
from game_launcher import GameInfo, launch_game_process

# Formato de Challenge.location: "archivo.py -> [Clase.]funcion(args)".
_LOCATION_RE = re.compile(
    r"^\s*(?P<file>\S+\.py)\s*->\s*(?:(?P<cls>[A-Za-z_]\w*)\.)?(?P<func>[A-Za-z_]\w*)\s*\("
)


class PatchError(Exception):
    """La funcion/metodo del desafio no se pudo ubicar o reemplazar."""


def _parse_location(location: str) -> tuple[str, Optional[str], str]:
    match = _LOCATION_RE.match(location)
    if not match:
        raise PatchError(f"No se pudo interpretar la ubicación del desafío: {location!r}")
    return match.group("file"), match.group("cls"), match.group("func")


def _find_function_slot(tree: ast.Module, class_name: Optional[str], func_name: str):
    """Devuelve (lista_de_statements, indice) donde vive la funcion/metodo
    a reemplazar: el body del modulo, o el body de la clase indicada.
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
    """Interpreta `solution_code` -- el texto crudo que devolvio la IA
    aislada, se espera una unica definicion de funcion/metodo -- y
    devuelve su nodo FunctionDef, renombrado para calzar con `func_name`.
    """
    try:
        parsed = ast.parse(textwrap.dedent(solution_code))
    except SyntaxError as exc:
        raise PatchError(f"El código generado no es Python válido: {exc}") from exc

    func_node = next(
        (n for n in parsed.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))),
        None,
    )
    if func_node is None:
        raise PatchError("El código generado no contiene ninguna función/método.")
    func_node.name = func_name
    return func_node


def _copy_game_to_tempdir(game: GameInfo) -> Path:
    tmp_root = Path(tempfile.mkdtemp(prefix=f"sesion_guiada_{game.name}_"))
    dest = tmp_root / game.name
    shutil.copytree(
        game.path, dest,
        ignore=shutil.ignore_patterns(".venv", "__pycache__", "*.pyc", ".git"),
    )
    return dest


def _apply_replacement(game_dir: Path, relative_file: str, class_name: Optional[str],
                        func_name: str, replacement_factory) -> None:
    source_path = game_dir / relative_file
    if not source_path.exists():
        raise PatchError(f"No se encontró {relative_file} en la copia del juego.")

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    body, index = _find_function_slot(tree, class_name, func_name)
    replacement = replacement_factory(body[index])
    body[index] = ast.copy_location(replacement, body[index])
    ast.fix_missing_locations(tree)
    source_path.write_text(ast.unparse(tree), encoding="utf-8")


# Game-01 (Snake) arranca por defecto en el estado "cover" (splash) y de
# ahi pasa al menu, donde el jugador elige a mano Modo Clasico o Modo
# Desafio. El desafio A01 (World.count_apples_in_range) SOLO se ejercita
# en Modo Desafio -- ver `self.mode == "challenge"` en src/world.py --
# asi que si la sesion guiada dejara el juego en el splash/menu (o el
# participante terminara en Modo Clasico), nunca se veria el conteo ni
# el bono periodico roto/incompleto que la Etapa 1 necesita mostrar, ni
# la solucion aplicada en la Etapa 6. Por eso, solo en esta copia
# temporal, se salta directo a PlayState en Modo Desafio.
_SNAKE_COVER_CALL = 'self.state_machine.change("cover")'
_SNAKE_CHALLENGE_CALL = 'self.state_machine.change("play", mode="challenge")'


def _force_snake_challenge_mode(game_dir: Path) -> None:
    source_path = game_dir / "src" / "snake_game.py"
    if not source_path.exists():
        raise PatchError("No se encontró src/snake_game.py en la copia del juego.")

    source = source_path.read_text(encoding="utf-8")
    if _SNAKE_COVER_CALL not in source:
        raise PatchError(
            "No se encontró el arranque en 'cover' de SnakeGame -- no se pudo forzar el Modo Desafio."
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
    """Etapa 1: copia el juego TAL CUAL (la funcion/metodo del desafio ya
    esta sin resolver en el codigo fuente real, ver challenges.py) y lo
    lanza, para que el participante vea en vivo la falla real -- el
    mismo TODO/raise que hay en el repo -- antes de leer el enunciado.

    Puede lanzar PatchError (Game-01: no se pudo forzar el Modo Desafio)
    o cualquier excepcion de IO/subprocess si algo falla -- el llamador
    debe mostrar el error sin tumbar la sesion guiada.
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
    """Etapa 6: copia el juego, reemplaza la funcion/metodo del desafio por
    el codigo que genero la IA aislada a partir del prompt del participante
    (Etapa 3) y lo lanza, para observar esa solucion concreta en accion.

    Puede lanzar PatchError (codigo generado invalido, o no calza con la
    firma esperada) o cualquier excepcion de IO/subprocess -- el llamador
    debe mostrar el error sin tumbar la sesion guiada.
    """
    relative_file, class_name, func_name = _parse_location(challenge.location)
    game_dir = _copy_game_to_tempdir(game)
    try:
        _apply_replacement(
            game_dir, relative_file, class_name, func_name,
            lambda _original: _solution_function(func_name, solution_code),
        )
        if game.name == "Game-01":
            _force_snake_challenge_mode(game_dir)
    except Exception:
        shutil.rmtree(game_dir.parent, ignore_errors=True)
        raise
    _launch_and_cleanup(game_dir)
