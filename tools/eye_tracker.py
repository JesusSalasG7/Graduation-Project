"""
Eye Tracker - Estimacion de direccion de mirada del desarrollador.

Captura video en tiempo real desde la webcam y usa el Face Landmarker de
MediaPipe (Tasks API, con landmarks de iris) para localizar ambos ojos y
estimar hacia donde esta mirando el participante (izquierda/centro/derecha,
arriba/centro/abajo). Es una estimacion heuristica sin calibracion por
usuario: dibuja el contorno de los ojos y el centro del iris sobre el
video, e informa por terminal y opcionalmente por CSV la direccion
detectada cada N fotogramas.

La primera ejecucion descarga automaticamente el modelo
"face_landmarker.task" (~3.7 MB) de Google y lo guarda en
tools/models/, para no tener que commitear un binario al repositorio.

IMPORTANTE: este script vive en un entorno virtual separado
(tools/.venv-eyetracker, ver tools/requirements-eyetracker.txt) porque
mediapipe requiere opencv-contrib-python, que no puede convivir con
opencv-python (dependencia de deepface, usado por emotion_tracker.py) en
el mismo entorno: ambos paquetes instalan archivos en el mismo directorio
cv2/ y se pisan entre si, dejando cv2 roto.

Controles:
    q  -> salir

Uso:
    python eye_tracker.py [--interval N] [--camera INDEX] [--mirror]
"""

import argparse
import csv
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core.base_options import BaseOptions

DEFAULT_LOG_INTERVAL = 10  # registrar 1 de cada N fotogramas analizados
CSV_FIELDNAMES = [
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

# Umbrales heuristicos sobre la posicion relativa del iris dentro del ojo.
HORIZONTAL_LOW, HORIZONTAL_HIGH = 0.42, 0.58
VERTICAL_LOW, VERTICAL_HIGH = 0.35, 0.65


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
                    csv.DictWriter(f, fieldnames=CSV_FIELDNAMES).writeheader()

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

    def report(self, gaze_x: float, gaze_y: float, direction: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] Mirada detectada: {direction} (x={gaze_x:.2f}, y={gaze_y:.2f})")
        if self.log_file:
            with open(self.log_file, "a", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=CSV_FIELDNAMES).writerow({
                    "timestamp": timestamp,
                    "participant_id": self.participant_id,
                    "participant_name": self.participant_name,
                    "session_label": self.session_label,
                    "gaze_x": f"{gaze_x:.4f}",
                    "gaze_y": f"{gaze_y:.4f}",
                    "gaze_direction": direction,
                })


def _draw_eye_overlay(frame, landmarks, width, height, right_iris, left_iris):
    for idx in RIGHT_EYE_CORNERS + RIGHT_EYE_TOP_BOTTOM + LEFT_EYE_CORNERS + LEFT_EYE_TOP_BOTTOM:
        px = int(landmarks[idx].x * width)
        py = int(landmarks[idx].y * height)
        cv2.circle(frame, (px, py), 1, (0, 255, 0), -1)

    for cx, cy in (right_iris, left_iris):
        cv2.circle(frame, (int(cx), int(cy)), 2, (0, 255, 255), -1)


def main():
    parser = argparse.ArgumentParser(description="Eye Tracker")
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_LOG_INTERVAL,
        help=f"Registrar la mirada cada N frames (default: {DEFAULT_LOG_INTERVAL})",
    )
    parser.add_argument("--camera", type=int, default=0, help="Indice de la camara (default: 0)")
    parser.add_argument(
        "--mirror", action="store_true",
        help="Voltea el frame horizontalmente (vista espejo) antes de estimar la mirada",
    )
    parser.add_argument("--participant-id", default="", help="ID del participante activo (opcional)")
    parser.add_argument("--participant-name", default="", help="Nombre del participante activo (opcional)")
    parser.add_argument("--session-label", default="", help="Etiqueta de la sesion, ej. nombre del juego")
    parser.add_argument(
        "--log-file", default=None,
        help="Ruta de un CSV donde ademas se registra cada lectura (opcional)",
    )
    parser.add_argument(
        "--model-path", default=None,
        help=f"Ruta al modelo face_landmarker.task (default: {MODEL_PATH})",
    )
    args = parser.parse_args()

    estimator = GazeEstimator(
        log_file=Path(args.log_file) if args.log_file else None,
        participant_id=args.participant_id,
        participant_name=args.participant_name,
        session_label=args.session_label,
    )

    model_path = _ensure_model(Path(args.model_path) if args.model_path else MODEL_PATH)
    landmarker = vision.FaceLandmarker.create_from_options(
        vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
        )
    )

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print("Error: no se pudo acceder a la camara.")
        return

    print("Eye Tracker iniciado. Presiona 'q' en la ventana de video para salir.")
    if args.log_file:
        print(f"Registrando lecturas en: {args.log_file}")

    frame_count = 0
    window_name = "Eye Tracker - Vibe Coding"
    start_time = time.monotonic()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: no se pudo leer el frame de la camara.")
                break

            if args.mirror:
                frame = cv2.flip(frame, 1)

            frame_count += 1
            height, width = frame.shape[:2]

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            timestamp_ms = int((time.monotonic() - start_time) * 1000)
            result = landmarker.detect_for_video(mp_image, timestamp_ms)

            if result.face_landmarks:
                landmarks = result.face_landmarks[0]
                gaze_x, gaze_y, direction, right_iris, left_iris = estimator.estimate(landmarks, width, height)
                _draw_eye_overlay(frame, landmarks, width, height, right_iris, left_iris)

                if frame_count % args.interval == 0:
                    estimator.report(gaze_x, gaze_y, direction)

            cv2.imshow(window_name, frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        landmarker.close()
        cap.release()
        cv2.destroyAllWindows()
        print("Eye Tracker detenido.")


if __name__ == "__main__":
    main()
