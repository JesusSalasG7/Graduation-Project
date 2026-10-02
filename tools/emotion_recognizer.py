"""
Reconocimiento de emociones faciales con EmotiEffLib, compartido por
camera_tracker.py (sesión guiada) y emotion_tracker.py (versión suelta).

EmotiEffLib (https://github.com/sb-ai-lab/EmotiEffLib, antes HSEmotion)
solo clasifica: NO detecta rostros. Cada script recorta la cara con su
propio detector (landmarks de MediaPipe en camera_tracker.py, Haar cascade
en emotion_tracker.py) y le pasa ese recorte a EmotionAnalyzer.

Modelo: enet_b0_8_va_mtl (EfficientNet-B0 entrenado en AffectNet), en su
versión ONNX -- corre en CPU con onnxruntime, sin PyTorch ni TensorFlow.
En una sola pasada devuelve la probabilidad de 8 emociones y, además,
valencia (que tan positiva/negativa) y arousal (que tan activada), dos
valores continuos aproximadamente en [-1, 1]. La primera vez se descarga
el modelo (~16 MB) a ~/.emotiefflib/.
"""

import csv
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from emotiefflib.facial_analysis import EmotiEffLibRecognizer

MODEL_NAME = "enet_b0_8_va_mtl"
# Mismo orden en que el modelo devuelve las probabilidades (ver
# idx_to_emotion_class en emotiefflib.facial_analysis), en minúsculas.
EMOTION_CATEGORIES = ["anger", "contempt", "disgust", "fear", "happiness", "neutral", "sadness", "surprise"]
EMOTION_CSV_FIELDNAMES = [
    "timestamp", "participant_id", "participant_name", "session_label",
    "emotion", "confidence",
    *(f"pct_{category}" for category in EMOTION_CATEGORIES),
    "valence", "arousal",
]

# Margen que se agrega alrededor de la caja del rostro antes de recortar
# (fracción del lado): el modelo se entrenó con recortes de detector que
# incluyen algo de contorno, no solo el ovalo interno de la cara.
FACE_CROP_MARGIN = 0.1


def crop_face(frame, box, margin: float = FACE_CROP_MARGIN):
    """Recorta `box` = (x, y, w, h) en píxeles, con `margin` extra por lado,
    limitado a los bordes del frame. Devuelve una copia (BGR) o None si el
    recorte queda vacío."""
    height, width = frame.shape[:2]
    x, y, w, h = box
    pad_x, pad_y = int(w * margin), int(h * margin)
    x0, y0 = max(int(x) - pad_x, 0), max(int(y) - pad_y, 0)
    x1, y1 = min(int(x + w) + pad_x, width), min(int(y + h) + pad_y, height)
    if x1 <= x0 or y1 <= y0:
        return None
    return frame[y0:y1, x0:x1].copy()


class EmotionAnalyzer:
    """Ejecuta EmotiEffLib en un hilo aparte para no bloquear el loop de video."""

    def __init__(
        self,
        log_file: Optional[Path] = None,
        participant_id: str = "",
        participant_name: str = "",
        session_label: str = "",
        min_confidence: float = 0.0,
    ):
        self._lock = threading.Lock()
        self._busy = False
        self.log_file = log_file
        self.participant_id = participant_id
        self.participant_name = participant_name
        self.session_label = session_label
        self.min_confidence = min_confidence

        self._recognizer = EmotiEffLibRecognizer(engine="onnx", model_name=MODEL_NAME)
        model_categories = [
            self._recognizer.idx_to_emotion_class[i].lower()
            for i in range(len(self._recognizer.idx_to_emotion_class))
        ]
        if model_categories != EMOTION_CATEGORIES:
            raise RuntimeError(f"Categorias inesperadas del modelo {MODEL_NAME}: {model_categories}")

        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            if not self.log_file.exists():
                with open(self.log_file, "w", newline="", encoding="utf-8") as f:
                    csv.DictWriter(f, fieldnames=EMOTION_CSV_FIELDNAMES).writeheader()

    def analyze_async(self, face_crop):
        """Analiza `face_crop` (BGR, ya recortado) en segundo plano. Con
        None (no se encontró rostro) solo lo informa, sin loguear fila."""
        if face_crop is None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] No se pudo analizar la emoción: no se detectó un rostro.")
            return
        if self._busy:
            return  # ya hay un análisis en curso, se descarta este frame
        with self._lock:
            self._busy = True
        thread = threading.Thread(target=self._analyze, args=(face_crop,), daemon=True)
        thread.start()

    def _log_row(self, timestamp: str, emotion: str, confidence: float, percentages: dict,
                 valence: float, arousal: float):
        if not self.log_file:
            return
        row = {
            "timestamp": timestamp,
            "participant_id": self.participant_id,
            "participant_name": self.participant_name,
            "session_label": self.session_label,
            "emotion": emotion,
            "confidence": f"{confidence:.1f}",
            "valence": f"{valence:.3f}",
            "arousal": f"{arousal:.3f}",
        }
        for category in EMOTION_CATEGORIES:
            row[f"pct_{category}"] = f"{percentages[category]:.1f}"
        with open(self.log_file, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=EMOTION_CSV_FIELDNAMES).writerow(row)

    def _analyze(self, face_crop):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
            _, scores = self._recognizer.predict_emotions(rgb, logits=False)
            scores = np.asarray(scores)[0]
            # Modelo multitarea (_mtl): las primeras 8 columnas son
            # probabilidades (softmax), las 2 últimas valencia y arousal.
            probabilities = scores[:len(EMOTION_CATEGORIES)]
            valence, arousal = float(scores[-2]), float(scores[-1])
            percentages = {c: float(p) * 100 for c, p in zip(EMOTION_CATEGORIES, probabilities)}
            emotion = max(percentages, key=percentages.get)
            confidence = percentages[emotion]

            if confidence < self.min_confidence:
                print(
                    f"[{timestamp}] Emoción incierta "
                    f"(mejor candidata: {emotion} con {confidence:.1f}%, por debajo del umbral)"
                )
                emotion = "incierta"
            else:
                print(
                    f"[{timestamp}] Emoción detectada: {emotion} ({confidence:.1f}%) "
                    f"valencia={valence:+.2f} arousal={arousal:+.2f}"
                )
            self._log_row(timestamp, emotion, confidence, percentages, valence, arousal)
        except Exception as exc:
            print(f"[{timestamp}] No se pudo analizar la emoción: {exc}")
        finally:
            with self._lock:
                self._busy = False
