"""Escaneo dinamico y lanzamiento de los juegos del proyecto.

Los juegos se ejecutan siempre con el interprete del .venv unificado
de la raiz del proyecto, y con cwd en la carpeta del juego (todos
usan imports relativos tipo `import settings` / `from src...`).
"""

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from paths import DATA_DIR, GUI_REQUIREMENTS, PROJECT_ROOT, TOOLS_DIR
from storage.participant_store import participant_file_stub, participant_label

VENV_DIR = PROJECT_ROOT / ".venv"

EMOTION_TRACKER_SCRIPT = TOOLS_DIR / "emotion_tracker.py"
TOOLS_REQUIREMENTS = TOOLS_DIR / "requirements.txt"
# De tools/requirements.txt, SOLO esta seccion va al .venv unificado
# (emotion_tracker.py). Las demas son para venvs propios de tools/ y no
# pueden convivir con esta: la de MediaPipe trae opencv-contrib-python,
# que pisa los archivos de cv2/ de opencv-python (ver el comentario al
# principio de ese archivo).
ROOT_VENV_TOOLS_SECTION = "EMOTION"
EMOTION_LOG_DIR = DATA_DIR / "emotion_logs"

# Titulo declarado como `TITLE = "..."` en settings.py
_TITLE_IN_SETTINGS = re.compile(r'^\s*TITLE\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
# Titulo pasado como primer literal a un constructor tipo `SnakeGame("Snake", ...)`
_TITLE_IN_MAIN = re.compile(r'\w+Game\(\s*["\']([^"\']+)["\']')


def _detect_title(path: Path) -> Optional[str]:
    """Busca el nombre "bonito" del juego sin ejecutarlo (settings.py o main.py)."""
    settings_file = path / "settings.py"
    if settings_file.exists():
        match = _TITLE_IN_SETTINGS.search(settings_file.read_text(encoding="utf-8", errors="ignore"))
        if match:
            return match.group(1)

    main_file = path / "main.py"
    if main_file.exists():
        match = _TITLE_IN_MAIN.search(main_file.read_text(encoding="utf-8", errors="ignore"))
        if match:
            return match.group(1)

    return None


def venv_python() -> Path:
    if sys.platform == "win32":
        candidate = VENV_DIR / "Scripts" / "python.exe"
    else:
        candidate = VENV_DIR / "bin" / "python"
    return candidate if candidate.exists() else Path(sys.executable)


@dataclass
class GameInfo:
    name: str
    display_name: str
    path: Path
    entry_point: Optional[Path]

    @property
    def is_playable(self) -> bool:
        return self.entry_point is not None


def discover_games(root: Path = PROJECT_ROOT) -> list[GameInfo]:
    """Detecta carpetas Game-* con un main.py ejecutable."""
    games = []
    for path in sorted(root.glob("Game-*")):
        if not path.is_dir():
            continue
        entry = path / "main.py"
        title = _detect_title(path)
        games.append(
            GameInfo(
                name=path.name,
                display_name=title or path.name,
                path=path,
                entry_point=entry if entry.exists() else None,
            )
        )
    return games


def open_in_vscode(game: GameInfo) -> None:
    subprocess.Popen(["code", str(game.path)])


# Los 7 juegos extienden gale.game.Game, que abre la ventana con
# `pygame.display.set_mode((window_width, window_height), ...)` -- un
# tamano fijo definido en el settings.py de cada juego, mucho mas chico
# que la pantalla y con su propia relacion de aspecto (algunos, como
# Game-02 y Game-05, son verticales). En vez de tocar cada juego (o el
# paquete `gale` instalado en el .venv, que se reinstala solo con
# "Reparar entorno"), se lanza `main.py` con `-c` para poder parchear
# pygame.display.set_mode ANTES de que el juego llame a set_mode: la
# version parcheada agrega pygame.FULLSCREEN + pygame.SCALED,
# conservando el tamano logico que pidio el juego.
#
# SCALED es clave para no deformar la imagen: hace que SDL centre y
# escale esa resolucion logica a la resolucion real del monitor
# manteniendo la relacion de aspecto (con barras si no coincide), en vez
# de estirarla sin mas -- que es lo que pasaba forzando directamente el
# tamano del escritorio (Game-02 y Game-05, verticales, se veian
# aplastados). El resto del juego -- incluida su propia logica de
# escalado de resolucion virtual -- sigue igual: gale sigue viendo el
# tamano logico via screen.get_size() y reescala su render_surface a eso
# en cada frame, como si no hubiera pantalla completa de por medio.
#
# `python -c` (en vez de pasarle la ruta a main.py) agrega el directorio
# actual a sys.path como hace un script normal, asi que los imports
# relativos de cada juego (`import settings`, `from src...`) funcionan
# igual siempre que el cwd del proceso sea la carpeta del juego.
_FULLSCREEN_BOOTSTRAP = """
import runpy

import pygame

_real_set_mode = pygame.display.set_mode


def _fullscreen_set_mode(size=(0, 0), flags=0, depth=0, *args, **kwargs):
    pygame.display.init()
    return _real_set_mode(
        size, flags | pygame.FULLSCREEN | pygame.SCALED, depth, *args, **kwargs
    )


pygame.display.set_mode = _fullscreen_set_mode
runpy.run_path("main.py", run_name="__main__")
"""


def launch_game_process(game_dir: Path) -> subprocess.Popen:
    """Lanza `main.py` dentro de `game_dir` con el .venv unificado, siempre
    en pantalla completa (ver _FULLSCREEN_BOOTSTRAP). Usado tanto por
    play_game() (boton "Jugar" de la pestaña Juegos) como por
    game_patch._launch_and_cleanup() (Etapas 1 y 6 de la sesion guiada).
    """
    return subprocess.Popen(
        [str(venv_python()), "-c", _FULLSCREEN_BOOTSTRAP], cwd=str(game_dir),
    )


def play_game(game: GameInfo) -> None:
    if not game.is_playable:
        raise FileNotFoundError(f"{game.name} no tiene un main.py ejecutable.")
    launch_game_process(game.path)


def emotion_log_file(participant: dict) -> Path:
    return EMOTION_LOG_DIR / f"{participant_file_stub(participant)}.csv"


def delete_emotion_data(participant: Optional[dict]) -> None:
    """Borra el CSV de emociones capturado para `participant` en esta
    sesion -- se usa cuando la sesion guiada se abandona sin terminar los
    desafios (mismo criterio que neurosky_launcher.delete_neurosky_data):
    datos de una sesion incompleta no sirven para el analisis."""
    if not participant:
        return
    try:
        emotion_log_file(participant).unlink()
    except FileNotFoundError:
        pass


def start_emotion_tracker(participant: Optional[dict], session_label: str) -> subprocess.Popen:
    """Lanza tools/emotion_tracker.py en segundo plano con el .venv unificado,
    con su salida como pipe de texto linea a linea (ver la misma logica en
    neurosky_launcher.start_neurosky_test) para poder mostrarla en vivo en
    la pantalla de configuracion de la sesion guiada.

    Si hay un participante activo, sus lecturas se registran ademas en un
    CSV propio (graphic_interface/data/emotion_logs/<NOMBRE_APELLIDO>.csv)
    para poder correlacionarlas despues con la sesion.
    """
    if not EMOTION_TRACKER_SCRIPT.exists():
        raise FileNotFoundError("No se encontró tools/emotion_tracker.py")

    args = [str(venv_python()), "-u", str(EMOTION_TRACKER_SCRIPT), "--session-label", session_label]

    if participant:
        EMOTION_LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = emotion_log_file(participant)
        args += [
            "--participant-id", participant["id"],
            "--participant-name", participant_label(participant),
            "--log-file", str(log_file),
        ]

    return subprocess.Popen(
        args, cwd=str(TOOLS_DIR),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )


def consolidated_requirements(root: Path = PROJECT_ROOT) -> list[str]:
    """Junta (sin duplicados) las lineas de todos los Game-*/requirements.txt."""
    lines: set[str] = set()
    for req_file in sorted(root.glob("Game-*/requirements.txt")):
        for line in req_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                lines.add(line)
    return sorted(lines)


def tools_requirements_section(name: str, path: Path = TOOLS_REQUIREMENTS) -> list[str]:
    """Lineas de requisito entre `# --<name>-START--` y `# --<name>-END--`
    de tools/requirements.txt (sin comentarios ni lineas vacias)."""
    lines: list[str] = []
    inside = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line == f"# --{name}-START--":
            inside = True
        elif line == f"# --{name}-END--":
            break
        elif inside and line and not line.startswith("#"):
            lines.append(line)
    return lines


def _package_installed(python: Path, package: str) -> bool:
    result = subprocess.run(
        [str(python), "-m", "pip", "show", "-q", package], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return result.returncode == 0


def repair_environment(on_output: Optional[Callable[[str], None]] = None) -> tuple[bool, str]:
    """Reinstala en el .venv unificado las dependencias de todos los juegos, la
    GUI y la seccion de tools/requirements.txt que le corresponde a este venv
    (ROOT_VENV_TOOLS_SECTION) -- nunca el archivo entero.

    Si quedo instalado opencv-contrib-python (versiones anteriores de este
    boton instalaban tools/requirements.txt completo), lo desinstala y
    reinstala opencv-python para restaurar los archivos de cv2/ pisados.

    `on_output`, si se pasa, se llama con cada linea de salida de pip (progreso en vivo).
    Devuelve (exito, log_completo).
    """
    python = venv_python()
    log_lines: list[str] = []

    def run(cmd: list[str]) -> int:
        log_lines.append(f"$ {' '.join(cmd)}")
        if on_output:
            on_output(log_lines[-1])
        process = subprocess.Popen(
            cmd, cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        for line in process.stdout:
            line = line.rstrip()
            log_lines.append(line)
            if on_output:
                on_output(line)
        process.wait()
        return process.returncode

    commands = [[str(python), "-m", "pip", "install", "--upgrade", "pip"]]

    requirements = consolidated_requirements()
    if requirements:
        commands.append([str(python), "-m", "pip", "install"] + requirements)

    tools_requirements = tools_requirements_section(ROOT_VENV_TOOLS_SECTION) if TOOLS_REQUIREMENTS.exists() else []
    if tools_requirements:
        if _package_installed(python, "opencv-contrib-python"):
            commands.append([str(python), "-m", "pip", "uninstall", "-y", "opencv-contrib-python"])
            opencv = [r for r in tools_requirements if re.split(r"[=<>!~ ]", r, 1)[0].lower() == "opencv-python"]
            if opencv:
                commands.append([str(python), "-m", "pip", "install", "--force-reinstall", "--no-deps", *opencv])
        commands.append([str(python), "-m", "pip", "install", *tools_requirements])

    if GUI_REQUIREMENTS.exists():
        commands.append([str(python), "-m", "pip", "install", "-r", str(GUI_REQUIREMENTS)])

    for cmd in commands:
        if run(cmd) != 0:
            return False, "\n".join(log_lines)

    return True, "\n".join(log_lines)
