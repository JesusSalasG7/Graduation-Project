"""
main.py

Punto de entrada de 2048 (Pygame + framework Gale).

Ejecutar desde este directorio con:
    python main.py
(o, si se usa el entorno virtual sugerido en requirements.txt:
    ./.venv/bin/python main.py)
"""
from __future__ import annotations

from src.game_2048 import Game2048


if __name__ == "__main__":
    Game2048().exec()
