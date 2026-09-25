"""Pantalla de importacion de la frecuencia cardiaca del reloj (Samsung
Health), arrastrada por el evaluador una vez por desafio.

Se pide la CARPETA COMPLETA que exporta Samsung Health ("Descargar mis
datos personales", tipicamente "samsunghealth_<usuario>_<fecha>/"), no un
CSV suelto: el CSV plano ("com.samsung.shealth.tracker.heart_rate.
<numero>.csv") solo trae las lecturas puntuales sueltas y, para las horas
con medicion continua, un promedio/max/min por hora -- el detalle real
minuto a minuto de esa medicion continua vive en JSON aparte, dentro de
"jsons/com.samsung.shealth.tracker.heart_rate/" (ver
HEART_RATE_JSON_SUBDIR), que solo viene con la carpeta completa. Pedir
solo el CSV (como se hacia antes) pierde justo los datos de medicion
continua y deja solo los chequeos puntuales, espaciados minutos u horas
(ver stage_capture.slice_heart_rate).

No existia ningun drag & drop en el proyecto antes de esto -- se usa
tkinterdnd2 (ver register_drop_target) con un boton "Seleccionar carpeta"
de respaldo si esa libreria no esta disponible o falla en este equipo,
para que el flujo nunca quede bloqueado por un problema de esa dependencia
opcional.
"""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from typing import Callable, Optional

import customtkinter as ctk

from stage_capture import (
    challenge_dir_readonly,
    resolve_stage_folder,
    slice_heart_rate,
    write_challenge_manifest,
)

HEART_RATE_FILENAME_RE = re.compile(r"^com\.samsung\.shealth\.tracker\.heart_rate\.\d+\.csv$")
EXPECTED_HEADER_PREFIX = "com.samsung.shealth.tracker.heart_rate,"
EXPECTED_COLUMN_HINT = "com.samsung.health.heart_rate.heart_rate"

# Carpeta, relativa a la raiz del export de Samsung Health, con el detalle
# minuto a minuto de las horas con medicion continua (ver
# stage_capture._expand_binning_json) -- no viene si solo se copia el CSV
# suelto.
HEART_RATE_JSON_SUBDIR = Path("jsons") / "com.samsung.shealth.tracker.heart_rate"

# Nombre de la subcarpeta donde se copian esos JSON dentro del desafio,
# para trazabilidad (ver import_heart_rate_for_challenge/
# reimport_heart_rate_for_challenge) -- separado del CSV crudo para dejar
# en claro que es el respaldo de las filas agregadas por hora, no del
# archivo entero.
HEART_RATE_BINNING_COPY_DIRNAME = "heart_rate_binning_jsons"


class HeartRateValidationError(Exception):
    """La carpeta/archivo elegido no tiene el contenido o formato esperado."""


def validate_heart_rate_file(path: Path) -> None:
    """Valida un CSV de frecuencia cardiaca ya localizado (ver
    find_heart_rate_csv) -- nombre y cabecera esperados."""
    if not HEART_RATE_FILENAME_RE.match(path.name):
        raise HeartRateValidationError(
            f'El nombre del archivo no coincide con el esperado '
            f'("com.samsung.shealth.tracker.heart_rate.<número>.csv"): {path.name}'
        )
    try:
        with path.open(encoding="utf-8-sig") as f:
            first_line = f.readline()
            second_line = f.readline()
    except OSError as exc:
        raise HeartRateValidationError(f"No se pudo leer el archivo: {exc}") from exc

    if not first_line.startswith(EXPECTED_HEADER_PREFIX):
        raise HeartRateValidationError(
            "El archivo no tiene la cabecera esperada de un export de frecuencia "
            "cardíaca de Samsung Health (¿es el CSV correcto?)."
        )
    if EXPECTED_COLUMN_HINT not in second_line:
        raise HeartRateValidationError(
            "El archivo no tiene las columnas esperadas de frecuencia cardíaca."
        )


def find_heart_rate_csv(export_folder: Path) -> Path:
    """Busca DENTRO (no recursivo -- asi lo deja Samsung Health) de
    `export_folder` el CSV plano de frecuencia cardiaca. Lanza
    HeartRateValidationError si no hay ninguno o hay mas de uno."""
    matches = sorted(
        p for p in export_folder.iterdir() if p.is_file() and HEART_RATE_FILENAME_RE.match(p.name)
    )
    if not matches:
        raise HeartRateValidationError(
            'No se encontró ningún archivo "com.samsung.shealth.tracker.heart_rate.'
            f'<número>.csv" dentro de la carpeta ({export_folder}) -- ¿es la carpeta '
            "completa que exporta Samsung Health?"
        )
    if len(matches) > 1:
        raise HeartRateValidationError(
            f"Se encontró más de un archivo de frecuencia cardíaca dentro de la carpeta "
            f"({export_folder}) -- deja solo el más reciente."
        )
    return matches[0]


def validate_heart_rate_export_folder(export_folder: Path) -> Path:
    """Valida la carpeta completa del export de Samsung Health: que sea una
    carpeta y que tenga adentro un CSV de frecuencia cardiaca valido.
    Devuelve la ruta a ese CSV (ver find_heart_rate_csv)."""
    if not export_folder.is_dir():
        raise HeartRateValidationError(
            f'"{export_folder.name}" no es una carpeta -- se espera la carpeta completa '
            'que exporta Samsung Health ("Descargar mis datos personales"), no un archivo suelto.'
        )
    csv_path = find_heart_rate_csv(export_folder)
    validate_heart_rate_file(csv_path)
    return csv_path


def heart_rate_json_dir(export_folder: Path) -> Optional[Path]:
    """La subcarpeta "jsons/.../heart_rate/" de este export, o None si no
    esta presente (export viejo, o se copio solo el CSV) -- en ese caso
    slice_heart_rate simplemente no expande las horas de medicion continua
    y se queda con las lecturas puntuales sueltas, igual que antes."""
    candidate = export_folder / HEART_RATE_JSON_SUBDIR
    return candidate if candidate.is_dir() else None


def _copy_heart_rate_traceability(export_folder: Path, csv_path: Path, challenge_folder: Path) -> None:
    """Copia a la carpeta del desafio, para trazabilidad, el CSV crudo y --
    si esta disponible -- los JSON de binning que respaldan sus horas de
    medicion continua (ver heart_rate_json_dir). Todo best-effort: una
    copia fallida no debe frenar el recorte por etapa."""
    try:
        shutil.copy2(csv_path, challenge_folder / csv_path.name)
    except OSError:
        pass

    jsons_dir = heart_rate_json_dir(export_folder)
    if jsons_dir is not None:
        try:
            shutil.copytree(
                jsons_dir, challenge_folder / HEART_RATE_BINNING_COPY_DIRNAME, dirs_exist_ok=True,
            )
        except OSError:
            pass


def import_heart_rate_for_challenge(
    export_folder: Path, challenge_folder: Path, stage_folders: dict[int, Path], stage_windows: dict,
) -> dict[int, list[str]]:
    """Copia el CSV crudo (y los JSON de medicion continua, si estan) a la
    carpeta del desafio (trazabilidad) y recorta un heart_rate.csv por
    cada etapa 2/3/4/5 usando la ventana de tiempo de esa etapa (del ultimo
    intento, ver stage_capture.stage_dir). `export_folder` es la carpeta
    COMPLETA que exporta Samsung Health (ver validate_heart_rate_export_
    folder), no el CSV suelto.

    Devuelve {etapa: [advertencias]} para mostrar en la UI.
    """
    csv_path = find_heart_rate_csv(export_folder)
    jsons_dir = heart_rate_json_dir(export_folder)
    _copy_heart_rate_traceability(export_folder, csv_path, challenge_folder)

    warnings_by_stage: dict[int, list[str]] = {}
    for stage, folder in stage_folders.items():
        window = stage_windows.get(stage)
        if window is None:
            warnings_by_stage[stage] = ["Frecuencia cardíaca: no se registró la ventana de tiempo de esta etapa."]
            continue
        df, warnings = slice_heart_rate(
            csv_path, window.started_at, window.ended_at or window.started_at, jsons_dir=jsons_dir,
        )
        df.to_csv(folder / "heart_rate.csv", index=False)
        warnings_by_stage[stage] = warnings
    return warnings_by_stage


def reimport_heart_rate_for_challenge(
    participant_number: int, challenge_number: int, export_folder: Path,
) -> dict[int, list[str]]:
    """Reprocesa la frecuencia cardiaca de un desafio YA CERRADO (Etapas
    2/3/4/5 ya exportadas), a partir de la carpeta completa del export de
    Samsung Health -- la misma que se cargo durante la sesion, o una
    nueva/corregida -- sin depender de que la sesion guiada siga
    corriendo: la ventana de tiempo de cada etapa se reconstruye desde
    sync_timeline.json (ver stage_capture.write_sync_timeline), no de
    StageTimer en memoria.

    Sirve tanto para cargar el reloj de un desafio que se salteo (ver
    "Siguiente juego" en session_wizard.py, que nunca pasa por la
    pantalla de importacion) como para volver a cortar con una version
    mas nueva de slice_heart_rate (p.ej. HEART_RATE_FALLBACK_TOLERANCE, o
    el soporte de medicion continua via JSON de binning) sobre datos que
    ya se habian procesado con una version anterior.

    Uso desde linea de comandos, para cualquier participante/desafio: ver
    reimport_heart_rate.py.

    Devuelve {etapa: [advertencias]} como import_heart_rate_for_challenge,
    y ademas reescribe resumen_desafio.json con esas advertencias (el
    resto del manifiesto se conserva).
    """
    csv_path = validate_heart_rate_export_folder(export_folder)
    jsons_dir = heart_rate_json_dir(export_folder)

    participant = {"number": participant_number}
    challenge_folder = challenge_dir_readonly(participant, challenge_number)
    if not challenge_folder.is_dir():
        raise FileNotFoundError(
            f"No existe la carpeta del desafío ({challenge_folder}) -- "
            "revisa el número de participante/desafío.",
        )

    _copy_heart_rate_traceability(export_folder, csv_path, challenge_folder)

    warnings_by_stage: dict[int, list[str]] = {}
    for stage in (2, 3, 4, 5):
        folder = resolve_stage_folder(challenge_folder, stage)
        if folder is None:
            warnings_by_stage[stage] = [
                "Frecuencia cardíaca: esta etapa todavía no tiene datos exportados.",
            ]
            continue

        timeline_path = folder / "sync_timeline.json"
        if not timeline_path.exists():
            warnings_by_stage[stage] = [
                "Frecuencia cardíaca: no se encontró sync_timeline.json para "
                "reconstruir la ventana de tiempo de esta etapa.",
            ]
            continue
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        start = datetime.fromisoformat(timeline["stage_started_at"])
        end = datetime.fromisoformat(timeline["stage_ended_at"])

        df, warnings = slice_heart_rate(csv_path, start, end, jsons_dir=jsons_dir)
        df.to_csv(folder / "heart_rate.csv", index=False)
        warnings_by_stage[stage] = warnings

    _update_challenge_manifest_heart_rate(challenge_folder, participant, challenge_number, warnings_by_stage)
    return warnings_by_stage


def _update_challenge_manifest_heart_rate(
    challenge_folder: Path, participant: dict, challenge_number: int, warnings_by_stage: dict[int, list[str]],
) -> None:
    """Actualiza solo la parte de frecuencia cardiaca de resumen_desafio.json,
    conservando cualquier otra clave que ya tuviera ese manifiesto."""
    manifest_path = challenge_folder / "resumen_desafio.json"
    stage_status: dict = {}
    if manifest_path.exists():
        try:
            stage_status = json.loads(manifest_path.read_text(encoding="utf-8")).get("stages", {})
        except (json.JSONDecodeError, OSError):
            stage_status = {}

    stage_status.pop("heart_rate", None)  # ya no aplica "omitido por el evaluador" si se reimporto
    stage_status["heart_rate_warnings"] = {
        str(stage): warnings for stage, warnings in warnings_by_stage.items() if warnings
    }
    write_challenge_manifest(challenge_folder, participant, challenge_number, stage_status)


def register_drop_target(widget, on_drop_path: Callable[[str], None]) -> bool:
    """Intenta registrar `widget` como zona de destino de arrastrar-y-soltar
    con tkinterdnd2. Devuelve False (sin lanzar excepcion) si la libreria no
    esta instalada o el registro falla por cualquier motivo -- la pantalla
    debe seguir funcionando solo con el boton "Seleccionar archivo"."""
    try:
        from tkinterdnd2 import DND_FILES
    except ImportError:
        return False

    try:
        widget.drop_target_register(DND_FILES)

        def _on_drop(event):
            # event.data puede traer varias rutas separadas por espacio y
            # entre llaves si el nombre tiene espacios -- nos quedamos con
            # la primera.
            raw = event.data.strip()
            if raw.startswith("{") and "}" in raw:
                raw = raw[1:raw.index("}")]
            else:
                raw = raw.split()[0]
            on_drop_path(raw)

        widget.dnd_bind("<<Drop>>", _on_drop)
        return True
    except Exception:
        return False


class HeartRateDropFrame(ctk.CTkFrame):
    """Zona para cargar la carpeta completa del export de Samsung Health
    (frecuencia cardiaca del reloj): arrastrar y soltar (si esta
    disponible) o boton "Seleccionar carpeta" de respaldo, con error
    inline (nunca un messagebox bloqueante) si la carpeta no corresponde
    al formato esperado. Pide la carpeta -- no un CSV suelto -- porque el
    detalle minuto a minuto de la medicion continua vive en JSON aparte
    dentro de ella (ver HEART_RATE_JSON_SUBDIR)."""

    def __init__(
        self, master, colors: dict, font_family: str, scaled: Callable[[int], int], wrap: Callable[[int], int],
        on_file_accepted: Callable[[Path], None],
    ):
        super().__init__(master, fg_color=colors["BG_CARD"], corner_radius=12)
        self.c = colors
        self._on_file_accepted = on_file_accepted
        self._accepted_path: Optional[Path] = None

        ctk.CTkLabel(
            self, text="⌚  Cargar frecuencia cardíaca del reloj",
            font=ctk.CTkFont(family=font_family, size=scaled(15), weight="bold"),
        ).pack(anchor="w", padx=18, pady=(16, 4))
        ctk.CTkLabel(
            self,
            text="Arrastra acá la carpeta completa que exportó Samsung Health para este "
                 'desafío ("samsunghealth_usuario_<fecha>", con el archivo '
                 '"com.samsung.shealth.tracker.heart_rate.<número>.csv" adentro), o '
                 "elígela con el botón de abajo. Tiene que ser la carpeta completa -- no "
                 "el CSV suelto -- para poder usar la medición continua si está activada.",
            font=ctk.CTkFont(family=font_family, size=scaled(12)), text_color=self.c["TEXT_MUTED"],
            wraplength=wrap(560), justify="left",
        ).pack(anchor="w", padx=18, pady=(0, 12))

        self.drop_zone = ctk.CTkFrame(self, fg_color=self.c["BG_CARD_ALT"], corner_radius=10, height=scaled(90))
        self.drop_zone.pack(fill="x", padx=18, pady=(0, 10))
        self.drop_zone.pack_propagate(False)
        self.zone_label = ctk.CTkLabel(
            self.drop_zone, text="📂  Suelta la carpeta acá",
            font=ctk.CTkFont(family=font_family, size=scaled(13)), text_color=self.c["TEXT_MUTED"],
        )
        self.zone_label.pack(expand=True)

        drop_ok = register_drop_target(self.drop_zone, self._handle_dropped_path)
        if not drop_ok:
            self.zone_label.configure(
                text="📂  Arrastrar y soltar no disponible en este equipo -- usa el botón de abajo.",
            )

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.pack(fill="x", padx=18, pady=(0, 10))
        ctk.CTkButton(
            button_row, text="📂  Seleccionar carpeta", height=scaled(34), corner_radius=8,
            font=ctk.CTkFont(family=font_family, size=scaled(12)),
            fg_color=self.c["BG_CARD_ALT"], hover_color=self.c["BORDER"],
            command=self._open_folder_picker,
        ).pack(side="left")

        self.status_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(family=font_family, size=scaled(12)),
            wraplength=wrap(560), justify="left",
        )
        self.status_label.pack(anchor="w", padx=18, pady=(0, 16))

    def _open_folder_picker(self):
        path_str = filedialog.askdirectory(title="Seleccionar carpeta del export de Samsung Health")
        if path_str:
            self._handle_dropped_path(path_str)

    def _handle_dropped_path(self, path_str: str):
        path = Path(path_str)
        try:
            csv_path = validate_heart_rate_export_folder(path)
        except HeartRateValidationError as exc:
            self._accepted_path = None
            self.status_label.configure(text=f"⚠️  {exc}", text_color=self.c["WARNING"])
            return

        if heart_rate_json_dir(path) is not None:
            detail = "medición continua detectada ✅"
        else:
            detail = "sin carpeta \"jsons/\" -- solo se van a usar lecturas puntuales sueltas"

        self._accepted_path = path
        self.status_label.configure(
            text=f"✅  Carpeta válida ({csv_path.name}) -- {detail}", text_color=self.c["TEXT_MUTED"],
        )
        self._on_file_accepted(path)

    @property
    def accepted_path(self) -> Optional[Path]:
        return self._accepted_path
