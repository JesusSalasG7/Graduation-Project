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


def _work_area() -> Optional[tuple[int, int, int, int]]:
    """(x, y, ancho, alto) del área útil del escritorio (sin la barra
    superior ni el dock de GNOME), de `_NET_WORKAREA`. None si no se puede."""
    try:
        output = subprocess.run(
            ["xprop", "-root", "_NET_WORKAREA"], capture_output=True, text=True, timeout=3,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    numbers = [int(n) for n in re.findall(r"\d+", output.partition("=")[2])[:4]]
    return tuple(numbers) if len(numbers) == 4 else None


def usable_area(monitor: Monitor) -> tuple[int, int, int, int]:
    """El monitor recortado al área útil: si no, el gestor de ventanas
    corre las ventanas que caen debajo del dock o de la barra superior y
    terminan tapándose entre sí."""
    x, y, w, h = monitor.x, monitor.y, monitor.width, monitor.height
    area = _work_area()
    if area is not None:
        ax, ay, aw, ah = area
        left, top = max(x, ax), max(y, ay)
        right, bottom = min(x + w, ax + aw), min(y + h, ay + ah)
        if right - left > 400 and bottom - top > 300:
            return left, top, right - left, bottom - top
    return x, y, w, h


# Alto aproximado de la barra de título que agrega el gestor de ventanas:
# la posición que se pide es la del marco, pero el tamaño es el del
# contenido.
TITLE_BAR = 40
GAP = 12

# Ventanas del monitor del investigador.
SLOT_TIMER = "timer"
SLOT_GAZE = "gaze"
SLOT_VIDEO = "video"
SLOT_NEUROSKY = "neurosky"
SLOT_CAMERA_LOG = "camera_log"


def researcher_layout(widget) -> dict[str, tuple[int, int, int, int]]:
    """{ventana: (x, y, ancho, alto)} sobre el monitor del investigador,
    sin superponerse:

        +-----------+---------------------------------+
        |  Sesión   |  Mirada: izquierda o derecha    |
        |  en curso |  (la más grande)                |
        +-----------+----------------+----------------+
        |  Video    |  Datos del     |  Datos de la   |
        |  cámara   |  NeuroSky      |  Cámara        |
        +-----------+----------------+----------------+

    (x, y) es la esquina del marco de la ventana; (ancho, alto) el
    contenido, ya descontada la barra de título."""
    ax, ay, aw, ah = usable_area(researcher_monitor(widget))
    left_w = min(640, (aw - 3 * GAP) // 3)
    right_w = aw - 3 * GAP - left_w
    rows_h = ah - 3 * GAP
    top_h = round(rows_h * 0.46)
    bottom_h = rows_h - top_h
    top_y = ay + GAP
    bottom_y = top_y + top_h + GAP
    left_x = ax + GAP
    right_x = left_x + left_w + GAP
    half_w = (right_w - GAP) // 2
    return {
        SLOT_TIMER: (left_x, top_y, left_w, top_h - TITLE_BAR),
        SLOT_GAZE: (right_x, top_y, right_w, top_h - TITLE_BAR),
        SLOT_VIDEO: (left_x, bottom_y, left_w, bottom_h - TITLE_BAR),
        SLOT_NEUROSKY: (right_x, bottom_y, half_w, bottom_h - TITLE_BAR),
        SLOT_CAMERA_LOG: (right_x + half_w + GAP, bottom_y, right_w - half_w - GAP, bottom_h - TITLE_BAR),
    }


def tk_geometry(slot: tuple[int, int, int, int]) -> str:
    x, y, w, h = slot
    return f"{w}x{h}+{x}+{y}"
