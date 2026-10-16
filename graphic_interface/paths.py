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

# LLM-as-a-judge (ver judge/): la rúbrica y las fichas de referencia son
# documentos fijos que el código solo lee, igual que la carta de
# consentimiento. El dataset sintético y los resultados viven en data/, en
# la raíz del proyecto, junto a build_dataset.py.
PROJECT_DATA_DIR = PROJECT_ROOT / "data"
JUDGE_ASSETS_DIR = ASSETS_DIR / "juez"
JUDGE_RUBRIC_FILE = JUDGE_ASSETS_DIR / "rubrica.md"
JUDGE_SPECS_FILE = JUDGE_ASSETS_DIR / "especificaciones.md"
JUDGE_DATASET_FILE = PROJECT_DATA_DIR / "dataset_prompts.json"
JUDGE_RESULTS_DIR = PROJECT_DATA_DIR / "juez"
