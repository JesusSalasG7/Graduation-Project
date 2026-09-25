"""Lanzador de tools/eye_tracker.py: calibracion izquierda/derecha por
participante y arranque del seguimiento continuo con esa calibracion.

A diferencia del resto de las herramientas (que usan el .venv unificado de
la raiz del proyecto), eye_tracker.py vive en su propio entorno virtual
(tools/.venv-eyetracker) porque mediapipe necesita opencv-contrib-python,
que no puede convivir con opencv-python (la que usa emotion_tracker.py via
emotiefflib) en el mismo entorno -- ver tools/requirements.txt.

Flujo (ver session_wizard._show_configure_eye_tracker):
    1. run_calibration(...) corre `eye_tracker.py --calibrate`: le pide al
       participante mirar a la izquierda y despues a la derecha, y
       devuelve (left_x, right_x) -- su gaze_x real en cada lado.
    2. start_eye_tracker(...) lanza el seguimiento continuo pasandole esos
       dos valores por linea de comandos, para que el corte
       izquierda/derecha quede calibrado a ESE participante en vez de un
       umbral fijo generico.
"""

import re
import subprocess
from pathlib import Path
from typing import Callable, Optional

from paths import DATA_DIR, TOOLS_DIR
from storage.participant_store import participant_file_stub, participant_label

EYE_TRACKER_SCRIPT = TOOLS_DIR / "eye_tracker.py"
EYE_TRACKER_VENV_DIR = TOOLS_DIR / ".venv-eyetracker"
EYE_LOG_DIR = DATA_DIR / "eye_logs"

# "CALIBRATION_RESULT left_x=0.6123 right_x=0.3981" (ver eye_tracker.py::run_calibration).
_RESULT_RE = re.compile(r"CALIBRATION_RESULT\s+left_x=([\-0-9.]+)\s+right_x=([\-0-9.]+)")
_FAILED_RE = re.compile(r"CALIBRATION_FAILED\s+reason=(\S+)")

# La calibracion completa (2 fases + su conteo regresivo, ver
# CALIBRATION_COUNTDOWN_SECONDS/CALIBRATION_RECORD_SECONDS en
# eye_tracker.py) dura unos 10-12s; este timeout es solo una salvaguarda
# por si el proceso se cuelga (camara que nunca entrega frames, etc.).
CALIBRATION_TIMEOUT_SECONDS = 60


class CalibrationError(Exception):
    """La calibracion no se pudo completar (sin rostro, ventana cerrada, timeout)."""


def eye_tracker_python() -> Path:
    candidate = EYE_TRACKER_VENV_DIR / "bin" / "python"
    if not candidate.exists():
        raise FileNotFoundError(
            f"No se encontró el entorno virtual de eye_tracker en {EYE_TRACKER_VENV_DIR} "
            "(ver la seccion 2 de tools/requirements.txt para crearlo)."
        )
    return candidate


def run_calibration(on_output: Callable[[str], None], mirror: bool = True) -> tuple[float, float]:
    """Corre `eye_tracker.py --calibrate` hasta que termina, mandando cada
    linea de salida a `on_output` (para poder mostrarla en vivo). Bloquea
    al hilo que la llama -- se espera que se dispare desde un hilo de
    fondo, nunca desde el hilo de Tk (ver session_wizard).

    Devuelve (left_x, right_x). Lanza CalibrationError si el proceso
    termina sin imprimir CALIBRATION_RESULT (no se detecto un rostro
    durante alguna fase, se cerro la ventana, timeout, o la camara no
    se pudo abrir).
    """
    if not EYE_TRACKER_SCRIPT.exists():
        raise FileNotFoundError("No se encontró tools/eye_tracker.py")

    args = [str(eye_tracker_python()), "-u", str(EYE_TRACKER_SCRIPT), "--calibrate"]
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


def eye_log_file(participant: dict) -> Path:
    return EYE_LOG_DIR / f"{participant_file_stub(participant)}.csv"


def delete_eye_data(participant: Optional[dict]) -> None:
    """Borra el CSV de mirada capturado para `participant` en esta sesion
    -- se usa cuando la sesion guiada se abandona sin terminar los
    desafios (mismo criterio que game_launcher.delete_emotion_data /
    neurosky_launcher.delete_neurosky_data): datos de una sesion
    incompleta no sirven para el analisis."""
    if not participant:
        return
    try:
        eye_log_file(participant).unlink()
    except FileNotFoundError:
        pass


def start_eye_tracker(
    participant: Optional[dict], session_label: str, left_x: float, right_x: float, mirror: bool = True,
) -> subprocess.Popen:
    """Lanza el seguimiento continuo de eye_tracker.py con los umbrales
    calibrados de run_calibration(), con su salida como pipe de texto
    linea a linea (igual que start_neurosky_test/start_emotion_tracker)
    para poder mostrarla en vivo.

    Si hay un participante activo, sus lecturas se registran ademas en un
    CSV propio (graphic_interface/data/eye_logs/<NOMBRE_APELLIDO>.csv).
    """
    if not EYE_TRACKER_SCRIPT.exists():
        raise FileNotFoundError("No se encontró tools/eye_tracker.py")

    args = [
        str(eye_tracker_python()), "-u", str(EYE_TRACKER_SCRIPT),
        "--session-label", session_label,
        "--left-x", str(left_x), "--right-x", str(right_x),
    ]
    if mirror:
        args.append("--mirror")

    if participant:
        EYE_LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = eye_log_file(participant)
        args += [
            "--participant-id", participant["id"],
            "--participant-name", participant_label(participant),
            "--log-file", str(log_file),
        ]

    return subprocess.Popen(
        args, cwd=str(TOOLS_DIR),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
