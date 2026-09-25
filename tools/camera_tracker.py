"""
Camera Tracker - Emotion Tracker + Eye Tracker fusionados en UN SOLO
proceso que abre la camara UNA sola vez.

Por que existe: la webcam de este equipo (y la mayoria de las webcams USB
baratas) solo admite un unico proceso con la camara abierta a la vez --
confirmado a mano: lanzar emotion_tracker.py y eye_tracker.py como dos
procesos separados hace que el SEGUNDO en arrancar ni siquiera pueda abrir
la camara (`cap.isOpened()` da False), sin importar el orden. Este script
hace ambos analisis -- emocion dominante via DeepFace, direccion de
mirada izquierda/derecha via MediaPipe -- sobre los mismos frames
capturados por un unico cv2.VideoCapture, evitando la pelea por el
dispositivo.

Vive en su propio entorno virtual, tools/.venv-tracker (ver la seccion 3
de tools/requirements.txt): mediapipe y deepface SI pueden convivir en un
mismo venv, siempre que se instale unicamente opencv-contrib-python (y
NUNCA ademas opencv-python) -- opencv-contrib-python ya incluye todo lo
que deepface necesita de cv2 (cv2.data.haarcascades, etc.), asi que basta
instalar deepface/retina-face con --no-deps para que pip no intente
instalar tambien opencv-python (que pisaria los archivos de cv2/ del
venv y rompe el import, como documentaba el intento original de tener
emotion_tracker.py y eye_tracker.py en un solo venv).

Modos:
    --calibrate            Corre solo la calibracion izquierda/derecha del
                            Eye Tracker (ver run_calibration en
                            eye_tracker.py, misma logica) e imprime
                            CALIBRATION_RESULT/CALIBRATION_FAILED. No usa
                            DeepFace en este modo (mas rapido, no hace
                            falta para calibrar).
    (sin --calibrate)      Seguimiento continuo: Eye Tracker (con
                            --left-x/--right-x si vienen calibrados) +
                            Emotion Tracker, cada uno con su propio CSV.

Controles:
    q  -> salir

Uso:
    python camera_tracker.py --calibrate
    python camera_tracker.py --left-x 0.6 --right-x 0.4 [--emotion-log-file ...] [--eye-log-file ...]
"""

import argparse
import csv
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core.base_options import BaseOptions

from deepface import DeepFace

# ============================================================
# Emotion Tracker (misma logica que emotion_tracker.py)
# ============================================================

DEFAULT_EMOTION_INTERVAL = 30  # analizar 1 de cada N fotogramas (~1 segundo a 30 fps)
FACE_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
# Categorias exactas que devuelve DeepFace.analyze(actions=["emotion"]) en
# result["emotion"] -- se loguea el porcentaje de CADA una (no solo la
# dominante) para que el dataset consolidado (ver data/build_dataset.py)
# pueda reconstruir la distribucion completa de emociones por lectura, no
# solo cual gano.
DEEPFACE_EMOTION_CATEGORIES = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]
EMOTION_CSV_FIELDNAMES = [
    "timestamp", "participant_id", "participant_name", "session_label",
    "emotion", "confidence",
    *(f"pct_{category}" for category in DEEPFACE_EMOTION_CATEGORIES),
]
DEFAULT_DETECTOR_BACKEND = "mtcnn"
DETECTOR_BACKEND_CHOICES = ["opencv", "mtcnn", "retinaface"]


class EmotionAnalyzer:
    """Ejecuta DeepFace en un hilo aparte para no bloquear el loop de video."""

    def __init__(
        self,
        log_file: Optional[Path] = None,
        participant_id: str = "",
        participant_name: str = "",
        session_label: str = "",
        detector_backend: str = DEFAULT_DETECTOR_BACKEND,
        min_confidence: float = 0.0,
    ):
        self._lock = threading.Lock()
        self._busy = False
        self.log_file = log_file
        self.participant_id = participant_id
        self.participant_name = participant_name
        self.session_label = session_label
        self.detector_backend = detector_backend
        self.min_confidence = min_confidence
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            if not self.log_file.exists():
                with open(self.log_file, "w", newline="", encoding="utf-8") as f:
                    csv.DictWriter(f, fieldnames=EMOTION_CSV_FIELDNAMES).writeheader()

    def analyze_async(self, frame):
        if self._busy:
            return  # ya hay un analisis en curso, se descarta este frame
        with self._lock:
            self._busy = True
        frame_copy = frame.copy()
        thread = threading.Thread(target=self._analyze, args=(frame_copy,), daemon=True)
        thread.start()

    def _log_row(self, timestamp: str, emotion: str, confidence: float, all_emotions: Optional[dict] = None):
        if not self.log_file:
            return
        row = {
            "timestamp": timestamp,
            "participant_id": self.participant_id,
            "participant_name": self.participant_name,
            "session_label": self.session_label,
            "emotion": emotion,
            "confidence": f"{confidence:.1f}",
        }
        all_emotions = all_emotions or {}
        for category in DEEPFACE_EMOTION_CATEGORIES:
            row[f"pct_{category}"] = f"{all_emotions.get(category, 0.0):.1f}"
        with open(self.log_file, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=EMOTION_CSV_FIELDNAMES).writerow(row)

    def _analyze(self, frame):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            result = DeepFace.analyze(
                frame,
                actions=["emotion"],
                enforce_detection=True,
                detector_backend=self.detector_backend,
                silent=True,
            )
            if isinstance(result, list):
                result = result[0]
            all_emotions = result.get("emotion", {})
            emotion = result.get("dominant_emotion", "desconocida")
            confidence = all_emotions.get(emotion, 0.0)

            if confidence < self.min_confidence:
                print(
                    f"[{timestamp}] Emoción incierta "
                    f"(mejor candidata: {emotion} con {confidence:.1f}%, por debajo del umbral)"
                )
                self._log_row(timestamp, "incierta", confidence, all_emotions)
            else:
                print(f"[{timestamp}] Emoción detectada: {emotion} ({confidence:.1f}%)")
                self._log_row(timestamp, emotion, confidence, all_emotions)
        except Exception as exc:  # DeepFace puede fallar si no hay rostro claro
            print(f"[{timestamp}] No se pudo analizar la emoción: {exc}")
        finally:
            with self._lock:
                self._busy = False


# ============================================================
# Eye Tracker (misma logica que eye_tracker.py)
# ============================================================

DEFAULT_EYE_INTERVAL = 10  # registrar 1 de cada N fotogramas analizados
EYE_CSV_FIELDNAMES = [
    "timestamp", "participant_id", "participant_name", "session_label",
    "gaze_x", "gaze_y", "gaze_direction",
]

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
MODEL_PATH = Path(__file__).parent / "models" / "face_landmarker.task"

# Indices de landmarks del Face Landmarker de MediaPipe (478 puntos: 468
# del rostro + 10 de iris; misma topologia que el antiguo Face Mesh con
# refine_landmarks=True).
RIGHT_IRIS = [469, 470, 471, 472]
LEFT_IRIS = [474, 475, 476, 477]
RIGHT_EYE_CORNERS = (33, 133)   # esquina externa / interna del ojo derecho
LEFT_EYE_CORNERS = (362, 263)   # esquina interna / externa del ojo izquierdo
RIGHT_EYE_TOP_BOTTOM = (159, 145)  # parpado superior / inferior, ojo derecho
LEFT_EYE_TOP_BOTTOM = (386, 374)   # parpado superior / inferior, ojo izquierdo

# Umbrales heuristicos sobre la posicion relativa del iris dentro del ojo
# (solo alimentan la anotacion "direccion detallada" de la ventana de
# mirada -- lo que realmente se reporta/registra es SideTracker.side).
HORIZONTAL_LOW, HORIZONTAL_HIGH = 0.42, 0.58
VERTICAL_LOW, VERTICAL_HIGH = 0.35, 0.65

SIDE_NAMES = ["izquierda", "derecha"]
SIDE_DEBOUNCE_FRAMES = 3  # frames seguidos del otro lado antes de aceptar el cambio
DEFAULT_SIDE_MIDPOINT = 0.5  # sin calibracion por participante (ver --left-x/--right-x)

# Calibracion izquierda/derecha por participante (ver --calibrate): cada
# fase dura esto, mas un conteo regresivo antes de empezar a grabar para
# darle tiempo al participante de girar la cabeza/ojos.
CALIBRATION_COUNTDOWN_SECONDS = 2.0
CALIBRATION_RECORD_SECONDS = 3.0


def _ensure_model(path: Path) -> Path:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Descargando modelo de Face Landmarker en {path} ...")
        urllib.request.urlretrieve(MODEL_URL, path)
        print("Descarga completa.")
    return path


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _iris_center(landmarks, indices, width, height):
    xs = [landmarks[i].x for i in indices]
    ys = [landmarks[i].y for i in indices]
    cx = sum(xs) / len(xs) * width
    cy = sum(ys) / len(ys) * height
    return cx, cy


def _eye_gaze_ratio(landmarks, corners, top_bottom, iris_center, width, height):
    x1 = landmarks[corners[0]].x * width
    x2 = landmarks[corners[1]].x * width
    y1 = landmarks[top_bottom[0]].y * height
    y2 = landmarks[top_bottom[1]].y * height

    left_x, right_x = min(x1, x2), max(x1, x2)
    top_y, bottom_y = min(y1, y2), max(y1, y2)

    iris_x, iris_y = iris_center
    ratio_x = (iris_x - left_x) / (right_x - left_x) if right_x > left_x else 0.5
    ratio_y = (iris_y - top_y) / (bottom_y - top_y) if bottom_y > top_y else 0.5
    return _clamp01(ratio_x), _clamp01(ratio_y)


def _classify_direction(gaze_x: float, gaze_y: float) -> str:
    if gaze_x < HORIZONTAL_LOW:
        horizontal = "derecha"
    elif gaze_x > HORIZONTAL_HIGH:
        horizontal = "izquierda"
    else:
        horizontal = "centro"

    if gaze_y < VERTICAL_LOW:
        vertical = "arriba"
    elif gaze_y > VERTICAL_HIGH:
        vertical = "abajo"
    else:
        vertical = "centro"

    if horizontal == "centro" and vertical == "centro":
        return "centro"
    parts = [p for p in (vertical, horizontal) if p != "centro"]
    return "-".join(parts)


class GazeEstimator:
    """Estima la direccion de mirada a partir de los landmarks del Face Landmarker."""

    def __init__(
        self,
        log_file: Optional[Path] = None,
        participant_id: str = "",
        participant_name: str = "",
        session_label: str = "",
    ):
        self.log_file = log_file
        self.participant_id = participant_id
        self.participant_name = participant_name
        self.session_label = session_label
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            if not self.log_file.exists():
                with open(self.log_file, "w", newline="", encoding="utf-8") as f:
                    csv.DictWriter(f, fieldnames=EYE_CSV_FIELDNAMES).writeheader()

    def estimate(self, landmarks, width: int, height: int):
        """Devuelve (gaze_x, gaze_y, direction, right_iris_px, left_iris_px)."""
        right_iris = _iris_center(landmarks, RIGHT_IRIS, width, height)
        left_iris = _iris_center(landmarks, LEFT_IRIS, width, height)

        rx, ry = _eye_gaze_ratio(landmarks, RIGHT_EYE_CORNERS, RIGHT_EYE_TOP_BOTTOM, right_iris, width, height)
        lx, ly = _eye_gaze_ratio(landmarks, LEFT_EYE_CORNERS, LEFT_EYE_TOP_BOTTOM, left_iris, width, height)

        gaze_x = (rx + lx) / 2
        gaze_y = (ry + ly) / 2
        direction = _classify_direction(gaze_x, gaze_y)
        return gaze_x, gaze_y, direction, right_iris, left_iris

    def report(self, gaze_x: float, gaze_y: float, side: str):
        """`side` es la decision binaria izquierda/derecha (con debounce,
        ver SideTracker) -- lo unico que hace falta saber del estudio."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] Mirada detectada: {side} (x={gaze_x:.2f}, y={gaze_y:.2f})")
        if self.log_file:
            with open(self.log_file, "a", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=EYE_CSV_FIELDNAMES).writerow({
                    "timestamp": timestamp,
                    "participant_id": self.participant_id,
                    "participant_name": self.participant_name,
                    "session_label": self.session_label,
                    "gaze_x": f"{gaze_x:.4f}",
                    "gaze_y": f"{gaze_y:.4f}",
                    "gaze_direction": side,
                })


class SideTracker:
    """Decide izquierda/derecha a partir de gaze_x, con un debounce chico
    para no alternar por ruido de un solo frame justo en el medio.

    `midpoint` es el punto de corte entre "izquierda" y "derecha": por
    defecto 0.5 (el centro geometrico del ojo), pero se puede calibrar por
    participante con --left-x/--right-x, para que el corte quede centrado
    en SU rango real de movimiento de ojos en vez de asumir que todos
    miran exactamente igual.
    """

    def __init__(self, midpoint: float = DEFAULT_SIDE_MIDPOINT, debounce_frames: int = SIDE_DEBOUNCE_FRAMES):
        self.midpoint = midpoint
        self.debounce_frames = debounce_frames
        self.side = None
        self._pending = None
        self._pending_count = 0

    def update(self, gaze_x: float) -> str:
        # gaze_x bajo = derecha, alto = izquierda (ver _classify_direction).
        candidate = "derecha" if gaze_x < self.midpoint else "izquierda"

        if self.side is None:
            self.side = candidate
        elif candidate == self.side:
            self._pending, self._pending_count = None, 0
        elif self._pending == candidate:
            self._pending_count += 1
            if self._pending_count >= self.debounce_frames:
                self.side = candidate
                self._pending, self._pending_count = None, 0
        else:
            self._pending, self._pending_count = candidate, 1

        return self.side


def _detect_screen_size(default=(1280, 720)):
    """Intenta obtener la resolucion de la pantalla via tkinter (stdlib)."""
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        size = (root.winfo_screenwidth(), root.winfo_screenheight())
        root.destroy()
        return size
    except Exception:
        return default


def _side_rect(name: str, screen_width: int, screen_height: int):
    half_w = screen_width // 2
    if name == "izquierda":
        return 0, 0, half_w, screen_height
    return half_w, 0, screen_width, screen_height


def _draw_side_window(screen_width, screen_height, active_side: str, direction: str):
    canvas = np.zeros((screen_height, screen_width, 3), dtype=np.uint8)

    x1, y1, x2, y2 = _side_rect(active_side, screen_width, screen_height)
    overlay = canvas.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (60, 60, 0), -1)
    cv2.addWeighted(overlay, 0.35, canvas, 0.65, 0, canvas)
    cv2.line(canvas, (screen_width // 2, 0), (screen_width // 2, screen_height), (90, 90, 90), 2)

    cv2.putText(
        canvas, active_side, (screen_width // 2 - 80, screen_height // 2),
        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2,
    )
    cv2.putText(
        canvas, f"direccion detallada: {direction}", (20, screen_height - 20),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1,
    )
    return canvas


def _draw_eye_overlay(frame, landmarks, width, height, right_iris, left_iris):
    for idx in RIGHT_EYE_CORNERS + RIGHT_EYE_TOP_BOTTOM + LEFT_EYE_CORNERS + LEFT_EYE_TOP_BOTTOM:
        px = int(landmarks[idx].x * width)
        py = int(landmarks[idx].y * height)
        cv2.circle(frame, (px, py), 1, (0, 255, 0), -1)

    for cx, cy in (right_iris, left_iris):
        cv2.circle(frame, (int(cx), int(cy)), 2, (0, 255, 255), -1)


# Respaldo para rostros chicos (participante lejos de la camara o poca
# luz): el detector interno del Face Landmarker esta pensado para rostros
# cercanos y a 640x480 pierde uno de ~70 px, aunque el Haar cascade si lo
# encuentra. En ese caso se recorta la zona del rostro que marca Haar y se
# vuelve a correr el Landmarker sobre el recorte (en modo IMAGE, aparte,
# para no mezclar recortes con el seguimiento entre frames del de VIDEO).
FALLBACK_CROP_SCALE = 2.2
_fallback_cascade = None
_fallback_landmarker = None


class _Landmark:
    __slots__ = ("x", "y", "z")

    def __init__(self, x: float, y: float, z: float):
        self.x, self.y, self.z = x, y, z


def _landmarks_from_face_crop(frame, model_path: Path):
    """Landmarks (normalizados al frame completo) buscando primero el
    rostro con Haar y corriendo el Landmarker sobre ese recorte -- None si
    tampoco asi se encuentra."""
    global _fallback_cascade, _fallback_landmarker
    if _fallback_cascade is None:
        _fallback_cascade = cv2.CascadeClassifier(FACE_CASCADE_PATH)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = _fallback_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
    if len(faces) == 0:
        return None

    height, width = frame.shape[:2]
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    side = int(max(w, h) * FALLBACK_CROP_SCALE)
    cx, cy = x + w // 2, y + h // 2
    x0, y0 = max(cx - side // 2, 0), max(cy - side // 2, 0)
    x1, y1 = min(x0 + side, width), min(y0 + side, height)
    crop = frame[y0:y1, x0:x1]
    if crop.size == 0:
        return None

    if _fallback_landmarker is None:
        _fallback_landmarker = vision.FaceLandmarker.create_from_options(
            vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(model_path)),
                running_mode=vision.RunningMode.IMAGE,
            )
        )
    rgb_crop = cv2.cvtColor(np.ascontiguousarray(crop), cv2.COLOR_BGR2RGB)
    result = _fallback_landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_crop))
    if not result.face_landmarks:
        return None

    crop_w, crop_h = x1 - x0, y1 - y0
    return [
        _Landmark((x0 + lm.x * crop_w) / width, (y0 + lm.y * crop_h) / height, lm.z)
        for lm in result.face_landmarks[0]
    ]


def _detect_gaze(landmarker, estimator: GazeEstimator, frame, start_time: float, model_path: Path = MODEL_PATH):
    """Corre el Face Landmarker sobre `frame` y, si detecta un rostro,
    devuelve (landmarks, gaze_x, gaze_y, direction, right_iris, left_iris);
    si no detecta ninguno (ni siquiera con el respaldo de recorte, ver
    _landmarks_from_face_crop), devuelve None. Logica compartida por el
    loop principal y por run_calibration.
    """
    height, width = frame.shape[:2]
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    timestamp_ms = int((time.monotonic() - start_time) * 1000)
    result = landmarker.detect_for_video(mp_image, timestamp_ms)
    if result.face_landmarks:
        landmarks = result.face_landmarks[0]
    else:
        landmarks = _landmarks_from_face_crop(frame, model_path)
        if landmarks is None:
            return None
    gaze_x, gaze_y, direction, right_iris, left_iris = estimator.estimate(landmarks, width, height)
    return landmarks, gaze_x, gaze_y, direction, right_iris, left_iris


def run_calibration(cap, landmarker, mirror: bool, model_path: Path = MODEL_PATH) -> Optional[tuple]:
    """Rutina de calibracion izquierda/derecha por participante -- identica
    a eye_tracker.py::run_calibration. No usa DeepFace: la calibracion es
    corta y solo necesita la mirada.

    Imprime por stdout el resultado en un formato fijo que el lanzador
    (graphic_interface/camera_tracker_launcher.py) sabe parsear:
        CALIBRATION_RESULT left_x=<float> right_x=<float>
        CALIBRATION_FAILED reason=<motivo>
    """
    estimator = GazeEstimator()
    # Sin tilde a proposito: con Qt, getWindowProperty no encuentra una
    # ventana cuyo nombre tiene caracteres no ASCII (devuelve 0) y la
    # calibracion se cortaba al primer frame como si se hubiera cerrado.
    window_name = "Camera Tracker - Calibracion"
    start_time = time.monotonic()

    def run_phase(label: str) -> Optional[float]:
        samples = []
        countdown_start = time.monotonic()
        record_start = None

        while True:
            ret, frame = cap.read()
            if not ret:
                return None

            detected = _detect_gaze(landmarker, estimator, frame, start_time, model_path)
            now = time.monotonic()
            countdown_elapsed = now - countdown_start

            if countdown_elapsed < CALIBRATION_COUNTDOWN_SECONDS:
                remaining = CALIBRATION_COUNTDOWN_SECONDS - countdown_elapsed
                text = f"Prepara la mirada hacia la {label.upper()}... {remaining:.1f}s"
                color = (0, 200, 255)
                recording_done = False
            else:
                if record_start is None:
                    record_start = now
                record_elapsed = now - record_start
                if detected is not None:
                    samples.append(detected[1])  # gaze_x
                remaining = max(CALIBRATION_RECORD_SECONDS - record_elapsed, 0.0)
                text = f"Mirando hacia la {label.upper()} -- {remaining:.1f}s"
                color = (0, 255, 0)
                recording_done = record_elapsed >= CALIBRATION_RECORD_SECONDS

            display_frame = frame.copy()
            if detected is not None:
                landmarks, _, _, _, right_iris, left_iris = detected
                height, width = frame.shape[:2]
                _draw_eye_overlay(display_frame, landmarks, width, height, right_iris, left_iris)
            if mirror:
                display_frame = cv2.flip(display_frame, 1)
            cv2.putText(display_frame, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            cv2.imshow(window_name, display_frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                return None
            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                return None

            if recording_done:
                break

        if not samples:
            return None
        return sum(samples) / len(samples)

    print("Calibración iniciada: primero mirar a la IZQUIERDA, después a la DERECHA.")
    left_x = run_phase("izquierda")
    if left_x is None:
        print("CALIBRATION_FAILED reason=izquierda")
        return None

    right_x = run_phase("derecha")
    if right_x is None:
        print("CALIBRATION_FAILED reason=derecha")
        return None

    print(f"CALIBRATION_RESULT left_x={left_x:.4f} right_x={right_x:.4f}")
    return left_x, right_x


# ============================================================
# main fusionado
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Camera Tracker (Emotion Tracker + Eye Tracker fusionados)")
    parser.add_argument("--camera", type=int, default=0, help="Indice de la cámara (default: 0)")
    parser.add_argument(
        "--mirror", action="store_true",
        help="Voltea el frame horizontalmente (vista espejo) antes de mostrarlo/estimar la mirada",
    )
    parser.add_argument("--participant-id", default="", help="ID del participante activo (opcional)")
    parser.add_argument("--participant-name", default="", help="Nombre del participante activo (opcional)")
    parser.add_argument("--session-label", default="", help="Etiqueta de la sesion, ej. nombre del juego")

    # Eye Tracker
    parser.add_argument(
        "--eye-interval", type=int, default=DEFAULT_EYE_INTERVAL,
        help=f"Registrar la mirada cada N frames (default: {DEFAULT_EYE_INTERVAL})",
    )
    parser.add_argument("--eye-log-file", default=None, help="CSV donde registrar cada lectura de mirada (opcional)")
    parser.add_argument(
        "--model-path", default=None,
        help=f"Ruta al modelo face_landmarker.task (default: {MODEL_PATH})",
    )
    parser.add_argument(
        "--calibrate", action="store_true",
        help=(
            "Corre solo la calibracion izquierda/derecha del Eye Tracker (sin Emotion "
            "Tracker) e imprime CALIBRATION_RESULT/CALIBRATION_FAILED."
        ),
    )
    parser.add_argument(
        "--left-x", type=float, default=None,
        help="gaze_x calibrado para 'mirando a la izquierda' (de una corrida previa con --calibrate).",
    )
    parser.add_argument(
        "--right-x", type=float, default=None,
        help="gaze_x calibrado para 'mirando a la derecha' (de una corrida previa con --calibrate).",
    )

    # Emotion Tracker
    parser.add_argument(
        "--emotion-interval", type=int, default=DEFAULT_EMOTION_INTERVAL,
        help=f"Analizar la emoción cada N frames (default: {DEFAULT_EMOTION_INTERVAL})",
    )
    parser.add_argument("--emotion-log-file", default=None, help="CSV donde registrar cada emocion (opcional)")
    parser.add_argument(
        "--detector-backend", default=DEFAULT_DETECTOR_BACKEND, choices=DETECTOR_BACKEND_CHOICES,
        help=f"Detector de rostro para el analisis de emocion (default: {DEFAULT_DETECTOR_BACKEND}).",
    )
    parser.add_argument(
        "--min-confidence", type=float, default=0.0,
        help="Umbral de confianza (0-100) por debajo del cual se reporta 'incierta' (default: 0, sin filtro)",
    )
    args = parser.parse_args()

    model_path = _ensure_model(Path(args.model_path) if args.model_path else MODEL_PATH)
    landmarker = vision.FaceLandmarker.create_from_options(
        vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
        )
    )

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print("Error: no se pudo acceder a la cámara.")
        return

    if args.calibrate:
        try:
            run_calibration(cap, landmarker, args.mirror, model_path)
        finally:
            landmarker.close()
            cap.release()
            cv2.destroyAllWindows()
        return

    eye_estimator = GazeEstimator(
        log_file=Path(args.eye_log_file) if args.eye_log_file else None,
        participant_id=args.participant_id,
        participant_name=args.participant_name,
        session_label=args.session_label,
    )
    emotion_analyzer = EmotionAnalyzer(
        log_file=Path(args.emotion_log_file) if args.emotion_log_file else None,
        participant_id=args.participant_id,
        participant_name=args.participant_name,
        session_label=args.session_label,
        detector_backend=args.detector_backend,
        min_confidence=args.min_confidence,
    )
    face_cascade = cv2.CascadeClassifier(FACE_CASCADE_PATH)

    print("Camera Tracker iniciado (Emotion + Eye). Presiona 'q' en la ventana de video para salir.")
    if args.eye_log_file:
        print(f"Registrando mirada en: {args.eye_log_file}")
    if args.emotion_log_file:
        print(f"Registrando emociones en: {args.emotion_log_file}")

    frame_count = 0
    window_name = "Camera Tracker - Vibe Coding"
    side_window_name = "Mirada: izquierda o derecha"
    screen_width, screen_height = _detect_screen_size()

    cv2.namedWindow(side_window_name, cv2.WINDOW_NORMAL)

    # Si vinieron los dos umbrales calibrados (ver --calibrate), el corte
    # izquierda/derecha queda centrado en el rango real de movimiento de
    # ESE participante en vez del 0.5 fijo -- ver SideTracker.
    if args.left_x is not None and args.right_x is not None:
        side_midpoint = (args.left_x + args.right_x) / 2
        print(f"Usando calibracion: left_x={args.left_x:.4f} right_x={args.right_x:.4f} (midpoint={side_midpoint:.4f})")
    else:
        side_midpoint = DEFAULT_SIDE_MIDPOINT

    side_tracker = SideTracker(midpoint=side_midpoint)
    side_times = {name: 0.0 for name in SIDE_NAMES}
    last_tick = time.monotonic()
    start_time = time.monotonic()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: no se pudo leer el frame de la cámara.")
                break

            now = time.monotonic()
            dt = now - last_tick
            last_tick = now

            frame_count += 1

            # La deteccion siempre corre sobre el frame "crudo" (sin
            # espejo): si se voltea antes, izquierda/derecha quedan
            # invertidas respecto a la mirada real. El volteo (--mirror)
            # se aplica solo al final, unicamente para la ventana de
            # video, despues de dibujar los overlays sobre el frame crudo.
            detected = _detect_gaze(landmarker, eye_estimator, frame, start_time, model_path)
            if detected is not None:
                landmarks, gaze_x, gaze_y, direction, right_iris, left_iris = detected
                height, width = frame.shape[:2]
                _draw_eye_overlay(frame, landmarks, width, height, right_iris, left_iris)

                side = side_tracker.update(gaze_x)
                side_times[side] += dt
                side_canvas = _draw_side_window(screen_width, screen_height, side, direction)
                cv2.imshow(side_window_name, side_canvas)

                if frame_count % args.eye_interval == 0:
                    eye_estimator.report(gaze_x, gaze_y, side)

            # Deteccion de rostro (Haar cascade, liviana) para el recuadro
            # verde + disparo del analisis de emocion -- independiente de
            # si MediaPipe encontro landmarks arriba (son dos detectores
            # distintos sobre el mismo frame).
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            if frame_count % args.emotion_interval == 0:
                emotion_analyzer.analyze_async(frame)

            if args.mirror:
                frame = cv2.flip(frame, 1)
            cv2.imshow(window_name, frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        landmarker.close()
        cap.release()
        cv2.destroyAllWindows()

        total_time = sum(side_times.values())
        print("\nTiempo de mirada por lado:")
        for name in SIDE_NAMES:
            t = side_times[name]
            pct = (t / total_time * 100) if total_time > 0 else 0.0
            print(f"  {name}: {t:.2f} s ({pct:.1f}%)")
        print(f"  total registrado: {total_time:.2f} s")

        print("Camera Tracker detenido.")


if __name__ == "__main__":
    main()
