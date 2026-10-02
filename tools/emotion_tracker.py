"""
Emotion Tracker - Recoleccion de datos emocionales del desarrollador.

Captura video en tiempo real desde la webcam, dibuja un rectángulo
básico sobre el rostro detectado (Haar cascade) y, cada N fotogramas,
recorta la cara más grande y la clasifica con EmotiEffLib en un hilo en
segundo plano (ver emotion_recognizer.py) para no bloquear ni saturar el
feed de video. Por cada lectura registra la emoción dominante con su %
de confianza, el % de cada una de las 8 categorías, y la valencia y el
arousal. Ver --min-confidence.

La emoción detectada (con su % de confianza) se imprime por terminal
junto con una marca de tiempo. No se superpone texto sobre la ventana
de video.

Controles:
    q  -> salir

Uso:
    python emotion_tracker.py [--interval N] [--camera INDEX] [--min-confidence N]
"""

import argparse
from pathlib import Path

import cv2

from emotion_recognizer import EmotionAnalyzer, crop_face

DEFAULT_ANALYSIS_INTERVAL = 20  # analizar 1 de cada N fotogramas
FACE_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"


def main():
    parser = argparse.ArgumentParser(description="Emotion Tracker")
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_ANALYSIS_INTERVAL,
        help=f"Analizar la emoción cada N frames (default: {DEFAULT_ANALYSIS_INTERVAL})",
    )
    parser.add_argument("--camera", type=int, default=0, help="Índice de la cámara (default: 0)")
    parser.add_argument("--participant-id", default="", help="ID del participante activo (opcional)")
    parser.add_argument("--participant-name", default="", help="Nombre del participante activo (opcional)")
    parser.add_argument("--session-label", default="", help="Etiqueta de la sesión, ej. nombre del juego")
    parser.add_argument(
        "--log-file", default=None,
        help="Ruta de un CSV donde además se registra cada lectura (opcional)",
    )
    parser.add_argument(
        "--min-confidence", type=float, default=0.0,
        help="Umbral de confianza (0-100) por debajo del cual se reporta 'incierta' en vez de la emoción (default: 0, sin filtro)",
    )
    args = parser.parse_args()

    face_cascade = cv2.CascadeClassifier(FACE_CASCADE_PATH)
    analyzer = EmotionAnalyzer(
        log_file=Path(args.log_file) if args.log_file else None,
        participant_id=args.participant_id,
        participant_name=args.participant_name,
        session_label=args.session_label,
        min_confidence=args.min_confidence,
    )

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print("Error: no se pudo acceder a la cámara.")
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
                print("Error: no se pudo leer el frame de la cámara.")
                break

            frame_count += 1

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

            # El recorte se toma antes de dibujar el recuadro, para que el
            # modelo no lo vea.
            if frame_count % args.interval == 0:
                face_crop = crop_face(frame, max(faces, key=lambda f: f[2] * f[3])) if len(faces) else None
                analyzer.analyze_async(face_crop)

            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

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
