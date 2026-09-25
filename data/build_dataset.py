"""Consolida en un unico CSV todos los datos crudos que la sesion guiada ya
exporta por participante/desafio/etapa en el Escritorio (ver
graphic_interface/storage/stage_capture.py): NeuroSky crudo (bandas EEG,
atencion/meditacion), Emotion Tracker (emocion dominante + el porcentaje de
CADA categoria que devuelve DeepFace, ver tools/camera_tracker.py), Eye
Tracker (mirada cruda + miradas izquierda/derecha agregadas), frecuencia
cardiaca del reloj, y el resultado de los cuestionarios -- una fila por
(participante, desafio, etapa, intento), con listas de lecturas crudas en
las columnas "*_List" (mismo criterio que el dataset de referencia
Data_Completa_Editada.csv que se uso como modelo).

No incluye nombre/apellido de los participantes a proposito: ese registro
vive deliberadamente FUERA del proyecto (ver
graphic_interface/storage/personal_records.py) para no mezclar datos personales con
los datos anonimos de la sesion -- este dataset respeta esa misma
separacion y solo identifica a cada participante por su numero. El nivel de
experiencia del jugador (Avanzado/Intermedio/Principiante, elegido al
registrarlo) si se incluye: se lee de graphic_interface/data/participants.json
y queda vacio si ese participante ya no esta registrado ahi.

Una sesion vieja (grabada antes de agregar el desglose de emociones por
categoria) simplemente no tiene esas columnas -- quedan vacias en vez de
romper la generacion del dataset.

Uso:
    python data/build_dataset.py [--out data/dataset_sesiones.csv]

Tambien se puede llamar programaticamente (ver graphic_interface/ui/app.py,
seccion "Dataset consolidado" de la pestaña Sesion):
    from build_dataset import build_dataset, save_dataset
    df = build_dataset()
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

GRAPHIC_INTERFACE_DIR = Path(__file__).resolve().parent.parent / "graphic_interface"
if str(GRAPHIC_INTERFACE_DIR) not in sys.path:
    sys.path.insert(0, str(GRAPHIC_INTERFACE_DIR))

from ai.challenge_solver import GUIDED_SESSION_GAME_ORDER  # noqa: E402
from storage.stage_capture import GUIDED_SESSION_STAGE_ORDER, list_stage_attempts, sessions_root  # noqa: E402

DEFAULT_OUTPUT = Path(__file__).resolve().parent / "dataset_sesiones.csv"
PARTICIPANTS_FILE = GRAPHIC_INTERFACE_DIR / "data" / "participants.json"

# Mismas categorias que devuelve DeepFace.analyze(actions=["emotion"]) --
# ver tools/camera_tracker.py::DEEPFACE_EMOTION_CATEGORIES.
EMOTION_CATEGORIES = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]

_PARTICIPANT_NUMBER_RE = re.compile(r"_(\d+)$")
_CHALLENGE_DIR_RE = re.compile(r"^Desafio_(\d+)$")


def _participant_number(folder_name: str) -> Optional[int]:
    match = _PARTICIPANT_NUMBER_RE.search(folder_name)
    return int(match.group(1)) if match else None


def _read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (pd.errors.EmptyDataError, OSError, pd.errors.ParserError):
        return pd.DataFrame()


def _read_json_safe(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _list_str(values) -> str:
    """"[1, 2, 3]" a partir de una lista/Series -- mismo formato que usa el
    dataset de referencia (Data_Completa_Editada.csv) en sus columnas
    "*_List"."""
    return str(list(values))


def _round_mean(values: "pd.Series"):
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    return round(numeric.mean(), 1) if not numeric.empty else ""


def _experience_by_participant() -> dict[int, str]:
    """{numero de participante: nivel de experiencia} a partir del registro
    anonimo de participants.json (ver graphic_interface/storage/participant_store.py)."""
    payload = _read_json_safe(PARTICIPANTS_FILE)
    return {
        p["number"]: p.get("attributes", {}).get("nivel_experiencia", "")
        for p in payload.get("participants", [])
        if isinstance(p, dict) and "number" in p
    }


# ============================================================
# Una funcion por fuente de datos -- cada una devuelve {} si esa fuente no
# tiene nada que aportar en esta etapa (dispositivo no usado, sesion vieja
# sin esa columna, etc.), nunca lanza.
# ============================================================

def _timing_columns(stage_folder: Path) -> dict:
    payload = _read_json_safe(stage_folder / "sync_timeline.json")
    started, ended = payload.get("stage_started_at"), payload.get("stage_ended_at")
    duration = ""
    try:
        if started and ended:
            duration = round((datetime.fromisoformat(ended) - datetime.fromisoformat(started)).total_seconds(), 1)
    except ValueError:
        pass
    return {"Hora_Inicio": started or "", "Hora_Fin": ended or "", "Duracion_Segundos": duration}


def _neurosky_columns(stage_folder: Path) -> dict:
    df = _read_csv_safe(stage_folder / "neurosky.csv")
    if df.empty:
        return {}
    band_columns = {
        "Attention": "NeuroSky_Attention", "Meditation": "NeuroSky_Meditation",
        "Delta": "NeuroSky_Delta", "Theta": "NeuroSky_Theta",
        "Low_Alpha": "NeuroSky_LowAlpha", "High_Alpha": "NeuroSky_HighAlpha",
        "Low_Beta": "NeuroSky_LowBeta", "High_Beta": "NeuroSky_HighBeta",
        "Low_Gamma": "NeuroSky_LowGamma", "Mid_Gamma": "NeuroSky_MidGamma",
        "Poor_Signal": "NeuroSky_PoorSignal",
    }
    cols = {}
    for source_col, prefix in band_columns.items():
        if source_col not in df.columns:
            continue
        cols[f"{prefix}_List"] = _list_str(df[source_col].tolist())
    cols["NeuroSky_Attention_Promedio"] = _round_mean(df.get("Attention", pd.Series(dtype=float)))
    cols["NeuroSky_Meditation_Promedio"] = _round_mean(df.get("Meditation", pd.Series(dtype=float)))
    return cols


def _emotion_columns(stage_folder: Path) -> dict:
    df = _read_csv_safe(stage_folder / "emotion_tracker.csv")
    if df.empty:
        return {}
    cols = {
        "Emotion_List": _list_str(df.get("emotion", pd.Series(dtype=str)).tolist()),
        "Emotion_Confidence_List": _list_str(pd.to_numeric(df.get("confidence"), errors="coerce").tolist())
        if "confidence" in df.columns else "[]",
    }
    for category in EMOTION_CATEGORIES:
        source_col = f"pct_{category}"
        label = category.capitalize()
        if source_col in df.columns:
            values = pd.to_numeric(df[source_col], errors="coerce")
            cols[f"Emotion_Pct_{label}_List"] = _list_str(values.tolist())
            cols[f"Emotion_Pct_{label}_Promedio"] = _round_mean(values)
        else:
            # Sesion capturada antes de agregar el desglose por categoria.
            cols[f"Emotion_Pct_{label}_List"] = ""
            cols[f"Emotion_Pct_{label}_Promedio"] = ""
    return cols


def _eye_columns(stage_folder: Path) -> dict:
    cols = {}
    raw = _read_csv_safe(stage_folder / "eye_tracker.csv")
    if not raw.empty:
        cols["Eye_Gaze_Direction_List"] = _list_str(raw.get("gaze_direction", pd.Series(dtype=str)).tolist())
        cols["Eye_Gaze_X_List"] = _list_str(pd.to_numeric(raw.get("gaze_x"), errors="coerce").tolist()) \
            if "gaze_x" in raw.columns else "[]"
        cols["Eye_Gaze_Y_List"] = _list_str(pd.to_numeric(raw.get("gaze_y"), errors="coerce").tolist()) \
            if "gaze_y" in raw.columns else "[]"

    looks = _read_csv_safe(stage_folder / "eye_tracker_miradas.csv")
    for direction, label in (("izquierda", "Izq"), ("derecha", "Der")):
        if looks.empty or "direction" not in looks.columns:
            continue
        rows = looks[looks["direction"] == direction]
        cols[f"Eye_Mirada_{label}_Cantidad"] = len(rows)
        cols[f"Eye_Mirada_{label}_Duracion_Total"] = (
            round(rows["duration_seconds"].sum(), 1) if not rows.empty else 0.0
        )
    return cols


def _heart_rate_columns(stage_folder: Path) -> dict:
    df = _read_csv_safe(stage_folder / "heart_rate.csv")
    if df.empty:
        return {}
    cols = {}
    ts_col = "com.samsung.health.heart_rate.start_time"
    hr_col = "com.samsung.health.heart_rate.heart_rate"
    if ts_col in df.columns:
        cols["HeartRate_Timestamps_List"] = _list_str(df[ts_col].tolist())
    if hr_col in df.columns:
        values = pd.to_numeric(df[hr_col], errors="coerce")
        cols["HeartRate_BPM_List"] = _list_str(values.tolist())
        cols["HeartRate_BPM_Promedio"] = _round_mean(values)
    cols["HeartRate_Aproximado"] = bool(
        df.get("is_fallback_reading", pd.Series(dtype=bool)).fillna(False).any()
    )
    return cols


def _cuestionario_columns(stage_folder: Path) -> dict:
    path = stage_folder / "cuestionario.txt"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    correct = text.count("¿Correcto?: Si")
    total = correct + text.count("¿Correcto?: No")
    if total == 0:
        return {}
    return {"Cuestionario_Correctas": correct, "Cuestionario_Total": total}


def _stage3_columns(stage_folder: Path) -> dict:
    cols = {}
    prompt_path = stage_folder / "escrito_etapa3.txt"
    if prompt_path.exists():
        try:
            cols["Prompt_Escrito"] = prompt_path.read_text(encoding="utf-8")
        except OSError:
            pass
    df = _read_csv_safe(stage_folder / "registro_enunciado.csv")
    if not df.empty:
        cols["Enunciado_Aperturas"] = len(df)
        cols["Enunciado_Duracion_Total"] = round(
            pd.to_numeric(df.get("duration_seconds"), errors="coerce").fillna(0).sum(), 1,
        )
    return cols


def _device_status_columns(stage: int, stage_status: dict) -> dict:
    hr_warnings = stage_status.get("heart_rate_warnings", {}).get(str(stage), [])
    return {
        "Dispositivo_HeartRate_Estado": stage_status.get("heart_rate", ""),
        "HeartRate_Advertencias": "; ".join(hr_warnings) if hr_warnings else "",
    }


def _build_row(
    participant_number: int, experience_level: str, challenge_number: int, game_name: str,
    stage: int, attempt: int, stage_folder: Path, stage_status: dict,
) -> dict:
    row = {
        "Participante_ID": participant_number,
        "Nivel_Experiencia": experience_level,
        "Desafio": challenge_number,
        "Juego": game_name,
        "Etapa": stage,
        "Intento": attempt,
    }
    row.update(_timing_columns(stage_folder))
    row.update(_neurosky_columns(stage_folder))
    row.update(_emotion_columns(stage_folder))
    row.update(_eye_columns(stage_folder))
    row.update(_heart_rate_columns(stage_folder))
    row.update(_device_status_columns(stage, stage_status))
    if stage in (2, 4, 5):
        row.update(_cuestionario_columns(stage_folder))
    elif stage == 3:
        row.update(_stage3_columns(stage_folder))
    return row


def build_dataset() -> pd.DataFrame:
    """Recorre ~/Escritorio/Sesiones_participantes/ entero y arma el
    dataset consolidado en memoria -- nunca lanza (una carpeta corrupta o
    incompleta simplemente aporta columnas vacias en esa fila, ver cada
    _*_columns de arriba)."""
    rows = []
    root = sessions_root()
    if not root.is_dir():
        return pd.DataFrame()
    experience_levels = _experience_by_participant()

    for participant_dir in sorted(root.iterdir()):
        if not participant_dir.is_dir():
            continue
        participant_number = _participant_number(participant_dir.name)
        if participant_number is None:
            continue
        experience_level = experience_levels.get(participant_number, "")

        for challenge_dir in sorted(participant_dir.glob("Desafio_*")):
            match = _CHALLENGE_DIR_RE.match(challenge_dir.name)
            if not match:
                continue
            challenge_number = int(match.group(1))
            game_name = (
                GUIDED_SESSION_GAME_ORDER[challenge_number - 1]
                if 1 <= challenge_number <= len(GUIDED_SESSION_GAME_ORDER) else ""
            )
            manifest = _read_json_safe(challenge_dir / "resumen_desafio.json")
            stage_status = manifest.get("stages", {})

            for stage in GUIDED_SESSION_STAGE_ORDER:
                attempts = list_stage_attempts(challenge_dir, stage)
                stage_root = challenge_dir / f"Etapa_{stage}"
                if attempts:
                    for attempt in attempts:
                        stage_folder = stage_root / f"intento_{attempt}"
                        rows.append(_build_row(
                            participant_number, experience_level, challenge_number, game_name,
                            stage, attempt, stage_folder, stage_status,
                        ))
                elif stage_root.is_dir():
                    rows.append(_build_row(
                        participant_number, experience_level, challenge_number, game_name,
                        stage, 1, stage_root, stage_status,
                    ))

    return pd.DataFrame(rows)


def save_dataset(output_path: Path = DEFAULT_OUTPUT) -> tuple[pd.DataFrame, Path]:
    df = build_dataset()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return df, output_path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUTPUT,
        help=f"Ruta del CSV de salida (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    df, path = save_dataset(args.out)
    print(f"Dataset generado: {len(df)} filas x {len(df.columns)} columnas -> {path}")


if __name__ == "__main__":
    main()
