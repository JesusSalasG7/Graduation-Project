"""Registro de datos personales de los participantes, guardado FUERA del
proyecto (en el Escritorio del usuario), separado del registro anónimo
de `participants.json`.

El resto de la aplicación -- y todo archivo versionado del proyecto --
solo conoce a cada participante por su número secuencial ("Participante
N"). Este módulo es la única pieza que conecta ese número con un nombre
real, y guarda ese vínculo fuera de la carpeta del proyecto a propósito,
para no mezclar datos personales con los datos anónimos de la sesión
(emociones, frecuencia cardíaca, etc.).
"""

import csv
from pathlib import Path
from typing import Optional

PERSONAL_RECORDS_DIR = Path.home() / "Escritorio" / "Participantes"
PERSONAL_RECORDS_FILE = PERSONAL_RECORDS_DIR / "participantes.csv"


def load_personal_record(number: int) -> Optional[tuple[str, str]]:
    """Busca (nombre, apellido) para `number` en el CSV del Escritorio.

    Devuelve None si el archivo no existe o el número no está registrado.
    Se usa solo para mostrar el nombre en pantalla (p.ej. saludo de
    bienvenida); nunca se persiste junto a los datos anónimos de sesión.
    """
    if not PERSONAL_RECORDS_FILE.exists():
        return None

    with PERSONAL_RECORDS_FILE.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                row_number = int(row["numero_participante"])
            except (KeyError, ValueError):
                continue
            if row_number == number:
                return row["nombre"], row["apellido"]

    return None


def save_personal_record(number: int, nombre: str, apellido: str) -> Path:
    """Agrega una fila (número, nombre, apellido) al CSV de participantes
    del Escritorio, creando la carpeta/archivo con encabezado si hace falta.

    Devuelve la ruta del CSV.
    """
    PERSONAL_RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    is_new_file = not PERSONAL_RECORDS_FILE.exists() or PERSONAL_RECORDS_FILE.stat().st_size == 0

    with PERSONAL_RECORDS_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new_file:
            writer.writerow(["numero_participante", "nombre", "apellido"])
        writer.writerow([number, nombre.strip(), apellido.strip()])

    return PERSONAL_RECORDS_FILE
