"""Registro de consentimientos informados, guardado FUERA del proyecto
(en el Escritorio, junto al registro personal de `personal_records.py`).

Acá viven los únicos datos personales del consentimiento -- nombre, C.I.,
correo y el PDF firmado -- separados de los datos del estudio
(`~/Escritorio/Sesiones_participantes/`), que solo conocen el número de
participante. Los archivos se nombran con un código sin datos personales
("P001") y nada de este módulo se envía al servicio de IA ni se imprime.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from paths import CONSENT_VERSION
from storage.personal_records import PERSONAL_RECORDS_DIR

CONSENT_DIR = PERSONAL_RECORDS_DIR / "consentimientos"
CONSENT_REGISTRY_FILE = CONSENT_DIR / "registro.json"

STATUS_SIGNED = "firmado"
STATUS_DECLINED = "rechazado"

# Estado del envío por correo de cada destinatario (ver consent_mailer.py).
MAIL_SENT = "enviado"
MAIL_PENDING = "pendiente"
MAIL_NOT_REQUESTED = "no_solicitado"

RECIPIENT_RESEARCHER = "investigador"
RECIPIENT_PARTICIPANT = "participante"


def participant_code(number: int) -> str:
    """Código sin datos personales del participante, ej. "P001"."""
    return f"P{number:03d}"


def signed_pdf_path(number: int, version: str = CONSENT_VERSION) -> Path:
    return CONSENT_DIR / f"consentimiento_{participant_code(number)}_v{version}.pdf"


def _load() -> dict:
    if not CONSENT_REGISTRY_FILE.exists():
        return {}
    with CONSENT_REGISTRY_FILE.open("r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return {}
    return data if isinstance(data, dict) else {}


def _save(data: dict) -> None:
    CONSENT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONSENT_REGISTRY_FILE.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(CONSENT_REGISTRY_FILE)


def get_record(number: int) -> Optional[dict]:
    return _load().get(participant_code(number))


def has_signed(number: int) -> bool:
    """Firmó y el PDF firmado sigue en disco -- si alguien borró el
    archivo, se vuelve a pedir el consentimiento."""
    record = get_record(number)
    return bool(
        record
        and record.get("estado") == STATUS_SIGNED
        and Path(record.get("pdf", "")).exists()
    )


def has_declined(number: int) -> bool:
    record = get_record(number)
    return bool(record and record.get("estado") == STATUS_DECLINED)


def consent_status_text(number: int) -> str:
    """Texto corto para la tabla de participantes."""
    if has_signed(number):
        return "Firmado"
    if has_declined(number):
        return "No participa"
    return "Pendiente"


def save_signed(number: int, nombre: str, ci: str, correo: str, send_copy: bool, pdf_path: Path) -> dict:
    data = _load()
    record = {
        "numero_participante": number,
        "estado": STATUS_SIGNED,
        "version_documento": CONSENT_VERSION,
        "firmado_en": datetime.now().isoformat(timespec="seconds"),
        "nombre": nombre,
        "ci": ci,
        "correo": correo,
        "pdf": str(pdf_path),
        "envio": {
            RECIPIENT_RESEARCHER: MAIL_PENDING,
            RECIPIENT_PARTICIPANT: MAIL_PENDING if send_copy else MAIL_NOT_REQUESTED,
            "ultimo_intento": None,
            "ultimo_error": None,
        },
    }
    data[participant_code(number)] = record
    _save(data)
    return record


def save_declined(number: int) -> None:
    """Solo deja constancia de que no quiso participar -- sin nombre,
    C.I. ni correo."""
    data = _load()
    data[participant_code(number)] = {
        "numero_participante": number,
        "estado": STATUS_DECLINED,
        "version_documento": CONSENT_VERSION,
        "rechazado_en": datetime.now().isoformat(timespec="seconds"),
    }
    _save(data)


def update_mail_status(number: int, recipient: str, status: str) -> None:
    data = _load()
    record = data.get(participant_code(number))
    if not record or "envio" not in record:
        return
    record["envio"][recipient] = status
    _save(data)


def record_mail_attempt(number: int, error: Optional[str]) -> None:
    data = _load()
    record = data.get(participant_code(number))
    if not record or "envio" not in record:
        return
    record["envio"]["ultimo_intento"] = datetime.now().isoformat(timespec="seconds")
    record["envio"]["ultimo_error"] = error
    _save(data)


def request_participant_copy(number: int) -> None:
    """Usado por "Reenviar copia": vuelve a dejar pendientes ambos
    envíos aunque ya hubieran salido."""
    data = _load()
    record = data.get(participant_code(number))
    if not record or "envio" not in record:
        return
    record["envio"][RECIPIENT_RESEARCHER] = MAIL_PENDING
    if record["envio"].get(RECIPIENT_PARTICIPANT) != MAIL_NOT_REQUESTED:
        record["envio"][RECIPIENT_PARTICIPANT] = MAIL_PENDING
    _save(data)


def has_pending_mail(record: dict) -> bool:
    envio = record.get("envio") or {}
    return MAIL_PENDING in (envio.get(RECIPIENT_RESEARCHER), envio.get(RECIPIENT_PARTICIPANT))


def pending_mail_numbers() -> list[int]:
    return [
        record["numero_participante"]
        for record in _load().values()
        if record.get("estado") == STATUS_SIGNED and has_pending_mail(record)
    ]
