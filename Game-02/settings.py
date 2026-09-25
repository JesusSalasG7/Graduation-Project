"""
settings.py

Configuración leída automáticamente por gale.conf.settings: basta con que
este archivo exista junto a main.py para que Game la resuelva sola.
"""

from pathlib import Path

TITLE = "2048"
WINDOW_WIDTH = 700
WINDOW_HEIGHT = 850
VIRTUAL_WIDTH = 700
VIRTUAL_HEIGHT = 850
FPS = 60

# Recursos (rutas absolutas, para no depender del directorio de trabajo).
BASE_DIR = Path(__file__).resolve().parent
COVER_PATH = BASE_DIR / "assets" / "images" / "Cover.png"
CHECK_SOUND_PATH = BASE_DIR / "assets" / "sounds" / "check.mp3"
GAME_MUSIC_PATH = BASE_DIR / "assets" / "sounds" / "Bucle_music.mp3"
