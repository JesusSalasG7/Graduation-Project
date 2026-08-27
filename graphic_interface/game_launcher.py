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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = PROJECT_ROOT / ".venv"
GUI_REQUIREMENTS = Path(__file__).resolve().parent / "requirements.txt"

TOOLS_DIR = PROJECT_ROOT / "tools"
EMOTION_TRACKER_SCRIPT = TOOLS_DIR / "emotion_tracker.py"
TOOLS_REQUIREMENTS = TOOLS_DIR / "requirements.txt"
EMOTION_LOG_DIR = Path(__file__).resolve().parent / "data" / "emotion_logs"

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


def play_game(game: GameInfo) -> None:
    if not game.is_playable:
        raise FileNotFoundError(f"{game.name} no tiene un main.py ejecutable.")
    subprocess.Popen([str(venv_python()), "main.py"], cwd=str(game.path))


def start_emotion_tracker(participant: Optional[dict], session_label: str) -> subprocess.Popen:
    """Lanza tools/emotion_tracker.py en segundo plano con el .venv unificado.

    Si hay un participante activo, sus lecturas se registran ademas en un
    CSV propio (graphic_interface/data/emotion_logs/<participant_id>.csv)
    para poder correlacionarlas despues con la sesion de juego.
    """
    if not EMOTION_TRACKER_SCRIPT.exists():
        raise FileNotFoundError("No se encontro tools/emotion_tracker.py")

    args = [str(venv_python()), str(EMOTION_TRACKER_SCRIPT), "--session-label", session_label]

    if participant:
        EMOTION_LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = EMOTION_LOG_DIR / f"{participant['id']}.csv"
        args += [
            "--participant-id", participant["id"],
            "--participant-name", f"{participant['nombre']} {participant['apellido']}",
            "--log-file", str(log_file),
        ]

    return subprocess.Popen(args, cwd=str(TOOLS_DIR))


def consolidated_requirements(root: Path = PROJECT_ROOT) -> list[str]:
    """Junta (sin duplicados) las lineas de todos los Game-*/requirements.txt."""
    lines: set[str] = set()
    for req_file in sorted(root.glob("Game-*/requirements.txt")):
        for line in req_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                lines.add(line)
    return sorted(lines)


def repair_environment(on_output: Optional[Callable[[str], None]] = None) -> tuple[bool, str]:
    """Reinstala en el .venv unificado las dependencias de todos los juegos + la GUI.

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

    if TOOLS_REQUIREMENTS.exists():
        commands.append([str(python), "-m", "pip", "install", "-r", str(TOOLS_REQUIREMENTS)])

    if GUI_REQUIREMENTS.exists():
        commands.append([str(python), "-m", "pip", "install", "-r", str(GUI_REQUIREMENTS)])

    for cmd in commands:
        if run(cmd) != 0:
            return False, "\n".join(log_lines)

    return True, "\n".join(log_lines)
