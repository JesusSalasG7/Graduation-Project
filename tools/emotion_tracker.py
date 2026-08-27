"""
Emotion Tracker - Recoleccion de datos emocionales del desarrollador.

Captura video en tiempo real desde la webcam, dibuja un rectangulo
basico sobre el rostro detectado y, cada N fotogramas, ejecuta un
analisis de emocion dominante con DeepFace en un hilo en segundo
plano para no bloquear ni saturar el feed de video.

La emocion detectada se imprime por terminal junto con una marca de
tiempo. No se superpone texto sobre la ventana de video.

Controles:
    q  -> salir

Uso:
    python emotion_tracker.py [--interval N] [--camera INDEX]
"""

import argparse
import csv
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
from deepface import DeepFace

DEFAULT_ANALYSIS_INTERVAL = 20  # analizar 1 de cada N fotogramas
FACE_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
CSV_FIELDNAMES = ["timestamp", "participant_id", "participant_name", "session_label", "emotion"]


class EmotionAnalyzer:
    """Ejecuta DeepFace en un hilo aparte para no bloquear el loop de video."""

    def __init__(
        self,
        log_file: Optional[Path] = None,
        participant_id: str = "",
        participant_name: str = "",
        session_label: str = "",
    ):
        self._lock = threading.Lock()
        self._busy = False
        self.log_file = log_file
        self.participant_id = participant_id
        self.participant_name = participant_name
        self.session_label = session_label
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            if not self.log_file.exists():
                with open(self.log_file, "w", newline="", encoding="utf-8") as f:
                    csv.DictWriter(f, fieldnames=CSV_FIELDNAMES).writeheader()

    def analyze_async(self, frame):
        if self._busy:
            return  # ya hay un analisis en curso, se descarta este frame
        with self._lock:
            self._busy = True
        frame_copy = frame.copy()
        thread = threading.Thread(target=self._analyze, args=(frame_copy,), daemon=True)
        thread.start()

    def _log_row(self, timestamp: str, emotion: str):
        if not self.log_file:
            return
        with open(self.log_file, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=CSV_FIELDNAMES).writerow({
                "timestamp": timestamp,
                "participant_id": self.participant_id,
                "participant_name": self.participant_name,
                "session_label": self.session_label,
                "emotion": emotion,
            })

    def _analyze(self, frame):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            result = DeepFace.analyze(
                frame,
                actions=["emotion"],
                enforce_detection=False,
                detector_backend="opencv",
                silent=True,
            )
            if isinstance(result, list):
                result = result[0]
            emotion = result.get("dominant_emotion", "desconocida")
            print(f"[{timestamp}] Emocion detectada: {emotion}")
            self._log_row(timestamp, emotion)
        except Exception as exc:  # DeepFace puede fallar si no hay rostro claro
            print(f"[{timestamp}] No se pudo analizar la emocion: {exc}")
        finally:
            with self._lock:
                self._busy = False


def main():
    parser = argparse.ArgumentParser(description="Emotion Tracker")
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_ANALYSIS_INTERVAL,
        help=f"Analizar la emocion cada N frames (default: {DEFAULT_ANALYSIS_INTERVAL})",
    )
    parser.add_argument("--camera", type=int, default=0, help="Indice de la camara (default: 0)")
    parser.add_argument("--participant-id", default="", help="ID del participante activo (opcional)")
    parser.add_argument("--participant-name", default="", help="Nombre del participante activo (opcional)")
    parser.add_argument("--session-label", default="", help="Etiqueta de la sesion, ej. nombre del juego")
    parser.add_argument(
        "--log-file", default=None,
        help="Ruta de un CSV donde ademas se registra cada lectura (opcional)",
    )
    args = parser.parse_args()

    face_cascade = cv2.CascadeClassifier(FACE_CASCADE_PATH)
    analyzer = EmotionAnalyzer(
        log_file=Path(args.log_file) if args.log_file else None,
        participant_id=args.participant_id,
        participant_name=args.participant_name,
        session_label=args.session_label,
    )

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print("Error: no se pudo acceder a la camara.")
        return

    print("Emotion Tracker iniciado. Presiona 'q' en la ventana de video para salir.")
    if args.log_file:
        print(f"Registrando lecturas en: {args.log_file}")

    frame_count = 0
    window_name = "Emotion Tracker - Vibe Coding"

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: no se pudo leer el frame de la camara.")
                break

            frame_count += 1

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            if frame_count % args.interval == 0:
                analyzer.analyze_async(frame)

            cv2.imshow(window_name, frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("Emotion Tracker detenido.")


if __name__ == "__main__":
    main()
