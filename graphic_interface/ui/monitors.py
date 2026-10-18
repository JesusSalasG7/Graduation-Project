"""Monitor del investigador: dónde se abren las ventanas de monitoreo de
la sesión guiada (datos del NeuroSky, de la cámara, el video del Camera
Tracker y el cronómetro de la sesión), separadas de la pantalla que usa
el participante.

Por defecto es el "monitor 1": el primer monitor externo conectado (el
que no es la pantalla de la laptop: eDP/LVDS/DSI), o el primero de la
lista si no hay ninguno externo. Se puede fijar con la variable
RESEARCHER_MONITOR (en el entorno o en el `.env`): el nombre de la salida
tal como lo muestra `xrandr --listmonitors` (ej. "HDMI-1") o su número
empezando en 1 (en el orden de esa lista).

Los monitores se leen de `xrandr --listmonitors` (también responde bajo
Wayland, vía XWayland, que es donde corren Tk y la ventana de OpenCV).
Si no se puede, se usa la pantalla entera que reporta Tk.
"""

import os
import re
import subprocess
from dataclasses import dataclass
from typing import Optional

from dotenv import dotenv_values

from paths import PROJECT_ROOT

ENV_FILE = PROJECT_ROOT / ".env"
RESEARCHER_MONITOR_ENV = "RESEARCHER_MONITOR"
_INTERNAL_PREFIXES = ("eDP", "LVDS", "DSI")

# " 0: +*HDMI-1 1920/530x1080/300+0+0  HDMI-1"
_MONITOR_RE = re.compile(r"^\s*\d+:\s+\S+\s+(\d+)/\d+x(\d+)/\d+([+-]\d+)([+-]\d+)\s+(\S+)")

# Separación entre las ventanas y con el borde del monitor.
MARGIN = 24


@dataclass(frozen=True)
class Monitor:
    name: str
    x: int
    y: int
    width: int
    height: int


def list_monitors() -> list[Monitor]:
    try:
        output = subprocess.run(
            ["xrandr", "--listmonitors"], capture_output=True, text=True, timeout=3,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    monitors = []
    for line in output.splitlines():
        match = _MONITOR_RE.match(line)
        if match:
            width, height, x, y, name = match.groups()
            monitors.append(Monitor(name, int(x), int(y), int(width), int(height)))
    return monitors


def _configured_monitor() -> str:
    file_values = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}
    return (os.environ.get(RESEARCHER_MONITOR_ENV) or file_values.get(RESEARCHER_MONITOR_ENV) or "").strip()


def researcher_monitor(widget) -> Monitor:
    """`widget` (cualquier widget de Tk) solo se usa para el respaldo sin xrandr."""
    monitors = list_monitors()
    configured = _configured_monitor()
    chosen: Optional[Monitor] = None
    if configured:
        if configured.isdigit():
            index = int(configured) - 1
            chosen = monitors[index] if 0 <= index < len(monitors) else None
        else:
            chosen = next((m for m in monitors if m.name == configured), None)
    if chosen is None:
        external = [m for m in monitors if not m.name.startswith(_INTERNAL_PREFIXES)]
        chosen = (external or monitors or [None])[0]
    if chosen is None:
        chosen = Monitor("pantalla", 0, 0, widget.winfo_screenwidth(), widget.winfo_screenheight())
    return chosen


def corner_position(monitor: Monitor, corner: str, width: int, height: int) -> tuple[int, int]:
    """Esquina (`top-left`, `top-right`, `bottom-left`, `bottom-right`) del
    monitor donde va una ventana de `width`x`height`."""
    left = monitor.x + MARGIN
    right = monitor.x + max(monitor.width - width - MARGIN, 0)
    top = monitor.y + MARGIN
    bottom = monitor.y + max(monitor.height - height - MARGIN, 0)
    x = left if corner.endswith("left") else right
    y = top if corner.startswith("top") else bottom
    return x, y


def fit_height(monitor: Monitor, height: int, rows: int = 2) -> int:
    """`height` recortado para que `rows` ventanas apiladas entren en el
    monitor (el título de cada ventana suma ~40px que Tk no cuenta)."""
    available = (monitor.height - MARGIN * (rows + 1)) // rows - 40
    return min(height, max(available, 200))
