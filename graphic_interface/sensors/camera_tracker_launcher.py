"""Lanzador del Camera Tracker fusionado (tools/camera_tracker.py):
Emotion Tracker + Eye Tracker sobre UNA sola camara, en un solo proceso
-- ver el docstring de ese script para el motivo (la webcam de esta
configuracion, como la mayoria de las webcams USB, solo admite un
handle de captura abierto a la vez; lanzar los dos scripts viejos por
separado hacia que el segundo en arrancar no pudiera abrir la camara).

Vive en su propio entorno virtual, tools/.venv-tracker (ver la seccion 3
de tools/requirements.txt), separado tanto del .venv unificado de la
raiz como de tools/.venv-eyetracker.

Flujo (ver session_wizard._show_configure_camera_tracker):
    1. run_calibration(...) corre `camera_tracker.py --calibrate`: le
       pide al participante mirar a la izquierda y despues a la derecha,
       y devuelve (left_x, right_x) -- su gaze_x real en cada lado.
    2. start_camera_tracker(...) lanza el seguimiento continuo (mirada +
       emocion) pasandole esos dos valores, para que el corte
       izquierda/derecha quede calibrado a ESE participante, y con un CSV
       propio para cada analisis.
"""

import re
import subprocess
from pathlib import Path
from typing import Callable, Optional

from sensors.eye_tracker_launcher import EYE_LOG_DIR, eye_log_file
from games.game_launcher import EMOTION_LOG_DIR, emotion_log_file
from paths import TOOLS_DIR
from storage.participant_store import participant_label

CAMERA_TRACKER_SCRIPT = TOOLS_DIR / "camera_tracker.py"
CAMERA_TRACKER_VENV_DIR = TOOLS_DIR / ".venv-tracker"

# "CALIBRATION_RESULT left_x=0.6123 right_x=0.3981" (ver camera_tracker.py::run_calibration).
_RESULT_RE = re.compile(r"CALIBRATION_RESULT\s+left_x=([\-0-9.]+)\s+right_x=([\-0-9.]+)")
_FAILED_RE = re.compile(r"CALIBRATION_FAILED\s+reason=(\S+)")

# La calibracion completa (2 fases + su conteo regresivo) dura unos
# 10-12s; este timeout es solo una salvaguarda por si el proceso se
# cuelga (camara que nunca entrega frames, etc.).
CALIBRATION_TIMEOUT_SECONDS = 60


class CalibrationError(Exception):
    """La calibracion no se pudo completar (sin rostro, ventana cerrada, timeout)."""


def camera_tracker_python() -> Path:
    candidate = CAMERA_TRACKER_VENV_DIR / "bin" / "python"
    if not candidate.exists():
        raise FileNotFoundError(
            f"No se encontró el entorno virtual del Camera Tracker en {CAMERA_TRACKER_VENV_DIR} "
            "(ver la seccion 3 de tools/requirements.txt para crearlo)."
        )
    return candidate


def delete_camera_data(participant: Optional[dict]) -> None:
    """Borra los CSV de emocion y de mirada capturados para `participant`
    en esta sesion -- se usa cuando la sesion guiada se abandona sin
    terminar los desafios (mismo criterio que neurosky_launcher.
    delete_neurosky_data): datos de una sesion incompleta no sirven para
    el analisis."""
    if not participant:
        return
    for path in (emotion_log_file(participant), eye_log_file(participant)):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def run_calibration(on_output: Callable[[str], None], mirror: bool = True) -> tuple[float, float]:
    """Corre `camera_tracker.py --calibrate` hasta que termina, mandando
    cada linea de salida a `on_output` (para poder mostrarla en vivo).
    Bloquea al hilo que la llama -- se espera que se dispare desde un
    hilo de fondo, nunca desde el hilo de Tk (ver session_wizard).

    Devuelve (left_x, right_x). Lanza CalibrationError si el proceso
    termina sin imprimir CALIBRATION_RESULT (no se detecto un rostro
    durante alguna fase, se cerro la ventana, timeout, o la camara no
    se pudo abrir).
    """
    if not CAMERA_TRACKER_SCRIPT.exists():
        raise FileNotFoundError("No se encontró tools/camera_tracker.py")

    args = [str(camera_tracker_python()), "-u", str(CAMERA_TRACKER_SCRIPT), "--calibrate"]
    if mirror:
        args.append("--mirror")

    process = subprocess.Popen(
        args, cwd=str(TOOLS_DIR),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )

    result: Optional[tuple[float, float]] = None
    failure_reason: Optional[str] = None
    try:
        for line in process.stdout:
            line = line.rstrip()
            if not line:
                continue
            on_output(line)

            match = _RESULT_RE.search(line)
            if match:
                result = (float(match.group(1)), float(match.group(2)))
                continue
            match = _FAILED_RE.search(line)
            if match:
                failure_reason = match.group(1)
    finally:
        try:
            process.wait(timeout=CALIBRATION_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()

    if result is not None:
        return result
    if failure_reason:
        raise CalibrationError(f"No se detectó un rostro mirando hacia: {failure_reason}.")
    raise CalibrationError("La calibracion se interrumpio antes de terminar.")


def start_camera_tracker(
    participant: Optional[dict], session_label: str, left_x: float, right_x: float, mirror: bool = True,
) -> subprocess.Popen:
    """Lanza el seguimiento continuo (mirada + emocion, un solo proceso,
    una sola camara) con los umbrales calibrados de run_calibration(),
    con su salida como pipe de texto linea a linea para poder mostrarla
    en vivo.

    Si hay un participante activo, sus lecturas se registran ademas en
    dos CSV propios -- graphic_interface/data/emotion_logs/<NOMBRE_
    APELLIDO>.csv y graphic_interface/data/eye_logs/<NOMBRE_APELLIDO>.csv
    -- los mismos que usaban las herramientas separadas.
    """
    if not CAMERA_TRACKER_SCRIPT.exists():
        raise FileNotFoundError("No se encontró tools/camera_tracker.py")

    args = [
        str(camera_tracker_python()), "-u", str(CAMERA_TRACKER_SCRIPT),
        "--session-label", session_label,
        "--left-x", str(left_x), "--right-x", str(right_x),
    ]
    if mirror:
        args.append("--mirror")

    if participant:
        EMOTION_LOG_DIR.mkdir(parents=True, exist_ok=True)
        EYE_LOG_DIR.mkdir(parents=True, exist_ok=True)
        args += [
            "--participant-id", participant["id"],
            "--participant-name", participant_label(participant),
            "--emotion-log-file", str(emotion_log_file(participant)),
            "--eye-log-file", str(eye_log_file(participant)),
        ]

    return subprocess.Popen(
        args, cwd=str(TOOLS_DIR),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
