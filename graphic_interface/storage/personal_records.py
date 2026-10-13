"""Registro de datos personales de los participantes, guardado FUERA del
proyecto (en el Escritorio del usuario), separado del registro anónimo
de `participants.json`.

El resto de la aplicación -- y todo archivo versionado del proyecto --
solo conoce a cada participante por su número secuencial ("Participante
N"). Este módulo es la única pieza que conecta ese número con un nombre
real (y con la cédula y el correo que se cargan al registrarlo, para que
la carta de consentimiento ya aparezca completa), y guarda ese vínculo
fuera de la carpeta del proyecto a propósito,
para no mezclar datos personales con los datos anónimos de la sesión
(emociones, frecuencia cardíaca, etc.).
"""

import csv
from pathlib import Path
from typing import Optional

PERSONAL_RECORDS_DIR = Path.home() / "Escritorio" / "Participantes"
PERSONAL_RECORDS_FILE = PERSONAL_RECORDS_DIR / "participantes.csv"

FIELDNAMES = ["numero_participante", "nombre", "apellido", "cedula", "correo"]


def _find_row(number: int) -> Optional[dict]:
    if not PERSONAL_RECORDS_FILE.exists():
        return None

    with PERSONAL_RECORDS_FILE.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                row_number = int(row["numero_participante"])
            except (KeyError, TypeError, ValueError):
                continue
            if row_number == number:
                return row

    return None


def load_personal_record(number: int) -> Optional[tuple[str, str]]:
    """Busca (nombre, apellido) para `number` en el CSV del Escritorio.

    Devuelve None si el archivo no existe o el número no está registrado.
    Se usa solo para mostrar el nombre en pantalla (p.ej. saludo de
    bienvenida); nunca se persiste junto a los datos anónimos de sesión.
    """
    row = _find_row(number)
    if row is None:
        return None
    return row.get("nombre") or "", row.get("apellido") or ""


def load_personal_contact(number: int) -> tuple[str, str]:
    """(cédula, correo) cargados al registrar al participante, para
    precargar la carta de consentimiento. Cadenas vacías si no se
    cargaron (o si el registro es anterior a que existieran esas
    columnas)."""
    row = _find_row(number)
    if row is None:
        return "", ""
    return (row.get("cedula") or "").strip(), (row.get("correo") or "").strip()


def _upgrade_header() -> None:
    """Los CSV creados antes de que existieran cédula y correo solo
    tienen tres columnas: se reescriben con el encabezado nuevo (y esas
    dos columnas vacías) para que las filas nuevas no queden desfasadas."""
    with PERSONAL_RECORDS_FILE.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames == FIELDNAMES:
            return
        rows = list(reader)

    tmp = PERSONAL_RECORDS_FILE.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore", restval="")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(PERSONAL_RECORDS_FILE)


def save_personal_record(number: int, nombre: str, apellido: str, cedula: str = "", correo: str = "") -> Path:
    """Agrega una fila (número, nombre, apellido, cédula, correo) al CSV
    de participantes del Escritorio, creando la carpeta/archivo con
    encabezado si hace falta.

    Devuelve la ruta del CSV.
    """
    PERSONAL_RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    is_new_file = not PERSONAL_RECORDS_FILE.exists() or PERSONAL_RECORDS_FILE.stat().st_size == 0
    if not is_new_file:
        _upgrade_header()

    with PERSONAL_RECORDS_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new_file:
            writer.writerow(FIELDNAMES)
        writer.writerow([number, nombre.strip(), apellido.strip(), cedula.strip(), correo.strip()])

    return PERSONAL_RECORDS_FILE
