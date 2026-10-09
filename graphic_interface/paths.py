"""Rutas compartidas del panel, en un solo lugar para que no dependan de
en que subpaquete (ui/, sensors/, ...) vive cada módulo."""

from pathlib import Path

GUI_DIR = Path(__file__).resolve().parent  # graphic_interface/
PROJECT_ROOT = GUI_DIR.parent
TOOLS_DIR = PROJECT_ROOT / "tools"
DATA_DIR = GUI_DIR / "data"
ASSETS_DIR = GUI_DIR / "assets"
GUI_REQUIREMENTS = GUI_DIR / "requirements.txt"

# Carta de consentimiento informado original (nunca se modifica: las
# copias firmadas se guardan aparte). La versión va en el nombre del
# archivo y en el registro de cada firma.
CONSENT_VERSION = "1.0"
CONSENT_PDF = ASSETS_DIR / "consentimiento" / f"consentimiento_v{CONSENT_VERSION}.pdf"
