"""Envío por correo del consentimiento firmado (smtplib + EmailMessage).

La configuración sale del archivo `.env` de la raíz del proyecto (ver
`.env.example`), nunca del código. Si el envío falla -- sin internet,
credenciales erróneas, `.env` sin completar -- no se bloquea el estudio:
queda pendiente en el registro (`consent_store`) y se reintenta al
iniciar la app o con "Reenviar copia".

Ni la contraseña SMTP ni los datos del participante se imprimen o
registran: los mensajes de error que devuelve este módulo son genéricos.
"""

import os
import smtplib
import ssl
import threading
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Callable, Optional

from dotenv import dotenv_values

from paths import PROJECT_ROOT
from storage import consent_store

ENV_FILE = PROJECT_ROOT / ".env"

DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 587
SMTP_TIMEOUT = 20

SUBJECT = "Consentimiento informado – Proyecto Vibe Coding (ULA)"

# Un solo envío a la vez: evita que el reintento del arranque y un
# "Reenviar copia" manden el mismo correo dos veces.
_send_lock = threading.Lock()


class MailConfigError(RuntimeError):
    """Falta completar el `.env`."""


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    user: str
    password: str
    researcher_email: str


def load_config() -> SmtpConfig:
    """Lee solo las claves SMTP del `.env` (sin volcarlo a os.environ,
    para no tocar el resto de la configuración de la app). Una variable
    de entorno ya exportada tiene prioridad sobre el archivo."""
    file_values = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}

    def read(key: str, default: str = "") -> str:
        return (os.environ.get(key) or file_values.get(key) or default).strip()

    user = read("SMTP_USER")
    password = read("SMTP_PASSWORD")
    researcher = read("RESEARCHER_EMAIL")
    missing = [
        key for key, value in (
            ("SMTP_USER", user), ("SMTP_PASSWORD", password), ("RESEARCHER_EMAIL", researcher),
        ) if not value
    ]
    if missing:
        raise MailConfigError(
            f"Falta configurar {', '.join(missing)} en {ENV_FILE} "
            "(copia .env.example a .env y complétalo)."
        )
    try:
        port = int(read("SMTP_PORT", str(DEFAULT_SMTP_PORT)))
    except ValueError:
        raise MailConfigError("SMTP_PORT debe ser un número (587 o 465).") from None
    return SmtpConfig(
        host=read("SMTP_HOST", DEFAULT_SMTP_HOST), port=port,
        user=user, password=password, researcher_email=researcher,
    )


def _participant_body(researcher_email: str) -> str:
    return (
        "Hola,\n\n"
        "Gracias por aceptar participar en el estudio del Proyecto Vibe Coding "
        "(Escuela de Ingeniería de Sistemas, ULA).\n\n"
        "En este correo se adjunta tu copia firmada de la carta de consentimiento "
        "informado.\n\n"
        "Te recuerdo que tu participación es voluntaria y que puedes retirarte en "
        "cualquier momento, sin dar explicaciones y sin ninguna consecuencia.\n\n"
        f"Ante cualquier duda puedes escribir a: {researcher_email}\n\n"
        "Saludos,\n"
        "Jesús Salas\n"
    )


def _researcher_body(code: str) -> str:
    return (
        f"Se adjunta la carta de consentimiento informado firmada por el participante {code}.\n\n"
        "Este correo se generó automáticamente desde el panel del experimento.\n"
    )


def build_message(config: SmtpConfig, to: str, body: str, pdf_path: Path) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = SUBJECT
    message["From"] = config.user
    message["To"] = to
    message["Reply-To"] = config.researcher_email
    message.set_content(body)
    message.add_attachment(
        Path(pdf_path).read_bytes(), maintype="application", subtype="pdf", filename=Path(pdf_path).name,
    )
    return message


def _connect(config: SmtpConfig) -> smtplib.SMTP:
    context = ssl.create_default_context()
    if config.port == 465:
        server = smtplib.SMTP_SSL(config.host, config.port, timeout=SMTP_TIMEOUT, context=context)
    else:
        server = smtplib.SMTP(config.host, config.port, timeout=SMTP_TIMEOUT)
        server.starttls(context=context)
    server.login(config.user, config.password)
    return server


def _friendly_error(exc: Exception) -> str:
    """Mensaje para mostrar/guardar -- sin detalles del servidor que
    pudieran arrastrar direcciones o credenciales."""
    if isinstance(exc, MailConfigError):
        return str(exc)
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return (
            "El servidor rechazó el usuario o la contraseña SMTP. Con Gmail hace falta "
            "una \"contraseña de aplicación\", no la contraseña normal de la cuenta."
        )
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "El servidor rechazó la dirección de correo del destinatario."
    if isinstance(exc, smtplib.SMTPException):
        return f"El servidor de correo devolvió un error ({type(exc).__name__})."
    if isinstance(exc, (OSError, TimeoutError)):
        return "No se pudo conectar con el servidor de correo (¿sin internet?)."
    return f"Error inesperado al enviar el correo ({type(exc).__name__})."


@dataclass(frozen=True)
class SendResult:
    ok: bool
    message: str


def send_consent(number: int) -> SendResult:
    """Envía lo que esté pendiente del consentimiento de `number` (al
    investigador y, si lo pidió, al participante). Bloqueante: desde la
    interfaz usar `send_consent_async`."""
    with _send_lock:
        record = consent_store.get_record(number)
        if not record or record.get("estado") != consent_store.STATUS_SIGNED:
            return SendResult(False, "Este participante no tiene un consentimiento firmado.")
        pdf_path = Path(record["pdf"])
        if not pdf_path.exists():
            return SendResult(False, "No se encontró el PDF firmado para adjuntar.")

        envio = record["envio"]
        code = consent_store.participant_code(number)
        sent_to: list[str] = []
        try:
            config = load_config()
            pending = []
            if envio.get(consent_store.RECIPIENT_RESEARCHER) == consent_store.MAIL_PENDING:
                pending.append((
                    consent_store.RECIPIENT_RESEARCHER, config.researcher_email, _researcher_body(code),
                ))
            if envio.get(consent_store.RECIPIENT_PARTICIPANT) == consent_store.MAIL_PENDING:
                pending.append((
                    consent_store.RECIPIENT_PARTICIPANT, record["correo"],
                    _participant_body(config.researcher_email),
                ))
            if not pending:
                return SendResult(True, "La copia ya había sido enviada.")

            server = _connect(config)
            try:
                for recipient, address, body in pending:
                    server.send_message(build_message(config, address, body, pdf_path))
                    # Se marca uno por uno: si el segundo falla, el
                    # reintento no repite el que ya salió.
                    consent_store.update_mail_status(number, recipient, consent_store.MAIL_SENT)
                    sent_to.append(address)
            finally:
                try:
                    server.quit()
                except Exception:
                    pass
        except Exception as exc:  # noqa: BLE001 -- cualquier fallo deja el envío pendiente
            error = _friendly_error(exc)
            consent_store.record_mail_attempt(number, error)
            return SendResult(False, f"No se pudo enviar la copia; queda pendiente. {error}")

        consent_store.record_mail_attempt(number, None)
        return SendResult(True, f"Copia enviada a {' y '.join(sent_to)}.")


def send_consent_async(number: int, on_done: Optional[Callable[[SendResult], None]] = None) -> threading.Thread:
    """Igual que `send_consent` pero en un hilo aparte. `on_done` se
    llama DESDE ESE HILO: quien toque widgets debe reprogramarlo con
    `widget.after(0, ...)`."""
    def worker():
        result = send_consent(number)
        if on_done is not None:
            on_done(result)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return thread


def retry_pending_async(on_done: Optional[Callable[[int, int], None]] = None) -> Optional[threading.Thread]:
    """Reintenta todos los envíos pendientes (al iniciar la app).
    `on_done(enviados, fallidos)` se llama desde el hilo."""
    numbers = consent_store.pending_mail_numbers()
    if not numbers:
        return None

    def worker():
        results = [send_consent(number) for number in numbers]
        if on_done is not None:
            sent = sum(1 for r in results if r.ok)
            on_done(sent, len(results) - sent)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return thread


def send_test_email(to: Optional[str] = None) -> SendResult:
    """Prueba la configuración SMTP con un correo sin adjuntos (ver
    scripts/test_email_config.py)."""
    try:
        config = load_config()
        message = EmailMessage()
        message["Subject"] = "Prueba de correo – Proyecto Vibe Coding (ULA)"
        message["From"] = config.user
        message["To"] = to or config.researcher_email
        message.set_content(
            "Este es un correo de prueba del panel del experimento.\n"
            "Si lo recibiste, la configuración SMTP del archivo .env es correcta.\n"
        )
        server = _connect(config)
        try:
            server.send_message(message)
        finally:
            try:
                server.quit()
            except Exception:
                pass
    except Exception as exc:  # noqa: BLE001
        return SendResult(False, _friendly_error(exc))
    return SendResult(True, f"Correo de prueba enviado a {message['To']}.")
