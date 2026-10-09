"""Prueba rápida y manual de la configuración de correo (archivo `.env` de
la raíz del proyecto), sin abrir la app ni firmar ningún consentimiento.

No imprime la contraseña SMTP -- solo qué claves están completas y el
resultado del envío.

Uso:
    cp .env.example .env        # y completar SMTP_USER / SMTP_PASSWORD
    .venv/bin/python graphic_interface/scripts/test_email_config.py
    .venv/bin/python graphic_interface/scripts/test_email_config.py otro@correo.com
"""

import sys
from pathlib import Path

# Script suelto: agrega graphic_interface/ al path para poder importar sus paquetes.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from consent import consent_mailer  # noqa: E402

print(f"Archivo de configuración: {consent_mailer.ENV_FILE}")

try:
    config = consent_mailer.load_config()
except consent_mailer.MailConfigError as exc:
    print(f"Configuración incompleta: {exc}")
    raise SystemExit(1)

destination = sys.argv[1] if len(sys.argv) > 1 else config.researcher_email
print(f"Servidor: {config.host}:{config.port} ({'SSL' if config.port == 465 else 'STARTTLS'})")
print(f"Usuario: {config.user}  |  Contraseña: {'configurada' if config.password else 'vacía'}")
print(f"Enviando correo de prueba a {destination}...")

result = consent_mailer.send_test_email(destination)
print(("OK: " if result.ok else "Falló: ") + result.message)
raise SystemExit(0 if result.ok else 1)
