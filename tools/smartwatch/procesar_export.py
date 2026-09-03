#!/usr/bin/env python3
"""
Procesa exportaciones de "Descargar mis datos personales" de Samsung Health
y extrae las lecturas de frecuencia cardíaca de sesiones de ejercicio (BPM
punto a punto, no solo el promedio), guardándolas en un CSV limpio.

Flujo de uso:
  1. En el reloj: Samsung Health > Ejercicio > elige un tipo sin GPS > inicia,
     realiza la sesión, detén y guarda.
  2. Espera a que sincronice con el teléfono.
  3. En el teléfono: Samsung Health > Mi página > menú > Ajustes >
     Descargar mis datos personales > Descargar.
  4. Copia la carpeta "samsunghealth_<usuario>_<fecha>" resultante a la PC
     (USB en modo Transferir archivos, o Google Drive/Dropbox).
  5. Corre este script sobre esa carpeta.

Uso:
    python3 procesar_export.py /ruta/a/samsunghealth_usuario_YYYYMMDDHHMMSS
    python3 procesar_export.py /ruta/a/export --output datos_tesis.csv
    python3 procesar_export.py /ruta/a/export --list                  # listar sesiones disponibles
    python3 procesar_export.py /ruta/a/export --session-id <datauuid> # solo una sesión
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

EXERCISE_CSV_GLOB = "com.samsung.shealth.exercise.*.csv"
LIVE_DATA_COLUMN = "com.samsung.health.exercise.live_data"
DATAUUID_COLUMN = "com.samsung.health.exercise.datauuid"
START_TIME_COLUMN = "com.samsung.health.exercise.start_time"
END_TIME_COLUMN = "com.samsung.health.exercise.end_time"
EXERCISE_TYPE_COLUMN = "com.samsung.health.exercise.exercise_type"
MEAN_HR_COLUMN = "com.samsung.health.exercise.mean_heart_rate"
MAX_HR_COLUMN = "com.samsung.health.exercise.max_heart_rate"
MIN_HR_COLUMN = "com.samsung.health.exercise.min_heart_rate"

DEFAULT_OUTPUT = "datos_tesis.csv"


def read_exercise_rows(export_dir: Path) -> list[dict]:
    csv_files = sorted(export_dir.glob(EXERCISE_CSV_GLOB))
    if not csv_files:
        raise FileNotFoundError(
            f"No se encontró un CSV de ejercicios ({EXERCISE_CSV_GLOB}) en {export_dir}. "
            "¿Es la carpeta correcta del export de Samsung Health?"
        )

    rows: list[dict] = []
    for csv_path in csv_files:
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            f.readline()  # primera línea = metadata de la tabla (nombre, versión, num. columnas); se descarta
            reader = csv.DictReader(f)
            rows.extend(reader)
    return rows


def find_live_data_file(export_dir: Path, filename: str) -> Path | None:
    """Los blobs JSON están repartidos en subcarpetas de un carácter según el
    primer carácter del datauuid: jsons/com.samsung.shealth.exercise/<0-f>/<filename>
    """
    if not filename:
        return None
    base_dir = export_dir / "jsons" / "com.samsung.shealth.exercise"
    if not base_dir.exists():
        return None
    for subdir in base_dir.iterdir():
        candidate = subdir / filename
        if candidate.exists():
            return candidate
    return None


def epoch_ms_to_iso(epoch_ms) -> str:
    return datetime.fromtimestamp(int(float(epoch_ms)) / 1000).isoformat(sep=" ", timespec="milliseconds")


def extract_samples_in_window(export_dir: Path, start_dt: datetime, end_dt: datetime) -> list[dict]:
    """Devuelve las muestras BPM (de cualquier sesión de ejercicio del export)
    cuyo timestamp cae dentro de [start_dt, end_dt], ordenadas por tiempo.

    Filtra a nivel de muestra individual, no de sesión completa: así se
    toleran pequeños desfaces entre el inicio/fin marcado en la app y el de
    la sesión grabada por el reloj, e incluso permite juntar muestras de más
    de una sesión de ejercicio si el experimento abarcó varias.
    """
    rows = read_exercise_rows(export_dir)
    matches: list[dict] = []

    for row in rows:
        live_data_path = find_live_data_file(export_dir, row.get(LIVE_DATA_COLUMN))
        if not live_data_path:
            continue

        with live_data_path.open(encoding="utf-8") as jf:
            samples = json.load(jf)

        for sample in samples:
            timestamp = datetime.fromtimestamp(int(float(sample["start_time"])) / 1000)
            if start_dt <= timestamp <= end_dt:
                matches.append({"timestamp": timestamp, "bpm": sample["heart_rate"]})

    matches.sort(key=lambda m: m["timestamp"])
    return matches


def list_sessions(rows: list[dict]) -> None:
    if not rows:
        print("No hay sesiones de ejercicio en este export.")
        return
    for row in rows:
        print(
            f"{row[DATAUUID_COLUMN]}  "
            f"{row[START_TIME_COLUMN]} -> {row[END_TIME_COLUMN]}  "
            f"tipo={row[EXERCISE_TYPE_COLUMN]}  "
            f"HR avg/min/max={row[MEAN_HR_COLUMN]}/{row[MIN_HR_COLUMN]}/{row[MAX_HR_COLUMN]}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extrae BPM punto a punto de sesiones de ejercicio de un export de Samsung Health."
    )
    parser.add_argument("export_dir", type=Path, help="Carpeta samsunghealth_usuario_YYYYMMDDHHMMSS")
    parser.add_argument("--output", type=Path, default=Path(DEFAULT_OUTPUT))
    parser.add_argument("--session-id", help="datauuid de una sesión específica (ver --list)")
    parser.add_argument("--list", action="store_true", help="Solo listar las sesiones disponibles y salir")
    args = parser.parse_args()

    rows = read_exercise_rows(args.export_dir)

    if args.list:
        list_sessions(rows)
        return

    if args.session_id:
        rows = [r for r in rows if r[DATAUUID_COLUMN] == args.session_id]
        if not rows:
            print(f"No se encontró la sesión {args.session_id}. Usa --list para ver las disponibles.")
            return

    total_samples = 0
    is_new_file = not args.output.exists() or args.output.stat().st_size == 0
    with args.output.open("a", newline="", encoding="utf-8") as out_f:
        writer = csv.writer(out_f)
        if is_new_file:
            writer.writerow(["session_id", "exercise_type", "timestamp", "bpm"])

        for row in rows:
            live_data_path = find_live_data_file(args.export_dir, row.get(LIVE_DATA_COLUMN))

            if not live_data_path:
                print(f"[aviso] Sesión {row[DATAUUID_COLUMN]} sin datos punto a punto, se omite.")
                continue

            with live_data_path.open(encoding="utf-8") as jf:
                samples = json.load(jf)

            for sample in samples:
                writer.writerow(
                    [
                        row[DATAUUID_COLUMN],
                        row[EXERCISE_TYPE_COLUMN],
                        epoch_ms_to_iso(sample["start_time"]),
                        sample["heart_rate"],
                    ]
                )
                total_samples += 1

    print(f"{total_samples} lecturas guardadas en {args.output.resolve()}")


if __name__ == "__main__":
    main()
