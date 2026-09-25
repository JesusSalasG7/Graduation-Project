"""Rutas compartidas del panel, en un solo lugar para que no dependan de
en que subpaquete (ui/, sensors/, ...) vive cada modulo."""

from pathlib import Path

GUI_DIR = Path(__file__).resolve().parent  # graphic_interface/
PROJECT_ROOT = GUI_DIR.parent
TOOLS_DIR = PROJECT_ROOT / "tools"
DATA_DIR = GUI_DIR / "data"
ASSETS_DIR = GUI_DIR / "assets"
GUI_REQUIREMENTS = GUI_DIR / "requirements.txt"
