"""Corte por etapa de la sesion guiada: nombrado de carpetas en el
Escritorio, recorte por rango de tiempo (pandas) de los CSV continuos que
ya escriben NeuroSky y el Camera Tracker (Emotion + Eye), agregacion de
miradas izquierda/derecha, y escritores de los archivos por etapa/desafio.

Estos CSV se capturan en subprocesos externos que corren durante TODA la
sesion guiada (ver neurosky_launcher.py / camera_tracker_launcher.py) --
este modulo no toca esos procesos, solo relee los archivos que ya estan en
disco y los recorta por el rango [inicio, fin] de cada etapa.
"""

import csv
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from personal_records import load_personal_record
from quiz import QuizQuestion

SESSIONS_DIR_NAME = "Sesiones_participantes"

# Unicas etapas que capturan datos (ver session_wizard._export_stage /
# _save_stage3_files) -- la 1 y la 6 son solo transicion/demostracion, sin
# nada que exportar. Orden en el que ocurren durante la sesion.
GUIDED_SESSION_STAGE_ORDER = [2, 3, 4, 5]

_UNSAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9_-]+")


def sanitize_component(text: str) -> str:
    """Normaliza un componente de nombre de archivo/carpeta: sin tildes, sin
    espacios ni caracteres invalidos en distintos sistemas de archivos."""
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.strip().replace(" ", "_")
    normalized = _UNSAFE_CHARS_RE.sub("_", normalized)
    return normalized.strip("_") or "SinNombre"


def participant_folder_name(participant: dict) -> str:
    """"Nombre_Apellido_N" usando el registro personal ya cargado al crear
    el participante (ver personal_records.py) -- si no existe (participante
    viejo sin registro), cae a "Participante_N"."""
    number = participant["number"]
    record = load_personal_record(number)
    if record:
        nombre, apellido = record
        return f"{sanitize_component(nombre)}_{sanitize_component(apellido)}_{number}"
    return f"Participante_{number}"


def sessions_root() -> Path:
    return Path.home() / "Escritorio" / SESSIONS_DIR_NAME


def participant_session_dir(participant: dict) -> Path:
    path = sessions_root() / participant_folder_name(participant)
    path.mkdir(parents=True, exist_ok=True)
    return path


def challenge_dir(participant: dict, challenge_number: int) -> Path:
    path = participant_session_dir(participant) / f"Desafio_{challenge_number}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def challenge_dir_readonly(participant: dict, challenge_number: int) -> Path:
    """Igual que challenge_dir pero sin crear ninguna carpeta -- para
    lecturas (p.ej. la matriz de datos guardados en la pestaña Sesión, ver
    app.py) que no deben dejar rastro en disco por el solo hecho de
    mirar un desafío que todavia no tiene datos."""
    return sessions_root() / participant_folder_name(participant) / f"Desafio_{challenge_number}"


def list_stage_attempts(challenge_folder: Path, stage_number: int) -> list[int]:
    """Numeros de intento ya exportados para esta etapa (ver stage_dir),
    ordenados -- vacio si la etapa nunca se re-hizo (o no tiene datos)."""
    stage_folder = challenge_folder / f"Etapa_{stage_number}"
    if not stage_folder.is_dir():
        return []
    attempts = []
    for child in stage_folder.iterdir():
        if child.is_dir() and child.name.startswith("intento_"):
            try:
                attempts.append(int(child.name.removeprefix("intento_")))
            except ValueError:
                continue
    return sorted(attempts)


def resolve_stage_folder(challenge_folder: Path, stage_number: int, attempt: Optional[int] = None) -> Optional[Path]:
    """Encuentra, para lectura (ventana de resumen), la carpeta de una etapa
    ya exportada -- resuelve al ultimo intento por defecto si la etapa esta
    versionada, o a la carpeta directa si nunca se reintento. None si no hay
    nada exportado todavia."""
    stage_folder = challenge_folder / f"Etapa_{stage_number}"
    attempts = list_stage_attempts(challenge_folder, stage_number)
    if attempts:
        chosen = attempt if attempt in attempts else attempts[-1]
        return stage_folder / f"intento_{chosen}"
    return stage_folder if stage_folder.is_dir() else None


def stage_dir(participant: dict, challenge_number: int, stage_number: int, attempt: Optional[int] = None) -> Path:
    """Carpeta de una etapa. Las etapas 3/4/5 se re-hacen si el participante
    reintenta el desafio (ver session_wizard._show_stage4/5/6 "Reintentar
    este desafio"): si se pasa `attempt` (> 1, o siempre para no perder el
    primer intento) se versiona en una subcarpeta "intento_N" en vez de
    pisar la exportacion anterior."""
    base = challenge_dir(participant, challenge_number) / f"Etapa_{stage_number}"
    if attempt is not None:
        base = base / f"intento_{attempt}"
    base.mkdir(parents=True, exist_ok=True)
    return base


# ============================================================
# Cronometraje de etapas
# ============================================================

@dataclass
class StageWindow:
    stage: int
    started_at: datetime
    ended_at: Optional[datetime] = None


class StageTimer:
    """Guarda el inicio/fin de cada etapa (en memoria, vive en
    SessionWizard) para poder recortar por rango de tiempo los CSV
    continuos al exportar."""

    def __init__(self):
        self._windows: dict[int, StageWindow] = {}

    def start(self, stage: int) -> None:
        self._windows[stage] = StageWindow(stage=stage, started_at=datetime.now())

    def finish(self, stage: int) -> StageWindow:
        window = self._windows.get(stage)
        if window is None:
            # No se llamo a start() (p.ej. se entro a la etapa por otro
            # camino) -- se usa el instante actual como inicio y fin, mejor
            # una ventana de 0 segundos que reventar la exportacion.
            now = datetime.now()
            window = StageWindow(stage=stage, started_at=now, ended_at=now)
            self._windows[stage] = window
            return window
        window.ended_at = datetime.now()
        return window

    def window(self, stage: int) -> Optional[StageWindow]:
        return self._windows.get(stage)


# ============================================================
# Recorte por rango de tiempo de los CSV continuos
# ============================================================

def _empty_result(columns: list[str], warning: str) -> tuple[pd.DataFrame, list[str]]:
    return pd.DataFrame(columns=columns), [warning]


def slice_neurosky(csv_path: Path, start: datetime, end: datetime) -> tuple[pd.DataFrame, list[str]]:
    columns = [
        "Timestamp_Human", "Timestamp_Unix", "Poor_Signal",
        "Attention", "Meditation", "Delta", "Theta",
        "Low_Alpha", "High_Alpha", "Low_Beta", "High_Beta",
        "Low_Gamma", "Mid_Gamma",
    ]
    if not csv_path.exists():
        return _empty_result(columns, "NeuroSky: no se encontró el CSV de la sesión (¿se desconectó?).")
    try:
        df = pd.read_csv(csv_path)
    except (pd.errors.EmptyDataError, OSError):
        return _empty_result(columns, "NeuroSky: el CSV de la sesión está vacío o no se pudo leer.")
    if df.empty or "Timestamp_Unix" not in df.columns:
        return _empty_result(columns, "NeuroSky: el CSV no tiene filas todavía.")

    start_epoch, end_epoch = start.timestamp(), end.timestamp()
    sliced = df[(df["Timestamp_Unix"] >= start_epoch) & (df["Timestamp_Unix"] <= end_epoch)].copy()
    warnings = [] if not sliced.empty else ["NeuroSky: sin lecturas durante esta etapa (¿sin señal?)."]
    return sliced, warnings


def _slice_by_timestamp_column(
    csv_path: Path, start: datetime, end: datetime, columns: list[str], source_label: str,
) -> tuple[pd.DataFrame, list[str]]:
    if not csv_path.exists():
        return _empty_result(columns, f"{source_label}: no se encontró el CSV de la sesión (¿se desconectó?).")
    try:
        df = pd.read_csv(csv_path)
    except (pd.errors.EmptyDataError, OSError):
        return _empty_result(columns, f"{source_label}: el CSV de la sesión está vacío o no se pudo leer.")
    if df.empty or "timestamp" not in df.columns:
        return _empty_result(columns, f"{source_label}: el CSV no tiene filas todavía.")

    timestamps = pd.to_datetime(df["timestamp"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    mask = (timestamps >= start) & (timestamps <= end)
    sliced = df[mask].copy()
    warnings = [] if not sliced.empty else [f"{source_label}: sin lecturas durante esta etapa (¿sin señal?)."]
    return sliced, warnings


# Categorias que loguea tools/camera_tracker.py.EmotionAnalyzer (una
# columna "pct_<categoria>" por cada una, ver EMOTION_CSV_FIELDNAMES ahi) --
# duplicada aca (en vez de importar desde tools/) porque ese modulo carga
# opencv/deepface/mediapipe, pesado para lo unico que hace falta aca: los
# nombres de columna para construir un DataFrame vacio cuando falta el CSV.
DEEPFACE_EMOTION_CATEGORIES = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]


def slice_emotion(csv_path: Path, start: datetime, end: datetime) -> tuple[pd.DataFrame, list[str]]:
    columns = [
        "timestamp", "participant_id", "participant_name", "session_label", "emotion", "confidence",
        *(f"pct_{category}" for category in DEEPFACE_EMOTION_CATEGORIES),
    ]
    return _slice_by_timestamp_column(csv_path, start, end, columns, "Emotion Tracker")


def slice_eye(csv_path: Path, start: datetime, end: datetime) -> tuple[pd.DataFrame, list[str]]:
    columns = [
        "timestamp", "participant_id", "participant_name", "session_label",
        "gaze_x", "gaze_y", "gaze_direction",
    ]
    return _slice_by_timestamp_column(csv_path, start, end, columns, "Eye Tracker")


HEART_RATE_COLUMNS = [
    "com.samsung.health.heart_rate.start_time",
    "com.samsung.health.heart_rate.end_time",
    "com.samsung.health.heart_rate.heart_rate",
    "com.samsung.health.heart_rate.binning_data",
]

# Las etapas 2/4/5 duran segundos, pero el reloj -salvo que se active
# medicion continua- suele tomar una lectura puntual cada varios minutos.
# Es casi seguro que ninguna caiga justo dentro de la ventana de la etapa,
# asi que en vez de dejar la etapa sin ningun dato se admite la lectura
# puntual mas cercana (antes o despues) si esta a menos de esta tolerancia.
HEART_RATE_FALLBACK_TOLERANCE = timedelta(minutes=30)


_UTC_OFFSET_RE = re.compile(r"^UTC([+-])(\d{2})(\d{2})$")


def _parse_utc_offset(offset_text: str) -> timedelta:
    """"UTC-0400" -> timedelta(hours=-4) (ver columna
    com.samsung.health.heart_rate.time_offset) -- para poder pasar los
    timestamps epoch (UTC) de los JSON de binning (ver
    _expand_binning_json) a la misma hora local "naive" que ya usan las
    demas columnas de este CSV. Si el texto no matchea el formato
    esperado, no desplaza nada (mejor una hora posiblemente incorrecta en
    UTC que reventar el recorte)."""
    match = _UTC_OFFSET_RE.match((offset_text or "").strip())
    if not match:
        return timedelta(0)
    sign, hours, minutes = match.groups()
    delta = timedelta(hours=int(hours), minutes=int(minutes))
    return -delta if sign == "-" else delta


_BINNING_EXPANDED_COLUMNS = [
    "com.samsung.health.heart_rate.start_time",
    "com.samsung.health.heart_rate.heart_rate",
    "is_binned_reading",
]


def _expand_binning_json(row: "pd.Series", jsons_dir: Path) -> pd.DataFrame:
    """Una fila agregada por hora del CSV plano (`binning_data` no vacio)
    solo trae el promedio/max/min de esa hora -- la medicion real,
    minuto a minuto, vive en un JSON aparte (nombrado por esa misma
    columna) que Samsung Health exporta en
    "jsons/com.samsung.shealth.tracker.heart_rate/<primera_letra>/
    <nombre>.json" DENTRO de la carpeta completa del export (no viene con
    el CSV suelto, ver heart_rate_import.HEART_RATE_JSON_SUBDIR). Si ese
    JSON no esta disponible o no se puede leer, esta fila simplemente no
    aporta lecturas (no es un error -- ver el aviso de "datos agregados
    por hora" en slice_heart_rate)."""
    filename = str(row.get("com.samsung.health.heart_rate.binning_data", "")).strip()
    if not filename or filename.lower() == "nan":
        return pd.DataFrame(columns=_BINNING_EXPANDED_COLUMNS)

    json_path = jsons_dir / filename[0] / filename
    if not json_path.exists():
        return pd.DataFrame(columns=_BINNING_EXPANDED_COLUMNS)
    try:
        entries = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return pd.DataFrame(columns=_BINNING_EXPANDED_COLUMNS)

    offset = _parse_utc_offset(str(row.get("com.samsung.health.heart_rate.time_offset", "")))
    records = []
    for entry in entries:
        start_ms, heart_rate = entry.get("start_time"), entry.get("heart_rate")
        if start_ms is None or heart_rate is None:
            continue
        local_dt = (datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc) + offset).replace(tzinfo=None)
        records.append({
            "com.samsung.health.heart_rate.start_time": local_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "com.samsung.health.heart_rate.heart_rate": heart_rate,
            "is_binned_reading": True,
        })
    return pd.DataFrame(records, columns=_BINNING_EXPANDED_COLUMNS)


def slice_heart_rate(
    csv_path: Path, start: datetime, end: datetime, jsons_dir: Optional[Path] = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Recorta la frecuencia cardiaca del reloj para la ventana [start, end]
    de una etapa, combinando dos fuentes del CSV plano de Samsung Health
    ("com.samsung.shealth.tracker.heart_rate.*.csv", ver
    heart_rate_import.py):

    - Lecturas puntuales (`binning_data` vacio): chequeos sueltos del
      reloj, espaciados minutos u horas.
    - Lecturas agregadas por hora (`binning_data` con un nombre de JSON):
      si se pasa `jsons_dir` (la carpeta "jsons/com.samsung.shealth.
      tracker.heart_rate/" del export COMPLETO, no del CSV suelto -- ver
      HEART_RATE_JSON_SUBDIR), se expande cada una al detalle real
      minuto a minuto que trae su JSON de respaldo (ver
      _expand_binning_json) -- esto es lo que efectivamente produce la
      "medicion continua" del reloj. Sin `jsons_dir` (o si el JSON no
      esta disponible), esas filas se ignoran, igual que antes.

    Si ninguna lectura (puntual o expandida) cae dentro de [start, end],
    recurre a la mas cercana dentro de HEART_RATE_FALLBACK_TOLERANCE (ver
    esa constante) y la marca con la columna `is_fallback_reading` para que
    quien la muestre (ver stage_capture._summarize_heart_rate) deje en claro
    que es aproximada."""
    if not csv_path.exists():
        return _empty_result(HEART_RATE_COLUMNS, "Frecuencia cardíaca: no se encontró el archivo del reloj.")
    try:
        # index_col=False es necesario: cada fila trae una coma final (un
        # 22do campo vacio) mientras que la cabecera solo declara 21
        # columnas -- sin esto pandas asume que la primera columna es un
        # indice y desplaza el resto, corrompiendo todas las columnas.
        df = pd.read_csv(csv_path, skiprows=1, encoding="utf-8-sig", index_col=False)
    except (pd.errors.EmptyDataError, OSError):
        return _empty_result(HEART_RATE_COLUMNS, "Frecuencia cardíaca: el archivo está vacío o no se pudo leer.")

    start_col = "com.samsung.health.heart_rate.start_time"
    end_col = "com.samsung.health.heart_rate.end_time"
    binning_col = "com.samsung.health.heart_rate.binning_data"
    if df.empty or start_col not in df.columns:
        return _empty_result(HEART_RATE_COLUMNS, "Frecuencia cardíaca: el archivo no tiene filas reconocibles.")

    is_point = df[binning_col].isna() | (df[binning_col].astype(str).str.strip() == "")
    point_samples = df[is_point].copy()

    binned_samples = pd.DataFrame()
    if jsons_dir is not None:
        expanded = [_expand_binning_json(row, jsons_dir) for _, row in df[~is_point].iterrows()]
        expanded = [frame for frame in expanded if not frame.empty]
        if expanded:
            binned_samples = pd.concat(expanded, ignore_index=True)

    all_samples = (
        pd.concat([point_samples, binned_samples], ignore_index=True)
        if not binned_samples.empty else point_samples
    )
    timestamps = pd.to_datetime(all_samples[start_col], format="%Y-%m-%d %H:%M:%S.%f", errors="coerce")
    mask = (timestamps >= start) & (timestamps <= end)
    sliced = all_samples[mask].copy()

    if not sliced.empty:
        return sliced, []

    start_dist = (timestamps - start).abs()
    end_dist = (timestamps - end).abs()
    distance = start_dist.where(start_dist <= end_dist, end_dist)
    if distance.notna().any():
        nearest_idx = distance.idxmin()
        nearest_distance = distance.loc[nearest_idx]
        if nearest_distance <= HEART_RATE_FALLBACK_TOLERANCE:
            fallback = all_samples.loc[[nearest_idx]].copy()
            fallback["is_fallback_reading"] = True
            minutes = nearest_distance.total_seconds() / 60
            return fallback, [
                "Frecuencia cardíaca: sin lecturas durante esta etapa, se muestra la lectura "
                f"más cercana del reloj (~{minutes:.0f} min de diferencia)."
            ]

    total_in_range = df[
        (pd.to_datetime(df[start_col], format="%Y-%m-%d %H:%M:%S.%f", errors="coerce") >= start)
        & (pd.to_datetime(df[end_col], format="%Y-%m-%d %H:%M:%S.%f", errors="coerce") <= end)
    ]
    if not total_in_range.empty:
        warning = (
            "Frecuencia cardíaca: hay datos agregados por hora en esta etapa, pero no se "
            "encontró/pudo leer su detalle minuto a minuto (¿falta la carpeta \"jsons/\" del "
            "export completo?)."
            if jsons_dir is not None else
            "Frecuencia cardíaca: solo hay datos agregados por hora en esta etapa -- falta la "
            "carpeta \"jsons/\" del export completo para leer el detalle minuto a minuto."
        )
    else:
        warning = "Frecuencia cardíaca: sin lecturas durante esta etapa."
    return sliced, [warning]


# ============================================================
# Agregacion de miradas izquierda/derecha
# ============================================================

def aggregate_eye_looks(eye_df: pd.DataFrame) -> pd.DataFrame:
    """Agrupa filas consecutivas con el mismo `gaze_direction` en "miradas":
    cuantas veces el participante miro a cada lado y cuanto duro cada una.

    El CSV crudo (ver tools/camera_tracker.py::GazeEstimator.report) ya trae
    la direccion izquierda/derecha por fila (con debounce), pero no esta
    agregacion -- se calcula aca, no en la captura en vivo.

    Nota de precision: `timestamp` tiene resolucion de 1 segundo (sin
    fraccion), asi que una "mirada" de un solo frame puede reportar 0
    segundos de duracion aunque haya durado una fraccion de segundo real.
    """
    columns = ["direction", "start_ts", "end_ts", "duration_seconds", "sample_count"]
    if eye_df.empty or "gaze_direction" not in eye_df.columns:
        return pd.DataFrame(columns=columns)

    df = eye_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    df = df.sort_values("timestamp").reset_index(drop=True)

    run_id = (df["gaze_direction"] != df["gaze_direction"].shift()).cumsum()
    looks = []
    for _, group in df.groupby(run_id):
        direction = group["gaze_direction"].iloc[0]
        start_ts = group["timestamp"].iloc[0]
        end_ts = group["timestamp"].iloc[-1]
        looks.append({
            "direction": direction,
            "start_ts": start_ts,
            "end_ts": end_ts,
            "duration_seconds": (end_ts - start_ts).total_seconds(),
            "sample_count": len(group),
        })
    return pd.DataFrame(looks, columns=columns)


# ============================================================
# Escritores
# ============================================================

def write_stage_sensor_files(
    stage_folder: Path,
    neurosky_df: Optional[pd.DataFrame] = None, emotion_df: Optional[pd.DataFrame] = None,
    eye_df: Optional[pd.DataFrame] = None, heart_df: Optional[pd.DataFrame] = None,
) -> None:
    """Cada DataFrame es opcional -- None significa que ese dispositivo no
    se uso en esta sesion (ver SessionWizard._enabled_devices), no que
    falto el dato: en ese caso directamente no se escribe el CSV
    correspondiente, en vez de uno vacio, para no confundir "no se uso"
    con "se uso pero no se encontro nada" (ver stage_capture.
    summarize_stage / _summarize_csv_rows, que ya tratan un archivo
    ausente como EMPTY_CELL)."""
    if neurosky_df is not None:
        neurosky_df.to_csv(stage_folder / "neurosky.csv", index=False)
    if emotion_df is not None:
        emotion_df.to_csv(stage_folder / "emotion_tracker.csv", index=False)
    if eye_df is not None:
        eye_df.to_csv(stage_folder / "eye_tracker.csv", index=False)
    if heart_df is not None:
        heart_df.to_csv(stage_folder / "heart_rate.csv", index=False)

    if eye_df is not None:
        looks_df = aggregate_eye_looks(eye_df)
        looks_df.to_csv(stage_folder / "eye_tracker_miradas.csv", index=False)


def write_cuestionario_txt(stage_folder: Path, questions: list[QuizQuestion], answers: dict[int, int]) -> None:
    """Copia legible (.txt) del cuestionario de esta etapa -- el registro
    "de verdad" ya lo guarda quiz_results.save_quiz_answers en
    data/quiz_results/PARTICIPANTE_N.json; esto es una copia dentro de la
    carpeta de la etapa, para que quede todo junto en el Escritorio."""
    lines = []
    for i, question in enumerate(questions):
        selected = answers.get(i, -1)
        selected_text = question.options[selected] if 0 <= selected < len(question.options) else "(sin responder)"
        correct_text = question.options[question.correct_index]
        is_correct = selected == question.correct_index
        lines.append(f"Pregunta {i + 1}: {question.text}")
        for j, option in enumerate(question.options):
            marker = " (correcta)" if j == question.correct_index else ""
            lines.append(f"  {j + 1}. {option}{marker}")
        lines.append(f"  Respuesta correcta: {correct_text}")
        lines.append(f"  Respuesta seleccionada: {selected_text}")
        lines.append(f"  ¿Correcto?: {'Si' if is_correct else 'No'}")
        lines.append("")
    (stage_folder / "cuestionario.txt").write_text("\n".join(lines), encoding="utf-8")


def write_stage3_files(stage_folder: Path, prompt_text: str, statement_log: list[dict]) -> None:
    """Etapa 3: el prompt libre que escribio el participante
    (`escrito_etapa3.txt`, hoy solo vivia en memoria) y el registro de
    cuantas veces abrio el enunciado del desafio y cuanto duro cada
    apertura (`registro_enunciado.csv`)."""
    (stage_folder / "escrito_etapa3.txt").write_text(prompt_text, encoding="utf-8")

    with (stage_folder / "registro_enunciado.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["opened_at", "closed_at", "duration_seconds"])
        for entry in statement_log:
            opened_at = entry["opened_at"]
            closed_at = entry.get("closed_at")
            duration = (closed_at - opened_at).total_seconds() if closed_at else ""
            writer.writerow([opened_at.isoformat(), closed_at.isoformat() if closed_at else "", duration])


def write_sync_timeline(stage_folder: Path, window: StageWindow, per_source_info: dict) -> None:
    """sync_timeline.json: vincula por tiempo las distintas fuentes de esta
    etapa -- rango de la etapa y, por fuente, cantidad de filas / primer y
    ultimo timestamp / advertencias, para poder alinearlas despues sin
    rehacer el recorte."""
    payload = {
        "stage": window.stage,
        "stage_started_at": window.started_at.isoformat(),
        "stage_ended_at": (window.ended_at or window.started_at).isoformat(),
        "sources": per_source_info,
    }
    (stage_folder / "sync_timeline.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8",
    )


def source_info(df: pd.DataFrame, timestamp_column: str, warnings: list[str]) -> dict:
    info = {"rows": int(len(df)), "warnings": warnings}
    if not df.empty and timestamp_column in df.columns:
        info["first_timestamp"] = str(df[timestamp_column].iloc[0])
        info["last_timestamp"] = str(df[timestamp_column].iloc[-1])
    return info


def write_challenge_manifest(
    challenge_folder: Path, participant: dict, challenge_number: int, stage_status: dict,
) -> None:
    payload = {
        "participant_number": participant["number"],
        "challenge_number": challenge_number,
        "stages": stage_status,
    }
    (challenge_folder / "resumen_desafio.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8",
    )


def write_session_index(participant_folder: Path, completed_challenges: list[int]) -> None:
    payload = {"completed_challenges": sorted(completed_challenges)}
    (participant_folder / "resumen_sesion.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8",
    )


def available_challenges(participant_folder: Path) -> list[int]:
    """Desafíos con algo para mostrar (manifiesto propio o, a falta de eso,
    cualquier carpeta Etapa_* con contenido -- un desafío cerrado con
    "Siguiente juego" nunca pasa por la pantalla del reloj, asi que nunca
    tiene resumen_desafio.json, pero sus etapas ya tienen datos reales
    exportados en disco, ver _export_stage en session_wizard.py)."""
    session_index = participant_folder / "resumen_sesion.json"
    challenges = set()
    if session_index.exists():
        try:
            data = json.loads(session_index.read_text(encoding="utf-8"))
            challenges.update(data.get("completed_challenges", []))
        except (json.JSONDecodeError, OSError):
            pass
    for manifest in participant_folder.glob("Desafio_*/resumen_desafio.json"):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            challenges.add(data.get("challenge_number"))
        except (json.JSONDecodeError, OSError):
            continue
    for challenge_dir_path in participant_folder.glob("Desafio_*"):
        if not challenge_dir_path.is_dir() or not any(challenge_dir_path.glob("Etapa_*")):
            continue
        try:
            challenges.add(int(challenge_dir_path.name.removeprefix("Desafio_")))
        except ValueError:
            continue
    return sorted(c for c in challenges if c)


# ============================================================
# Resumen por etapa para la matriz de la pestaña "Sesión" (ver app.py)
# ============================================================

EMPTY_CELL = "—"


def _summarize_csv_rows(path: Path) -> str:
    """"N lecturas" para un CSV crudo (NeuroSky/Emotion) -- EMPTY_CELL si
    no existe, esta vacio, o no se puede leer (nunca lanza)."""
    if not path.exists():
        return EMPTY_CELL
    try:
        df = pd.read_csv(path)
    except (pd.errors.EmptyDataError, OSError, pd.errors.ParserError):
        return EMPTY_CELL
    if df.empty:
        return EMPTY_CELL
    return f"{len(df)} lecturas"


def _summarize_eye_looks(path: Path) -> str:
    """"Izq: N (Xs) · Der: N (Xs)" a partir de eye_tracker_miradas.csv
    (ya agregado por write_stage_sensor_files/aggregate_eye_looks)."""
    if not path.exists():
        return EMPTY_CELL
    try:
        df = pd.read_csv(path)
    except (pd.errors.EmptyDataError, OSError, pd.errors.ParserError):
        return EMPTY_CELL
    if df.empty or "direction" not in df.columns:
        return EMPTY_CELL
    parts = []
    for direction, label in (("izquierda", "Izq"), ("derecha", "Der")):
        rows = df[df["direction"] == direction]
        if rows.empty:
            continue
        total_seconds = rows["duration_seconds"].sum()
        parts.append(f"{label}: {len(rows)} ({total_seconds:.1f}s)")
    return " · ".join(parts) if parts else EMPTY_CELL


def _summarize_heart_rate(path: Path) -> str:
    """"HH:MM:SS–HH:MM:SS (~X bpm prom.)" a partir de heart_rate.csv (ya
    recortado por slice_heart_rate) -- prioriza el promedio de bpm sobre la
    cantidad de lecturas (poco util para el evaluador); si no hay valores
    de bpm utilizables cae a "N lecturas" para no dejar la celda vacia. Si
    la unica lectura disponible es la mas cercana fuera de la ventana de la
    etapa (columna `is_fallback_reading`, ver HEART_RATE_FALLBACK_
    TOLERANCE), lo marca con "(aprox., fuera de la etapa)" para que no se
    lea como una medicion exacta durante la etapa."""
    if not path.exists():
        return EMPTY_CELL
    try:
        df = pd.read_csv(path)
    except (pd.errors.EmptyDataError, OSError, pd.errors.ParserError):
        return EMPTY_CELL
    col = "com.samsung.health.heart_rate.start_time"
    if df.empty or col not in df.columns:
        return EMPTY_CELL
    try:
        timestamps = pd.to_datetime(df[col], format="%Y-%m-%d %H:%M:%S.%f", errors="coerce").dropna()
    except (ValueError, TypeError):
        return EMPTY_CELL
    if timestamps.empty:
        return EMPTY_CELL
    start, end = timestamps.min(), timestamps.max()

    hr_col = "com.samsung.health.heart_rate.heart_rate"
    avg_bpm = None
    if hr_col in df.columns:
        values = pd.to_numeric(df[hr_col], errors="coerce").dropna()
        if not values.empty:
            avg_bpm = values.mean()

    detail = f"~{avg_bpm:.0f} bpm prom." if avg_bpm is not None else f"{len(df)} lecturas"
    summary = f"{start:%H:%M:%S}–{end:%H:%M:%S} ({detail})"
    if "is_fallback_reading" in df.columns and df["is_fallback_reading"].fillna(False).any():
        summary += " (aprox., fuera de la etapa)"
    return summary


def _summarize_cuestionario(path: Path) -> str:
    """"N/M correctas" contando las lineas "¿Correcto?: Si/No" que ya
    escribe write_cuestionario_txt."""
    if not path.exists():
        return EMPTY_CELL
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return EMPTY_CELL
    correct = text.count("¿Correcto?: Si")
    total = correct + text.count("¿Correcto?: No")
    if total == 0:
        return EMPTY_CELL
    return f"{correct}/{total} correctas"


def _summarize_enunciado(path: Path) -> str:
    """"N aperturas · Xs total" a partir de registro_enunciado.csv."""
    if not path.exists():
        return EMPTY_CELL
    try:
        df = pd.read_csv(path)
    except (pd.errors.EmptyDataError, OSError, pd.errors.ParserError):
        return EMPTY_CELL
    if df.empty:
        return EMPTY_CELL
    total_seconds = pd.to_numeric(df.get("duration_seconds"), errors="coerce").fillna(0).sum()
    return f"{len(df)} aperturas · {total_seconds:.1f}s total"


def summarize_stage(challenge_folder: Path, stage: int, attempt: Optional[int] = None) -> dict:
    """Resumen (listo para mostrar) de una etapa ya exportada, para la
    matriz de la pestaña "Sesión" -- nunca lanza: una etapa sin datos
    (sesion en curso, o el participante todavia no llego ahi) devuelve
    todas las columnas en EMPTY_CELL, no rompe la interfaz.

    Las columnas de sensores aplican a las etapas 2/3/4/5; la de
    cuestionario solo a 2/4/5 y las de enunciado/escrito solo a la etapa 3
    (ver session_wizard._export_stage / _save_stage3_files) -- lo que no
    aplica a una etapa queda en EMPTY_CELL, no por faltar.
    """
    result = {
        "neurosky": EMPTY_CELL, "emotion": EMPTY_CELL, "eye": EMPTY_CELL,
        "heart_rate": EMPTY_CELL, "cuestionario": EMPTY_CELL,
        "enunciado": EMPTY_CELL, "escrito": EMPTY_CELL,
    }
    try:
        folder = resolve_stage_folder(challenge_folder, stage, attempt)
    except OSError:
        folder = None
    if folder is None:
        return result

    result["neurosky"] = _summarize_csv_rows(folder / "neurosky.csv")
    result["emotion"] = _summarize_csv_rows(folder / "emotion_tracker.csv")
    result["eye"] = _summarize_eye_looks(folder / "eye_tracker_miradas.csv")
    result["heart_rate"] = _summarize_heart_rate(folder / "heart_rate.csv")
    if stage in (2, 4, 5):
        result["cuestionario"] = _summarize_cuestionario(folder / "cuestionario.txt")
    elif stage == 3:
        result["enunciado"] = _summarize_enunciado(folder / "registro_enunciado.csv")
        result["escrito"] = "Sí" if (folder / "escrito_etapa3.txt").exists() else EMPTY_CELL

    return result
